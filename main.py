"""Thinking of You - backend API (first draft).

Run:  pip install -r requirements.txt
      uvicorn main:app --reload
Docs: http://localhost:8000/docs  (interactive API tester)
"""
import hashlib
import html
import base64
import io
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
from sqlmodel import Field, Session, SQLModel, and_, create_engine, or_, select
from PIL import Image, ImageOps

from catalog import CATEGORIES, guess_category, is_product_url, looks_like_product, product_key, store_name
from thumbs import page_metadata

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
    profile_photo: str = ""   # normalized 256px JPEG, base64 encoded


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
    score_adjustment: int = 0
    hidden: bool = False      # deleted auto items stay hidden so they never come back
    private: bool = False     # hidden from everyone you're connected with, still visible to you
    image_url: str = ""       # product photo address (the picture itself is not stored)
    category: str = ""        # blank = guessed from the title
    created_at: Optional[datetime] = None
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_view_counted_at: Optional[datetime] = None


class Link(SQLModel, table=True):
    """A two-way connection between two people. Each side has its own label for the other."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_a: int = Field(index=True)
    user_b: int = Field(index=True)
    a_sees_b_as: str = "Friend"
    b_sees_a_as: str = "Friend"


class Invite(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    inviter_id: int = Field(index=True)
    code: str = Field(index=True)
    label: str = "Friend"  # what the inviter calls the person they invite
    expires_at: datetime


class LoginToken(SQLModel, table=True):
    """One row per active login (app, extension, ...). Only a hash of the token is stored."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    token_hash: str = Field(index=True)
    expires_at: datetime


class GiftClaim(SQLModel, table=True):
    """A gift claim is visible to connected gift-givers, never to the list owner."""
    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(unique=True, index=True)
    claimant_id: int = Field(index=True)
    purchased: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GiftSublist(SQLModel, table=True):
    """A private collection curated by one connection for another person's list."""
    id: Optional[int] = Field(default=None, primary_key=True)
    curator_id: int = Field(index=True)
    owner_id: int = Field(index=True)
    title: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GiftSublistItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sublist_id: int = Field(index=True)
    item_id: int = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


SQLModel.metadata.create_all(engine)


def migrate():
    """Upgrades a database made by an earlier version (keeps existing data)."""
    new_cols = [("item", "image_url", "TEXT DEFAULT ''"), ("item", "category", "TEXT DEFAULT ''"),
                ("item", "created_at", "TIMESTAMP"), ("item", "score_adjustment", "INTEGER DEFAULT 0"),
                ("item", "last_view_counted_at", "TIMESTAMP")]
    old_cols = [("item", "private", "BOOLEAN DEFAULT 0"), ("user", "consented", "BOOLEAN DEFAULT 0"),
                ("user", "profile_photo", "TEXT DEFAULT ''")]
    with engine.begin() as c:
        if IS_SQLITE:
            for table, col, ddl in old_cols + new_cols:
                cols = [r[1] for r in c.exec_driver_sql(f'PRAGMA table_info("{table}")')]
                if col not in cols:
                    c.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN {col} {ddl}')
        else:
            postgres_old_cols = [("item", "private", "BOOLEAN DEFAULT FALSE"),
                                 ("user", "consented", "BOOLEAN DEFAULT FALSE"),
                                 ("user", "profile_photo", "TEXT DEFAULT ''")]
            for table, col, ddl in postgres_old_cols + new_cols:
                c.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS {col} {ddl}')
    with Session(engine) as s:  # old one-partner pairs become connections
        paired = s.exec(select(User).where(User.partner_id != None)).all()  # noqa: E711
        for u in paired:
            other = s.get(User, u.partner_id)
            if other and other.partner_id == u.id and u.id < other.id:
                s.add(Link(user_a=u.id, user_b=other.id, a_sees_b_as="Partner", b_sees_a_as="Partner"))
            u.partner_id = None
            s.add(u)
        s.commit()


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


def normalize_profile_photo(encoded: str) -> str:
    """Validate an uploaded raster image and store a small, normalized square JPEG."""
    if not encoded:
        return ""
    if encoded.startswith("data:"):
        header, sep, encoded = encoded.partition(",")
        if not sep or not header.lower().startswith(("data:image/jpeg;", "data:image/png;", "data:image/webp;")):
            raise HTTPException(422, "Use a JPEG, PNG, or WebP image")
    try:
        raw = base64.b64decode(encoded, validate=True)
        if not raw or len(raw) > 5_000_000:
            raise ValueError("image too large")
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"} or source.width * source.height > 25_000_000:
                raise ValueError("unsupported image")
            source.load()
            square = ImageOps.fit(source.convert("RGB"), (256, 256), method=Image.Resampling.LANCZOS)
            out = io.BytesIO()
            square.save(out, format="JPEG", quality=86, optimize=True)
        return base64.b64encode(out.getvalue()).decode("ascii")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "That photo could not be read. Choose a JPEG, PNG, or WebP image.")


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

def to_dict(i: Item) -> dict:
    title, desc = html.unescape(i.title), html.unescape(i.description)
    return {"id": i.id, "title": title, "description": desc, "price": i.price, "url": i.url,
            "source": i.source, "private": i.private,
            "score": max(0, i.views + CART_WEIGHT * i.carts + i.score_adjustment),
            "score_adjustment": i.score_adjustment,
            "image_url": i.image_url or "", "store": store_name(i.url),
            "category": i.category or guess_category(title, desc, i.url),
            "added": as_utc(i.created_at or i.last_seen).isoformat()}


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
    age_confirmed: bool = False  # must be true: this service is for people 13 and older
    profile_photo: str = PField("", max_length=7_000_000)


class Login(BaseModel):
    email: str = PField(max_length=254)
    password: str = PField(max_length=128)


@app.post("/register")
def register(body: Register, request: Request, s: Session = Depends(get_session)):
    rate_limit(f"register:{client_ip(request)}", 10, 3600)
    if not body.age_confirmed:
        raise HTTPException(400, "You must be 13 or older to sign up.")
    email = body.email.strip().lower()
    if s.exec(select(User).where(User.email == email)).first():
        raise HTTPException(400, "Email already registered")
    salt = secrets.token_hex(16)
    photo = normalize_profile_photo(body.profile_photo) if body.profile_photo else ""
    user = User(email=email, name=body.name.strip(), salt=salt, pw_hash=hash_pw(body.password, salt),
                token="", profile_photo=photo)
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
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "tracking_on": user.tracking_on,
            "consented": user.consented, "profile_photo": user.profile_photo or ""}


class ProfilePhotoIn(BaseModel):
    photo: str = PField(min_length=1, max_length=7_000_000)


@app.put("/profile/photo")
def update_profile_photo(body: ProfilePhotoIn, user: User = Depends(current_user), s: Session = Depends(get_session)):
    user.profile_photo = normalize_profile_photo(body.photo)
    s.add(user)
    s.commit()
    return {"profile_photo": user.profile_photo}


@app.delete("/profile/photo")
def remove_profile_photo(user: User = Depends(current_user), s: Session = Depends(get_session)):
    user.profile_photo = ""
    s.add(user)
    s.commit()
    return {"profile_photo": ""}


@app.get("/meta")
def meta():
    return {"categories": CATEGORIES, "labels": ["Partner", "Parent", "Child", "Friend", "Sibling", "Other"]}


# ---------- Connections (any two people can link, and one person can have many) ----------
INVERSE = {"Parent": "Child", "Child": "Parent"}
INVITE_DAYS = 7


def link_between(s: Session, a: int, b: int) -> Optional[Link]:
    return s.exec(select(Link).where(or_(and_(Link.user_a == a, Link.user_b == b),
                                         and_(Link.user_a == b, Link.user_b == a)))).first()


class InviteIn(BaseModel):
    label: str = PField("Friend", min_length=1, max_length=20)  # what you call the person you're inviting


@app.post("/invites")
def create_invite(body: InviteIn, user: User = Depends(current_user), s: Session = Depends(get_session)):
    rate_limit(f"invite:{user.id}", 20, 3600)
    label = body.label.strip()
    if not label:
        raise HTTPException(422, "Label cannot be blank")
    invite = Invite(inviter_id=user.id, code=secrets.token_hex(12).upper(), label=label,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_DAYS))
    s.add(invite)
    s.commit()
    return {"code": invite.code, "label": invite.label}


@app.get("/invites")
def my_invites(user: User = Depends(current_user), s: Session = Depends(get_session)):
    now = datetime.now(timezone.utc)
    rows = s.exec(select(Invite).where(Invite.inviter_id == user.id)).all()
    return [{"code": i.code, "label": i.label, "expires_at": as_utc(i.expires_at).isoformat()}
            for i in rows if as_utc(i.expires_at) > now]


class Accept(BaseModel):
    code: str = PField(min_length=1, max_length=32)


@app.post("/invites/accept")
def accept_invite(body: Accept, request: Request, user: User = Depends(current_user), s: Session = Depends(get_session)):
    rate_limit(f"accept:{user.id}", 10, 900)
    rate_limit(f"accept-ip:{client_ip(request)}", 30, 900)
    invite = s.exec(select(Invite).where(Invite.code == body.code.strip().upper())).first()
    inviter = s.get(User, invite.inviter_id) if invite else None
    if not inviter or inviter.id == user.id or as_utc(invite.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(400, "Invalid or expired code")
    if link_between(s, inviter.id, user.id):
        raise HTTPException(400, "You're already connected")
    link = Link(user_a=inviter.id, user_b=user.id, a_sees_b_as=invite.label,
                b_sees_a_as=INVERSE.get(invite.label, invite.label))
    s.add(link)
    s.delete(invite)  # codes work once
    s.commit()
    s.refresh(link)
    return {"id": link.id, "name": inviter.name, "label": link.b_sees_a_as}


def my_link(s: Session, link_id: int, user: User) -> Link:
    link = s.get(Link, link_id)
    if not link or user.id not in (link.user_a, link.user_b):
        raise HTTPException(404, "Connection not found")
    return link


@app.get("/connections")
def connections(user: User = Depends(current_user), s: Session = Depends(get_session)):
    links = s.exec(select(Link).where(or_(Link.user_a == user.id, Link.user_b == user.id))).all()
    out = []
    for link in links:
        mine = link.user_a == user.id
        other = s.get(User, link.user_b if mine else link.user_a)
        if other:
            out.append({"id": link.id, "user_id": other.id, "name": other.name,
                        "label": link.a_sees_b_as if mine else link.b_sees_a_as,
                        "profile_photo": other.profile_photo or "",
                        "item_count": len(ranked_items(s, other.id, include_private=False))})
    return out


class LabelIn(BaseModel):
    label: str = PField(min_length=1, max_length=20)


@app.patch("/connections/{link_id}")
def relabel(link_id: int, body: LabelIn, user: User = Depends(current_user), s: Session = Depends(get_session)):
    link = my_link(s, link_id, user)
    label = body.label.strip()
    if not label:
        raise HTTPException(422, "Label cannot be blank")
    if link.user_a == user.id:
        link.a_sees_b_as = label
    else:
        link.b_sees_a_as = label
    s.add(link)
    s.commit()
    return {"label": label}


@app.delete("/connections/{link_id}")
def disconnect(link_id: int, user: User = Depends(current_user), s: Session = Depends(get_session)):
    link = my_link(s, link_id, user)
    other_id = link.user_b if link.user_a == user.id else link.user_a
    s.delete(link)
    for claim in s.exec(select(GiftClaim)).all():
        item = s.get(Item, claim.item_id)
        if item and ((claim.claimant_id == user.id and item.owner_id == other_id) or
                     (claim.claimant_id == other_id and item.owner_id == user.id)):
            s.delete(claim)
    for sublist in s.exec(select(GiftSublist).where(
            or_(and_(GiftSublist.curator_id == user.id, GiftSublist.owner_id == other_id),
                and_(GiftSublist.curator_id == other_id, GiftSublist.owner_id == user.id)))).all():
        for row in s.exec(select(GiftSublistItem).where(GiftSublistItem.sublist_id == sublist.id)).all():
            s.delete(row)
        s.delete(sublist)
    s.commit()
    return {"disconnected": True}


@app.get("/people/{user_id}/items")
def people_items(user_id: int, user: User = Depends(current_user), s: Session = Depends(get_session)):
    if not link_between(s, user.id, user_id):
        raise HTTPException(404, "Not connected")
    items = ranked_items(s, user_id, include_private=False)  # live, and never includes private items
    visible_ids = [item["id"] for item in items]
    claims = s.exec(select(GiftClaim).where(GiftClaim.item_id.in_(visible_ids))).all() if visible_ids else []
    claim_by_item = {claim.item_id: claim for claim in claims}
    for item in items:
        claim = claim_by_item.get(item["id"])
        item["gift_status"] = ("purchased" if claim.purchased else "claimed") if claim else "available"
        item["claimed_by_me"] = bool(claim and claim.claimant_id == user.id)
    return items


def connected_owner(owner_id: int, user: User, s: Session) -> None:
    if not link_between(s, user.id, owner_id):
        raise HTTPException(404, "Not connected")


@app.post("/people/{user_id}/items/{item_id}/claim")
def claim_gift(user_id: int, item_id: int, user: User = Depends(current_user), s: Session = Depends(get_session)):
    connected_owner(user_id, user, s)
    item = s.get(Item, item_id)
    if not item or item.owner_id != user_id or item.hidden or item.private:
        raise HTTPException(404, "Item not found")
    claim = s.exec(select(GiftClaim).where(GiftClaim.item_id == item_id)).first()
    if claim and claim.claimant_id != user.id:
        raise HTTPException(409, "Someone else has already claimed this gift")
    if not claim:
        claim = GiftClaim(item_id=item_id, claimant_id=user.id)
        s.add(claim)
        s.commit()
    return {"gift_status": "purchased" if claim.purchased else "claimed", "claimed_by_me": True}


class PurchasedIn(BaseModel):
    purchased: bool


@app.patch("/people/{user_id}/items/{item_id}/claim")
def update_claim(user_id: int, item_id: int, body: PurchasedIn,
                 user: User = Depends(current_user), s: Session = Depends(get_session)):
    connected_owner(user_id, user, s)
    claim = s.exec(select(GiftClaim).where(GiftClaim.item_id == item_id,
                                           GiftClaim.claimant_id == user.id)).first()
    if not claim:
        raise HTTPException(404, "Your claim was not found")
    claim.purchased = body.purchased
    s.add(claim)
    s.commit()
    return {"gift_status": "purchased" if claim.purchased else "claimed", "claimed_by_me": True}


@app.delete("/people/{user_id}/items/{item_id}/claim")
def release_claim(user_id: int, item_id: int, user: User = Depends(current_user), s: Session = Depends(get_session)):
    connected_owner(user_id, user, s)
    claim = s.exec(select(GiftClaim).where(GiftClaim.item_id == item_id,
                                           GiftClaim.claimant_id == user.id)).first()
    if claim:
        s.delete(claim)
        s.commit()
    return {"released": True}


class SublistIn(BaseModel):
    title: str = PField(min_length=1, max_length=60)


class SublistItemIn(BaseModel):
    item_id: int


def sublist_for_curator(s: Session, sublist_id: int, user: User) -> GiftSublist:
    sublist = s.get(GiftSublist, sublist_id)
    if not sublist or sublist.curator_id != user.id:
        raise HTTPException(404, "Gift list not found")
    if not link_between(s, user.id, sublist.owner_id):
        raise HTTPException(404, "Not connected")
    return sublist


def sublist_dict(s: Session, sublist: GiftSublist) -> dict:
    rows = s.exec(select(GiftSublistItem).where(GiftSublistItem.sublist_id == sublist.id)).all()
    items = []
    for row in rows:
        item = s.get(Item, row.item_id)
        if item and item.owner_id == sublist.owner_id and not item.hidden and not item.private:
            items.append(to_dict(item))
    return {"id": sublist.id, "owner_id": sublist.owner_id, "title": sublist.title,
            "created_at": as_utc(sublist.created_at).isoformat(), "items": items}


@app.get("/people/{user_id}/sublists")
def get_sublists(user_id: int, user: User = Depends(current_user), s: Session = Depends(get_session)):
    connected_owner(user_id, user, s)
    lists = s.exec(select(GiftSublist).where(GiftSublist.curator_id == user.id,
                                              GiftSublist.owner_id == user_id)).all()
    return [sublist_dict(s, row) for row in lists]


@app.post("/people/{user_id}/sublists")
def create_sublist(user_id: int, body: SublistIn, user: User = Depends(current_user), s: Session = Depends(get_session)):
    connected_owner(user_id, user, s)
    title = body.title.strip()
    if not title:
        raise HTTPException(422, "Gift list name cannot be blank")
    sublist = GiftSublist(curator_id=user.id, owner_id=user_id, title=title)
    s.add(sublist)
    s.commit()
    s.refresh(sublist)
    return sublist_dict(s, sublist)


@app.post("/sublists/{sublist_id}/items")
def add_to_sublist(sublist_id: int, body: SublistItemIn, user: User = Depends(current_user),
                   s: Session = Depends(get_session)):
    sublist = sublist_for_curator(s, sublist_id, user)
    item = s.get(Item, body.item_id)
    if not item or item.owner_id != sublist.owner_id or item.hidden or item.private:
        raise HTTPException(404, "Item not found")
    existing = s.exec(select(GiftSublistItem).where(GiftSublistItem.sublist_id == sublist_id,
                                                     GiftSublistItem.item_id == body.item_id)).first()
    if not existing:
        s.add(GiftSublistItem(sublist_id=sublist_id, item_id=body.item_id))
        s.commit()
    return sublist_dict(s, sublist)


@app.delete("/sublists/{sublist_id}/items/{item_id}")
def remove_from_sublist(sublist_id: int, item_id: int, user: User = Depends(current_user),
                        s: Session = Depends(get_session)):
    sublist = sublist_for_curator(s, sublist_id, user)
    row = s.exec(select(GiftSublistItem).where(GiftSublistItem.sublist_id == sublist_id,
                                                GiftSublistItem.item_id == item_id)).first()
    if row:
        s.delete(row)
        s.commit()
    return sublist_dict(s, sublist)


@app.delete("/sublists/{sublist_id}")
def delete_sublist(sublist_id: int, user: User = Depends(current_user), s: Session = Depends(get_session)):
    sublist = sublist_for_curator(s, sublist_id, user)
    for row in s.exec(select(GiftSublistItem).where(GiftSublistItem.sublist_id == sublist_id)).all():
        s.delete(row)
    s.delete(sublist)
    s.commit()
    return {"deleted": True}


# ---------- Lists ----------
@app.get("/items/me")
def my_items(user: User = Depends(current_user), s: Session = Depends(get_session)):
    return ranked_items(s, user.id)


class NewItem(BaseModel):
    title: str = PField(min_length=1, max_length=500)
    private: bool = False
    description: str = PField("", max_length=5000)
    price: Optional[float] = PField(None, ge=0, le=1_000_000)
    url: str = PField("", max_length=2000, pattern=r"^(https?://.*)?$")  # web links only
    image_url: str = PField("", max_length=2000, pattern=r"^(https://.*)?$")
    category: str = PField("", max_length=30)  # blank = guess it


class PreviewIn(BaseModel):
    url: str = PField(min_length=1, max_length=2000, pattern=r"^https://.*$")


@app.post("/items/preview")
def preview_item(body: PreviewIn, user: User = Depends(current_user)):
    rate_limit(f"preview:{user.id}", 20, 60)
    try:
        return page_metadata(body.url)
    except Exception:
        raise HTTPException(422, "Couldn't safely read product details from that link. You can still add it manually.")


@app.post("/items")
def add_item(body: NewItem, user: User = Depends(current_user), s: Session = Depends(get_session)):
    rate_limit(f"items:{user.id}", 60, 60)
    if body.category and body.category not in CATEGORIES:
        raise HTTPException(422, "Unknown category")
    item = Item(owner_id=user.id, source="manual", views=MANUAL_START_SCORE, title=body.title,
                description=body.description, price=body.price, url=body.url, private=body.private,
                image_url=body.image_url, created_at=datetime.now(timezone.utc),
                category=body.category or guess_category(body.title, body.description, body.url))
    s.add(item)
    s.commit()
    s.refresh(item)
    return to_dict(item)


class CategoryIn(BaseModel):
    category: str


@app.patch("/items/{item_id}/category")
def set_category(item_id: int, body: CategoryIn, user: User = Depends(current_user),
                 s: Session = Depends(get_session)):
    item = s.get(Item, item_id)
    if not item or item.owner_id != user.id:
        raise HTTPException(404, "Item not found")
    if body.category not in CATEGORIES:
        raise HTTPException(422, "Unknown category")
    item.category = body.category
    s.add(item)
    s.commit()
    return to_dict(item)


class ScoreAdjustmentIn(BaseModel):
    delta: int = PField(ge=-100_000, le=100_000)


@app.post("/items/{item_id}/score-adjustment")
def adjust_score(item_id: int, body: ScoreAdjustmentIn, user: User = Depends(current_user),
                 s: Session = Depends(get_session)):
    item = s.get(Item, item_id)
    if not item or item.owner_id != user.id:
        raise HTTPException(404, "Item not found")
    activity_score = item.views + CART_WEIGHT * item.carts
    current_score = max(0, activity_score + item.score_adjustment)
    new_score = max(0, current_score + body.delta)
    item.score_adjustment = max(-activity_score, min(100_000, new_score - activity_score))
    s.add(item)
    s.commit()
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
    claim = s.exec(select(GiftClaim).where(GiftClaim.item_id == item_id)).first()
    if claim:
        s.delete(claim)
    for row in s.exec(select(GiftSublistItem).where(GiftSublistItem.item_id == item_id)).all():
        s.delete(row)
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
    for link in s.exec(select(Link).where(or_(Link.user_a == user.id, Link.user_b == user.id))).all():
        s.delete(link)
    for invite in s.exec(select(Invite).where(Invite.inviter_id == user.id)).all():
        s.delete(invite)
    for item in s.exec(select(Item).where(Item.owner_id == user.id)).all():
        for claim in s.exec(select(GiftClaim).where(GiftClaim.item_id == item.id)).all():
            s.delete(claim)
        for entry in s.exec(select(GiftSublistItem).where(GiftSublistItem.item_id == item.id)).all():
            s.delete(entry)
        s.delete(item)
    for claim in s.exec(select(GiftClaim).where(GiftClaim.claimant_id == user.id)).all():
        s.delete(claim)
    for sublist in s.exec(select(GiftSublist).where(
            or_(GiftSublist.curator_id == user.id, GiftSublist.owner_id == user.id))).all():
        for entry in s.exec(select(GiftSublistItem).where(GiftSublistItem.sublist_id == sublist.id)).all():
            s.delete(entry)
        s.delete(sublist)
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
    image: str = PField("", max_length=2000, pattern=r"^(https://.*)?$")


@app.post("/events")
def track(e: Event, user: User = Depends(current_user), s: Session = Depends(get_session)):
    """Called by the browser extension. Stores counters per product, not a browsing history."""
    rate_limit(f"events:{user.id}", 120, 60)
    if not user.consented or not user.tracking_on or not is_product_url(e.url) or not looks_like_product(e.title):
        return {"tracked": False}
    url, now = clean_url(e.url), datetime.now(timezone.utc)
    key = product_key(url)
    with _track_lock:  # one event at a time, so simultaneous events can't create duplicate rows
        mine = s.exec(select(Item).where(Item.owner_id == user.id)).all()
        matches = [i for i in mine if i.url and product_key(i.url) == key]
        visible = [i for i in matches if not i.hidden]
        item = visible[0] if visible else (matches[0] if matches else None)
        if item is None:
            title, desc = html.unescape(e.title)[:200], html.unescape(e.description)[:500]
            item = Item(owner_id=user.id, title=title, description=desc, price=e.price, url=url,
                        image_url=e.image, created_at=now, last_view_counted_at=now,
                        category=guess_category(title, desc, url))
            is_new = True
        elif item.hidden:
            return {"tracked": False}  # user deleted it; respect that
        else:
            is_new = False
            item.price = item.price or e.price
            item.image_url = e.image or item.image_url
        if e.event == "cart":
            item.carts += 1
        elif e.event == "view":
            last_counted = as_utc(item.last_view_counted_at or item.last_seen)
            if is_new or now - last_counted > VIEW_COOLDOWN:
                item.views += 1
                item.last_view_counted_at = now
        item.last_seen = now
        s.add(item)
        s.commit()
    return {"tracked": True}
