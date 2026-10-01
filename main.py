"""Thinking of You - backend API (first draft).

Run:  pip install -r requirements.txt
      uvicorn main:app --reload
Docs: http://localhost:8000/docs  (interactive API tester)
"""
import hashlib
import html
import os
import re
import secrets
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field as PField
from sqlmodel import Field, Session, SQLModel, create_engine, select

def _db_url() -> str:
    """Local SQLite by default; set DATABASE_URL (for example a Neon address) to use Postgres."""
    url = os.getenv("TOY_DB") or os.getenv("DATABASE_URL") or "sqlite:///thinking_of_you.db"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DB_URL = _db_url()
IS_SQLITE = DB_URL.startswith("sqlite")
engine = create_engine(DB_URL, pool_pre_ping=True,  # pre_ping: reconnect if the host dropped an idle connection
                       **({"connect_args": {"check_same_thread": False}} if IS_SQLITE else {}))
app = FastAPI(title="Thinking of You")

# Only these sites, and only their product pages, are ever tracked.
PRODUCT_PATHS = {
    "amazon.com": r"/(dp|gp/product)/",
    "etsy.com": r"/listing/",
    "target.com": r"/p/",
    "walmart.com": r"/ip/",
    "ebay.com": r"/itm/",
    "shein.com": r"-p-\d+",
}
CART_WEIGHT = 3                       # an add-to-cart counts more than a view
VIEW_COOLDOWN = timedelta(minutes=10)  # page refreshes don't inflate view counts
TOKEN_DAYS = 30  # a login expires after this long
MANUAL_START_SCORE = 5                # manually added items start with a strong signal


# ---------- Database models ----------
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str
    salt: str
    pw_hash: str
    token: str = Field(index=True)
    partner_id: Optional[int] = None
    invite_code: Optional[str] = None
    tracking_on: bool = True
    consented: bool = False   # has agreed to shopping tracking


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(index=True)
    title: str
    description: str = ""
    price: Optional[float] = None
    url: str = ""
    source: str = "auto"      # "auto" (tracked) or "manual"
    views: int = 0
    carts: int = 0
    hidden: bool = False      # deleted auto items stay hidden so they never come back
    private: bool = False     # hidden from the partner's view, still visible to the owner
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LoginToken(SQLModel, table=True):
    """One row per active login (app, extension, ...). Only a hash of the token is stored."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    token_hash: str = Field(index=True)
    expires_at: datetime


SQLModel.metadata.create_all(engine)


def migrate():
    """Adds the new columns to a database created by an earlier version (keeps existing data)."""
    if not IS_SQLITE:
        return  # a fresh Postgres database is created with every column already
    with engine.begin() as c:
        for table, col, ddl in [("item", "private", "BOOLEAN DEFAULT 0"), ("user", "consented", "BOOLEAN DEFAULT 0")]:
            cols = [r[1] for r in c.exec_driver_sql(f'PRAGMA table_info("{table}")')]
            if col not in cols:
                c.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN {col} {ddl}')


migrate()


# ---------- Helpers ----------
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(s: Session, user: User) -> str:
    """Creates a login token that expires after TOKEN_DAYS. Only its hash is saved."""
    now = datetime.now(timezone.utc)
    for old in s.exec(select(LoginToken).where(LoginToken.user_id == user.id)).all():
        if as_utc(old.expires_at) < now:
            s.delete(old)  # tidy up expired logins
    token = secrets.token_urlsafe(32)
    s.add(LoginToken(user_id=user.id, token_hash=hash_token(token), expires_at=now + timedelta(days=TOKEN_DAYS)))
    s.commit()
    return token


_hits: dict = defaultdict(list)
_hits_lock = threading.Lock()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Allows `limit` calls per window for this key, then answers 429 (in memory; resets on restart)."""
    now = time.time()
    with _hits_lock:
        recent = [t for t in _hits[key] if now - t < window_seconds]
        if len(recent) >= limit:
            _hits[key] = recent
            raise HTTPException(429, "Too many attempts. Please wait a few minutes and try again.")
        recent.append(now)
        _hits[key] = recent


def get_session():
    with Session(engine) as s:
        yield s


def hash_pw(password: str, salt: str) -> str:
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1).hex()


bearer = HTTPBearer(auto_error=False)  # adds the "Authorize" button to /docs


def current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
                 s: Session = Depends(get_session)) -> User:
    token = creds.credentials.strip() if creds else ""
    row = s.exec(select(LoginToken).where(LoginToken.token_hash == hash_token(token))).first() if token else None
    if not row or as_utc(row.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(401, "Not logged in")
    user = s.get(User, row.user_id)
    if not user:
        raise HTTPException(401, "Not logged in")
    return user


def as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # SQLite may hand back naive values


def clean_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}"  # drop tracking params / fragments


_track_lock = threading.Lock()  # events are handled one at a time (fine for this single-server draft)

# Each store's product ID, so different-looking links to the same product count as one item
PRODUCT_ID = [r"/A-(\d+)", r"/(?:dp|gp/product)/([A-Z0-9]{10})", r"/listing/(\d+)",
              r"/(?:ip|itm)/(?:[^/]+/)?(\d+)", r"-p-(\d+)"]


def product_key(url: str) -> str:
    p = urlparse(url)
    host = p.netloc.lower().removeprefix("www.")
    for pattern in PRODUCT_ID:
        m = re.search(pattern, p.path)
        if m:
            return f"{host}:{m.group(1)}"
    return clean_url(url)


def is_product_url(url: str) -> bool:
    p = urlparse(url)
    host = p.netloc.lower()
    for domain, pattern in PRODUCT_PATHS.items():
        if host == domain or host.endswith("." + domain):
            return re.search(pattern, p.path) is not None
    return False


def to_dict(i: Item) -> dict:
    return {"id": i.id, "title": html.unescape(i.title), "description": html.unescape(i.description), "price": i.price,
            "url": i.url, "source": i.source, "private": i.private, "score": i.views + CART_WEIGHT * i.carts}


def ranked_items(s: Session, owner_id: int, include_private: bool = True) -> list[dict]:
    items = s.exec(select(Item).where(Item.owner_id == owner_id, Item.hidden == False)).all()  # noqa: E712
    if not include_private:
        items = [i for i in items if not i.private]
    return sorted((to_dict(i) for i in items), key=lambda d: -d["score"])


# ---------- Accounts ----------
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class Register(BaseModel):
    email: str = PField(max_length=254, pattern=EMAIL)
    name: str = PField(min_length=1, max_length=50)
    password: str = PField(min_length=8, max_length=128)


class Login(BaseModel):
    email: str = PField(max_length=254)
    password: str = PField(max_length=128)


@app.post("/register")
def register(body: Register, request: Request, s: Session = Depends(get_session)):
    rate_limit(f"register:{client_ip(request)}", 10, 3600)
    email = body.email.strip().lower()
    if s.exec(select(User).where(User.email == email)).first():
        raise HTTPException(400, "Email already registered")
    salt = secrets.token_hex(16)
    user = User(email=email, name=body.name.strip(), salt=salt, pw_hash=hash_pw(body.password, salt), token="")
    s.add(user)
    s.commit()
    s.refresh(user)
    return {"token": issue_token(s, user)}


@app.post("/login")
def login(body: Login, request: Request, s: Session = Depends(get_session)):
    email = body.email.strip().lower()
    rate_limit(f"login-ip:{client_ip(request)}", 30, 900)
    rate_limit(f"login:{email}", 8, 900)  # slows down password guessing
    user = s.exec(select(User).where(User.email == email)).first()
    if not user or not secrets.compare_digest(user.pw_hash, hash_pw(body.password, user.salt)):
        raise HTTPException(401, "Wrong email or password")
    return {"token": issue_token(s, user), "name": user.name}


@app.post("/logout")
def logout(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer), s: Session = Depends(get_session)):
    token = creds.credentials.strip() if creds else ""
    row = s.exec(select(LoginToken).where(LoginToken.token_hash == hash_token(token))).first() if token else None
    if row:
        s.delete(row)
        s.commit()
    return {"logged_out": True}


@app.get("/health")
def health():
    return {"ok": True}  # lets the app (and Render) check the server is awake


@app.get("/me")
def me(user: User = Depends(current_user), s: Session = Depends(get_session)):
    partner = s.get(User, user.partner_id) if user.partner_id else None
    return {"name": user.name, "tracking_on": user.tracking_on, "consented": user.consented,
            "partner": partner.name if partner else None}


# ---------- Partner linking (both people must opt in) ----------
@app.post("/partner/invite")
def invite(user: User = Depends(current_user), s: Session = Depends(get_session)):
    if user.partner_id:
        raise HTTPException(400, "Already linked")
    user.invite_code = secrets.token_hex(3).upper()
    s.add(user)
    s.commit()
    return {"code": user.invite_code}  # give this code to your partner


class Accept(BaseModel):
    code: str


@app.post("/partner/accept")
def accept(body: Accept, user: User = Depends(current_user), s: Session = Depends(get_session)):
    inviter = s.exec(select(User).where(User.invite_code == body.code.upper())).first()
    if not inviter or inviter.id == user.id or user.partner_id or inviter.partner_id:
        raise HTTPException(400, "Invalid code or already linked")
    inviter.partner_id, user.partner_id = user.id, inviter.id
    inviter.invite_code = user.invite_code = None
    s.add(inviter)
    s.add(user)
    s.commit()
    return {"partner": inviter.name}


@app.delete("/partner")
def unlink(user: User = Depends(current_user), s: Session = Depends(get_session)):
    if user.partner_id:
        partner = s.get(User, user.partner_id)
        if partner:
            partner.partner_id = None
            s.add(partner)
    user.partner_id = None
    s.add(user)
    s.commit()
    return {"unlinked": True}


# ---------- Lists ----------
@app.get("/items/me")
def my_items(user: User = Depends(current_user), s: Session = Depends(get_session)):
    return ranked_items(s, user.id)


@app.get("/items/partner")
def partner_items(user: User = Depends(current_user), s: Session = Depends(get_session)):
    if not user.partner_id:
        raise HTTPException(404, "No linked partner")
    return ranked_items(s, user.partner_id, include_private=False)  # live, and never includes private items


class NewItem(BaseModel):
    title: str = PField(min_length=1, max_length=500)
    private: bool = False
    description: str = PField("", max_length=5000)
    price: Optional[float] = PField(None, ge=0, le=1_000_000)
    url: str = PField("", max_length=2000, pattern=r"^(https?://.*)?$")  # web links only


@app.post("/items")
def add_item(body: NewItem, user: User = Depends(current_user), s: Session = Depends(get_session)):
    rate_limit(f"items:{user.id}", 60, 60)
    item = Item(owner_id=user.id, source="manual", views=MANUAL_START_SCORE, title=body.title,
                description=body.description, price=body.price, url=body.url, private=body.private)
    s.add(item)
    s.commit()
    s.refresh(item)
    return to_dict(item)


@app.delete("/items/{item_id}")
def delete_item(item_id: int, user: User = Depends(current_user), s: Session = Depends(get_session)):
    item = s.get(Item, item_id)
    if not item or item.owner_id != user.id:
        raise HTTPException(404, "Item not found")
    if item.source == "auto":
        item.hidden = True  # keep a tombstone so the tracker never re-adds it
        s.add(item)
    else:
        s.delete(item)
    s.commit()
    return {"deleted": True}


# ---------- Privacy ----------
class PrivateFlag(BaseModel):
    private: bool


@app.patch("/items/{item_id}/private")
def set_private(item_id: int, body: PrivateFlag, user: User = Depends(current_user),
                s: Session = Depends(get_session)):
    item = s.get(Item, item_id)
    if not item or item.owner_id != user.id:
        raise HTTPException(404, "Item not found")
    item.private = body.private
    s.add(item)
    s.commit()
    return to_dict(item)


@app.post("/consent")
def give_consent(user: User = Depends(current_user), s: Session = Depends(get_session)):
    user.consented = True
    s.add(user)
    s.commit()
    return {"consented": True}


class Confirm(BaseModel):
    password: str


@app.delete("/account")
def delete_account(body: Confirm, user: User = Depends(current_user), s: Session = Depends(get_session)):
    rate_limit(f"delete:{user.id}", 5, 900)
    if not secrets.compare_digest(user.pw_hash, hash_pw(body.password, user.salt)):
        raise HTTPException(403, "Wrong password")  # 403, not 401, so the app doesn't log you out
    if user.partner_id:
        partner = s.get(User, user.partner_id)
        if partner:
            partner.partner_id = None
            s.add(partner)
    for item in s.exec(select(Item).where(Item.owner_id == user.id)).all():
        s.delete(item)
    for row in s.exec(select(LoginToken).where(LoginToken.user_id == user.id)).all():
        s.delete(row)
    s.delete(user)
    s.commit()
    return {"deleted": True}


# ---------- Tracking ----------
class Tracking(BaseModel):
    on: bool


@app.patch("/tracking")
def set_tracking(body: Tracking, user: User = Depends(current_user), s: Session = Depends(get_session)):
    user.tracking_on = body.on  # pause/resume switch, always available
    s.add(user)
    s.commit()
    return {"tracking_on": user.tracking_on}


class Event(BaseModel):
    url: str = PField(max_length=2000)
    title: str = PField(min_length=1, max_length=500)
    description: str = PField("", max_length=5000)
    price: Optional[float] = PField(None, ge=0, le=1_000_000)
    event: str = PField("view", pattern="^(view|cart)$")


@app.post("/events")
def track(e: Event, user: User = Depends(current_user), s: Session = Depends(get_session)):
    """Called by the browser extension. Stores counters per product, not a browsing history."""
    rate_limit(f"events:{user.id}", 120, 60)
    if not user.consented or not user.tracking_on or not is_product_url(e.url):
        return {"tracked": False}
    url, now = clean_url(e.url), datetime.now(timezone.utc)
    key = product_key(url)
    with _track_lock:  # one event at a time, so simultaneous events can't create duplicate rows
        mine = s.exec(select(Item).where(Item.owner_id == user.id)).all()
        matches = [i for i in mine if i.url and product_key(i.url) == key]
        visible = [i for i in matches if not i.hidden]
        item = visible[0] if visible else (matches[0] if matches else None)
        if item is None:
            item = Item(owner_id=user.id, title=html.unescape(e.title)[:200], description=html.unescape(e.description)[:500],
                        price=e.price, url=url)
            is_new = True
        elif item.hidden:
            return {"tracked": False}  # user deleted it; respect that
        else:
            is_new = False
            item.price = item.price or e.price
        if e.event == "cart":
            item.carts += 1
        elif is_new or now - as_utc(item.last_seen) > VIEW_COOLDOWN:
            item.views += 1
        item.last_seen = now
        s.add(item)
        s.commit()
    return {"tracked": True}