"""Thinking of You - Streamlit front end.

Run (with the backend already running):  streamlit run App.py
"""
import base64
import html
import io
import os
from pathlib import Path
from urllib.parse import quote

import requests
import streamlit as st
from PIL import Image, ImageOps

from thumbs import photo, warm
from welcome import welcome_screen


def _api_url() -> str:
    """Server address: the API_URL setting when deployed, your own computer otherwise."""
    url = os.getenv("API_URL")
    if not url:
        try:
            url = st.secrets["API_URL"]
        except Exception:
            url = "http://localhost:8000"
    return url.rstrip("/")


API = _api_url()
st.set_page_config(page_title="Thinking of You", page_icon="🎁", layout="centered")

EMOJI = {"Self-care & beauty": "🧴", "Clothes": "👚", "Shoes": "👟", "Accessories & jewelry": "💍",
         "Food & drink": "🍫", "Home & decor": "🕯️", "Tech & gadgets": "🎧", "Sports & fitness": "🏋️",
         "Books & media": "📚", "Toys & games": "🧸", "Hobbies & crafts": "🎨", "Pets": "🐾", "Other": "🎁"}
CATS = list(EMOJI)
LABELS = ["Partner", "Parent", "Child", "Friend", "Sibling", "Other"]
SORTS = ["Most wanted", "Price: low to high", "Price: high to low", "Newest first", "A to Z"]
PASTELS = [("#FFE9EE", "#D6336C"), ("#EFEBFF", "#6142E0"), ("#E3F8F5", "#14907F"),
           ("#FFF3D6", "#B77900"), ("#E7F1FF", "#2563C9"), ("#FDEBDD", "#B4551A")]
AVATARS = ["#FF6B8B", "#7C5CFF", "#2EC4B6", "#FFB000", "#4F8CFF", "#FF8A4C"]

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
html, body, .stApp, button, input, textarea { font-family: 'Poppins', sans-serif !important; }
.stApp { background: #fff; color: #1F2340; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { max-width: 820px; padding-top: 1.6rem; }

.brand { display: flex; align-items: center; gap: 10px; margin: 0; }
.logo { font-size: 1.9rem; }
.name { font-size: 2rem; font-weight: 700; line-height: 1.2; background: linear-gradient(90deg, #FF6B8B, #7C5CFF);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.tagline { color: #6B7089; margin: 2px 0 1rem 0; }

.stTabs [role="tablist"] { gap: 6px; }
.stTabs [role="tab"] { border-radius: 999px; padding: 6px 16px; font-weight: 500; color: #555B73; }
.stTabs [aria-selected="true"] { color: #FF6B8B; }
.stTabs [data-baseweb="tab-highlight"] { background: #FF6B8B; }
button[kind="primary"], button[kind="primaryFormSubmit"] { background: linear-gradient(90deg, #FF6B8B, #7C5CFF);
  border: 0; color: #fff; border-radius: 999px; font-weight: 600; padding: 0.4rem 1.4rem; }
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover { filter: brightness(1.07); color: #fff; }
button[kind="secondary"] { border-radius: 999px; border: 1px solid #E6E1FF; background: #fff; }
div[data-testid="stVerticalBlockBorderWrapper"] { border: 1px solid #EEE9FF; border-radius: 18px;
  box-shadow: 0 4px 18px rgba(124, 92, 255, .06); }
input, textarea { border-radius: 12px !important; }

.item { display: flex; gap: 14px; align-items: flex-start; }
.thumb { position: relative; flex: 0 0 92px; width: 92px; height: 92px; border-radius: 14px; background: #F7F5FF; overflow: hidden; border: 1px solid #EEE9FF;
  display: flex; align-items: center; justify-content: center; font-size: 2rem; }
.thumb img { width: 100%; height: 100%; object-fit: contain; background: #fff; }
.thumb.photo { background-color: #fff; background-size: contain; background-repeat: no-repeat; background-position: center; }
.info { min-width: 0; overflow-wrap: anywhere; }
.ttl { font-weight: 600; line-height: 1.4; }
.price { font-weight: 700; font-size: 1.05rem; margin: 2px 0; }
.desc { color: #6B7089; font-size: .82rem; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.chip { padding: 2px 10px; border-radius: 999px; font-size: .74rem; font-weight: 500; background: #F1F2F6; color: #555B73; }
[class*="st-key-item_tags_"] [data-testid="stPopover"] button {
  min-height: 28px; padding: 2px 10px; border: 1px solid transparent; background: #FFF3D6; color: #B77900; }
[class*="st-key-item_tags_"] [data-testid="stPopover"] button:hover {
  border-color: #E5B652; background: #FFE9AF; }
[class*="st-key-item_tags_"] [data-testid="stPopover"] button p { font-size: .74rem; font-weight: 500; }
[class*="st-key-item_tags_"] [data-testid="stPopover"] button svg,
[class*="st-key-item_tags_"] [data-testid="stPopover"] button [data-testid="stIconMaterial"] { display: none; }
a.buy { display: inline-block; padding: 4px 16px; border-radius: 999px; font-size: .85rem; font-weight: 600;
  background: linear-gradient(90deg, #FF6B8B, #7C5CFF); color: #fff !important; text-decoration: none; }
.person { text-align: center; padding: 12px 6px 6px; border-radius: 16px; }
.person.sel { background: #F7F5FF; outline: 2px solid #7C5CFF33; }
.avatar { width: 64px; height: 64px; border-radius: 50%; margin: 0 auto 6px; color: #fff; font-weight: 700;
  font-size: 1.3rem; display: flex; align-items: center; justify-content: center; }
.avatar img, .profile-preview img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; display: block; }
.profile-preview { width: 112px; height: 112px; border-radius: 50%; overflow: hidden; border: 2px solid #EEE9FF; margin: 4px 0 10px; }
.pname { font-weight: 600; } .pcount { color: #6B7089; font-size: .8rem; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)
st.markdown(f"<style>{Path(__file__).with_name('mobile.css').read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True)

st.session_state.setdefault("token", None)


# ---------- helpers ----------
def logout():
    if st.session_state.token:  # end this login on the server too
        try:
            requests.post(API + "/logout", headers={"Authorization": f"Bearer {st.session_state.token}"}, timeout=3)
        except requests.RequestException:
            pass
    st.session_state.token = None
    for k in ("code", "skip_consent", "person", "auth_view"):
        st.session_state.pop(k, None)
    st.rerun()


def api(method, path, **kw):
    """Returns (status_code, json). Shows a friendly error if the server is down."""
    headers = {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}
    try:
        r = requests.request(method, API + path, headers=headers, timeout=75, **kw)
    except requests.RequestException:
        st.error("Can't reach the server. Is `uvicorn main:app --reload` running?")
        return None, None
    if r.status_code == 401 and st.session_state.token:
        logout()
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, None


def problem(data, fallback="Something went wrong."):
    detail = data.get("detail", fallback) if isinstance(data, dict) else fallback
    if isinstance(detail, list):  # validation errors: show the plain messages
        detail = "; ".join(str(d.get("msg", "")) for d in detail)
    return detail


def live(seconds=15):
    """Re-runs the decorated function on a timer (Streamlit 1.37+), so screens stay fresh."""
    def wrap(fn):
        frag = getattr(st, "fragment", None)
        return frag(run_every=seconds)(fn) if frag else fn
    return wrap


def menu(where, label):
    return where.popover(label, use_container_width=True) if hasattr(where, "popover") else where.expander(label)


def chip(text, i=None):
    style = f' style="background:{PASTELS[i % len(PASTELS)][0]};color:{PASTELS[i % len(PASTELS)][1]}"' if i is not None else ""
    return f'<span class="chip"{style}>{html.escape(text)}</span>'


def profile_photo_crop(key, label="Profile photo (optional)"):
    upload = st.file_uploader(label, type=["jpg", "jpeg", "png", "webp"], key=f"{key}_upload",
                              help="Choose a square photo, or adjust its crop and position below.")
    if not upload:
        return ""
    raw = upload.getvalue()
    if len(raw) > 5_000_000:
        st.error("Choose an image smaller than 5 MB.")
        return ""
    try:
        opened = Image.open(io.BytesIO(raw))
        image_format = opened.format
        image = ImageOps.exif_transpose(opened)
        if image_format not in {"JPEG", "PNG", "WEBP"} or image.width * image.height > 25_000_000:
            st.error("Choose a JPEG, PNG, or WebP image with fewer than 25 megapixels.")
            return ""
        image.load()
    except Exception:
        st.error("That image could not be opened. Choose a JPEG, PNG, or WebP photo.")
        return ""
    zoom = st.slider("Zoom", 1.0, 3.0, 1.0, 0.05, key=f"{key}_zoom")
    horizontal, vertical = st.columns(2)
    x_pos = horizontal.slider("Move left / right", 0, 100, 50, key=f"{key}_x")
    y_pos = vertical.slider("Move up / down", 0, 100, 50, key=f"{key}_y")
    side = min(image.size) / zoom
    left = round((image.width - side) * x_pos / 100)
    top = round((image.height - side) * y_pos / 100)
    crop = image.crop((left, top, left + round(side), top + round(side))).resize((256, 256), Image.Resampling.LANCZOS).convert("RGB")
    buf = io.BytesIO()
    crop.save(buf, format="JPEG", quality=86, optimize=True)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    st.markdown(f'<div class="profile-preview"><img src="data:image/jpeg;base64,{encoded}" alt="Profile photo crop preview"></div>',
                unsafe_allow_html=True)
    st.caption("Drag the sliders to frame the part you want inside the circle.")
    return encoded


def profile_circle(encoded, name, css_class="avatar"):
    if encoded:
        contents = f'<img src="data:image/jpeg;base64,{encoded}" alt="{html.escape(name)} profile photo">'
    else:
        contents = html.escape((name or "?")[:1].upper())
    return f'<div class="{css_class}">{contents}</div>'


# ---------- items ----------
def item_card(i):
    cat = i["category"] if i["category"] in EMOJI else "Other"
    img = i.get("image_url") or ""
    local = photo(img, i["url"]) if img.startswith("https://") else ""  # our own small copy: stores can't block it
    if local:
        thumb = f'<div class="thumb"><img src="{local}" alt=""></div>'
    elif img.startswith("https://"):  # fall back to the store's own link; a failed load leaves a plain tile
        safe = quote(img, safe=":/?&=%#@!$*+,;~-._")
        thumb = f'<style>.th{i["id"]}{{background-image:url("{safe}")}}</style><div class="thumb photo th{i["id"]}"></div>'
    else:
        thumb = f'<div class="thumb"><span>{EMOJI[cat]}</span></div>'
    price = f'<div class="price">${i["price"]:,.2f}</div>' if i["price"] is not None else ""
    desc = f'<div class="desc">{html.escape(i["description"][:200])}</div>' if i["description"] else ""
    body = f'<div class="info"><div class="ttl">{html.escape(i["title"])}</div>{price}{desc}</div>'
    url = i["url"] if i["url"].startswith(("http://", "https://")) else ""
    buy = f'<a class="buy" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">Buy ↗</a>' if url else ""
    return thumb, body, buy


def priority_points(i, ctx):
    with st.popover(f"🔥 {i['score']}", key=f"{ctx}score{i['id']}", help="Add or subtract priority points"):
        st.markdown(f"**Current score: 🔥 {i['score']}**")
        st.caption("Add or subtract points to change this item's priority. Scores stop at zero.")
        points = st.number_input("Points", min_value=1, max_value=100_000, value=1,
                                 step=1, key=f"{ctx}pts{i['id']}")
        add_col, subtract_col = st.columns(2)
        add = add_col.button("＋ Add", key=f"{ctx}addpts{i['id']}", use_container_width=True)
        subtract = subtract_col.button("− Subtract", key=f"{ctx}subpts{i['id']}",
                                       disabled=i["score"] == 0, use_container_width=True)
        if add or subtract:
            delta = int(points) if add else -int(points)
            code, data = api("POST", f"/items/{i['id']}/score-adjustment", json={"delta": delta})
            if code == 200:
                st.toast(f"Score updated to 🔥 {data['score']}")
                st.rerun()
            elif code:
                st.error(problem(data, "Couldn't update the score. Please try again."))
        st.caption("Choose Most wanted to see higher scores first.")


def render_items(items, mine, ctx, owner_id=None, sublists=None):
    if not items:
        st.info("Nothing here yet, or nothing matches your filters. ✨")
    warm((i["image_url"], i["url"]) for i in items if (i.get("image_url") or "").startswith("https://"))
    for i in items:
        thumb, body, buy = item_card(i)
        with st.container(border=True, key=f"item_card_{ctx}_{i['id']}"):
            left, right = st.columns([5, 1.6])
            with left.container(horizontal=True, wrap=False, gap="small", key=f"item_body_{ctx}_{i['id']}"):
                st.markdown(thumb, unsafe_allow_html=True, width="content")
                with st.container():
                    st.markdown(body, unsafe_allow_html=True)
                    with st.container(horizontal=True, gap="xxsmall", vertical_alignment="center",
                                      key=f"item_tags_{ctx}_{i['id']}"):
                        cat = i["category"] if i["category"] in EMOJI else "Other"
                        st.markdown(chip(cat, CATS.index(cat)), unsafe_allow_html=True, width="content")
                        if i["store"]:
                            st.markdown(chip(i["store"]), unsafe_allow_html=True, width="content")
                        if mine:
                            priority_points(i, ctx)
                        else:
                            st.markdown(chip(f"🔥 {i['score']}", 3), unsafe_allow_html=True, width="content")
                        if i["private"]:
                            st.markdown(chip("🔒 Only you", 0), unsafe_allow_html=True, width="content")
                        if i.get("gift_status") in ("claimed", "purchased"):
                            label = "🎁 Purchased" if i["gift_status"] == "purchased" else "🎁 Claimed"
                            st.markdown(chip(label, 2), unsafe_allow_html=True, width="content")
            if buy:
                right.markdown(buy, unsafe_allow_html=True)
            if mine:
                with menu(right, "⋯ Edit"):
                    now = st.toggle("🔒 Private", value=i["private"], key=f"{ctx}p{i['id']}", help="Hide from everyone you're connected with")
                    if now != i["private"]:
                        api("PATCH", f"/items/{i['id']}/private", json={"private": now})
                        st.rerun()
                    cat = st.selectbox("Category", CATS, index=CATS.index(i["category"]) if i["category"] in CATS else len(CATS) - 1,
                                       key=f"{ctx}c{i['id']}")
                    if cat != i["category"]:
                        api("PATCH", f"/items/{i['id']}/category", json={"category": cat})
                        st.rerun()
                    if st.button("🗑 Remove", key=f"{ctx}d{i['id']}"):
                        api("DELETE", f"/items/{i['id']}")
                        st.rerun()
            elif owner_id is not None:
                if i.get("gift_status", "available") == "available":
                    if right.button("🎁 Claim", key=f"{ctx}claim{i['id']}", use_container_width=True):
                        code, data = api("POST", f"/people/{owner_id}/items/{i['id']}/claim")
                        if code == 200:
                            st.rerun()
                        elif code:
                            st.error(problem(data))
                elif i.get("claimed_by_me"):
                    if i["gift_status"] == "claimed":
                        if right.button("Mark purchased", key=f"{ctx}bought{i['id']}", use_container_width=True):
                            api("PATCH", f"/people/{owner_id}/items/{i['id']}/claim", json={"purchased": True})
                            st.rerun()
                    else:
                        right.caption("You marked this purchased")
                        if right.button("Undo purchase", key=f"{ctx}undo{i['id']}", use_container_width=True):
                            api("PATCH", f"/people/{owner_id}/items/{i['id']}/claim", json={"purchased": False})
                            st.rerun()
                    if right.button("Release claim", key=f"{ctx}release{i['id']}"):
                        api("DELETE", f"/people/{owner_id}/items/{i['id']}/claim")
                        st.rerun()
                else:
                    right.caption("Purchased by another gifter" if i["gift_status"] == "purchased" else "Claimed by another gifter")
                if sublists:
                    selected = right.selectbox("Add to your private gift list", sublists,
                                               format_func=lambda x: x["title"], key=f"{ctx}sl{i['id']}")
                    if right.button("＋ Save to list", key=f"{ctx}sli{i['id']}", use_container_width=True):
                        code, data = api("POST", f"/sublists/{selected['id']}/items", json={"item_id": i["id"]})
                        if code == 200:
                            st.toast(f"Saved to {selected['title']}")
                        elif code:
                            st.error(problem(data))


def filter_and_sort(items, ctx):
    stores = sorted({i["store"] for i in items if i["store"]})
    cats = sorted({i["category"] for i in items})
    with st.container(key=f"list_tools_{ctx}"):
        a, b, c = st.columns([3, 2, 1.4], gap="small")
    q = a.text_input("Search", key=f"{ctx}q", placeholder="🔍 Search this list", label_visibility="collapsed").strip().lower()
    sort = b.selectbox("Sort", SORTS, key=f"{ctx}s", label_visibility="collapsed")
    with menu(c, "⚙ Filters"):
        c_sel = st.multiselect("Category", cats, key=f"{ctx}cat")
        s_sel = st.multiselect("Store", stores, key=f"{ctx}sto")
        lo_col, hi_col = st.columns(2)
        lo = lo_col.number_input("Price from ($)", min_value=0.0, step=5.0, key=f"{ctx}lo")
        hi = hi_col.number_input("Up to ($, 0 = any)", min_value=0.0, step=5.0, key=f"{ctx}hi")
        src = st.selectbox("Source", ["All", "Spotted while browsing", "Added by hand"], key=f"{ctx}src")
        top = st.checkbox("Most wanted only (🔥 4 or more)", key=f"{ctx}top")

    def price_ok(p):
        return (not lo and not hi) or (p is not None and p >= lo and (not hi or p <= hi))

    out = [i for i in items
           if (not q or q in f"{i['title']} {i['description']} {i['store']}".lower())
           and (not c_sel or i["category"] in c_sel) and (not s_sel or i["store"] in s_sel)
           and (src == "All" or (src.startswith("Spotted") == (i["source"] == "auto")))
           and (not top or i["score"] >= 4) and price_ok(i["price"])]
    if sort == "Price: low to high":
        out.sort(key=lambda i: (i["price"] is None, i["price"] or 0))
    elif sort == "Price: high to low":
        out.sort(key=lambda i: (i["price"] is None, -(i["price"] or 0)))
    elif sort == "Newest first":
        out.sort(key=lambda i: i["added"], reverse=True)
    elif sort == "A to Z":
        out.sort(key=lambda i: i["title"].lower())
    if len(out) != len(items):
        st.caption(f"Showing {len(out)} of {len(items)} items")
    return out


@live(15)
def person_list(uid):
    code, items = api("GET", f"/people/{uid}/items")
    if code == 200:
        list_code, sublists = api("GET", f"/people/{uid}/sublists")
        render_items(filter_and_sort(items, f"u{uid}"), False, f"u{uid}", uid,
                     sublists if list_code == 200 else [])


# ---------- screens ----------
def brand(tagline):
    st.markdown('<div class="brand"><span class="logo">🎁</span><span class="name">Thinking of You</span></div>'
                f'<p class="tagline">{tagline}</p>', unsafe_allow_html=True)


def auth_screen():
    if st.button("← Back to home", key="auth_back"):
        st.session_state.pop("auth_view", None)
        st.rerun()
    brand("Gifts people actually want.")
    default_tab = "Sign up" if st.session_state.get("auth_view") == "signup" else "Log in"
    login_tab, signup_tab = st.tabs(["Log in", "Sign up"], default=default_tab)
    with login_tab:
        with st.form("login"):
            email = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", type="primary", use_container_width=True):
                code, data = api("POST", "/login", json={"email": email, "password": pw})
                if code == 200:
                    st.session_state.token = data["token"]
                    st.rerun()
                elif code:
                    st.error(problem(data))
    with signup_tab:
        signup_photo = profile_photo_crop("signup_photo", "Add a profile photo (optional)")
        with st.form("signup"):
            name = st.text_input("Your name")
            email = st.text_input("Email", key="su_email")
            pw = st.text_input("Password (at least 8 characters)", type="password", key="su_pw")
            age = st.checkbox("I'm 13 or older")
            if st.form_submit_button("Create account", type="primary", use_container_width=True):
                if not (name and email and pw):
                    st.warning("Please fill in every field.")
                elif not age:
                    st.warning("You need to be 13 or older to sign up.")
                else:
                    code, data = api("POST", "/register", json={"email": email, "name": name, "password": pw,
                                                                "age_confirmed": True, "profile_photo": signup_photo})
                    if code == 200:
                        st.session_state.token = data["token"]
                        st.rerun()
                    elif code:
                        st.error(problem(data))


def consent_screen(name):
    brand(f"Before we start, {html.escape(name)}")
    st.markdown("""
- 🛍️ With the browser extension, we note the **products** you view or add to your cart on a few shopping sites. Nothing else, and never your general browsing.
- 👥 **Only your item list** is shared, and only with the people you connect with. They never see your browsing history.
- 🔒 You can mark any item **private**, remove anything, pause tracking, or delete your account and data whenever you like.
- ✋ Nothing is tracked until you say yes below.
""")
    agree = st.checkbox("I understand and want to turn on tracking")
    a, b, c = st.columns([1, 2, 1])
    if a.button("Start", type="primary", disabled=not agree, use_container_width=True):
        api("POST", "/consent")
        st.rerun()
    if b.button("Not now, I'll add items by hand", use_container_width=True):
        st.session_state.skip_consent = True
        st.rerun()
    if c.button("Log out", use_container_width=True):
        logout()


def connect_box(expanded):
    with st.expander("➕ Connect with someone", expanded=expanded):
        left, right = st.columns(2)
        with left:
            st.markdown("**Invite someone**")
            label = st.selectbox("They are my…", LABELS, index=3, key="inv_label")
            if st.button("Create invite code", type="primary", use_container_width=True):
                code, data = api("POST", "/invites", json={"label": label})
                if code == 200:
                    st.session_state.code = data["code"]
            if st.session_state.get("code"):
                st.code(st.session_state.code)
                st.caption("Send this to them. It works once and expires in 7 days.")
        with right:
            st.markdown("**Got a code?**")
            entered = st.text_input("Code", placeholder="e.g. A1B2C3", label_visibility="collapsed")
            if st.button("Connect", use_container_width=True):
                code, data = api("POST", "/invites/accept", json={"code": entered.strip()})
                if code == 200:
                    st.session_state.person = None
                    st.toast(f"Connected with {data['name']} 🎉")
                    st.rerun()
                elif code:
                    st.error(problem(data))


def people_tab():
    code, conns = api("GET", "/connections")
    if code != 200:
        return
    if not conns:
        st.markdown("### Your people")
        st.info("Nobody here yet. Invite a partner, family member, or friend to see each other's wishlists. 🎁")
        connect_box(True)
        return
    ids = [c["user_id"] for c in conns]
    if st.session_state.get("person") not in ids:
        st.session_state.person = ids[0]
    with st.container(key="people_grid"):
        for r in range(0, len(conns), 3):
            for col, c in zip(st.columns(3, gap="small"), conns[r:r + 3]):
                sel = c["user_id"] == st.session_state.person
                n = f"{c['item_count']} item" + ("" if c["item_count"] == 1 else "s")
                photo_html = profile_circle(c.get("profile_photo", ""), c["name"])
                if not c.get("profile_photo"):
                    photo_html = photo_html.replace('class="avatar"',
                        f'class="avatar" style="background:{AVATARS[c["user_id"] % len(AVATARS)]}"')
                col.markdown(f'<div class="person{" sel" if sel else ""}">{photo_html}'
                             f'<div class="pname">{html.escape(c["name"])}</div>'
                             f'{chip(c["label"], c["user_id"])}<div class="pcount">{n}</div></div>', unsafe_allow_html=True)
                if col.button("Viewing" if sel else "Open", key=f"open{c['user_id']}", disabled=sel, use_container_width=True):
                    st.session_state.person = c["user_id"]
                    st.rerun()
    cur = next(c for c in conns if c["user_id"] == st.session_state.person)
    st.markdown(f"### {html.escape(cur['name'])}'s wishlist")
    sl_code, sublists = api("GET", f"/people/{cur['user_id']}/sublists")
    if sl_code == 200:
        with st.expander(f"📝 Your private gift lists for {cur['name']}"):
            st.caption("Only you can see these lists. The list owner will not see which items you save here.")
            with st.form(f"new_sublist_{cur['user_id']}", clear_on_submit=True):
                sublist_title = st.text_input("New list name", placeholder="Birthday ideas")
                if st.form_submit_button("Create private list", type="primary", use_container_width=True):
                    code, data = api("POST", f"/people/{cur['user_id']}/sublists", json={"title": sublist_title})
                    if code == 200:
                        st.rerun()
                    elif code:
                        st.error(problem(data))
            if not sublists:
                st.caption("Examples: birthday ideas, small spontaneous gifts, or holiday gifts.")
            for sl in sublists:
                st.markdown(f"**{html.escape(sl['title'])}** · {len(sl['items'])} items")
                for saved in sl["items"]:
                    with st.container(horizontal=True, wrap=False, vertical_alignment="center",
                                      key=f"saved_gift_{sl['id']}_{saved['id']}"):
                        st.caption(saved["title"])
                        if st.button("Remove", key=f"remove_sl_{sl['id']}_{saved['id']}"):
                            api("DELETE", f"/sublists/{sl['id']}/items/{saved['id']}")
                            st.rerun()
                if st.button(f"Delete {sl['title']}", key=f"delete_sl_{sl['id']}"):
                    api("DELETE", f"/sublists/{sl['id']}")
                    st.rerun()
    person_list(cur["user_id"])
    with st.expander("Manage this connection"):
        new = st.text_input("What you call them", value=cur["label"], max_chars=20, key=f"lab{cur['id']}")
        if st.button("Save", key=f"savelab{cur['id']}") and new.strip() and new.strip() != cur["label"]:
            api("PATCH", f"/connections/{cur['id']}", json={"label": new.strip()})
            st.rerun()
        if st.checkbox(f"Disconnect from {cur['name']}", key=f"dis{cur['id']}") and st.button("Disconnect", key=f"disb{cur['id']}"):
            api("DELETE", f"/connections/{cur['id']}")
            st.session_state.person = None
            st.rerun()
    connect_box(False)


def settings_tab(me):
    st.markdown("### Profile")
    if me.get("profile_photo"):
        st.markdown(profile_circle(me["profile_photo"], me["name"], "profile-preview"), unsafe_allow_html=True)
    else:
        st.caption("Add a photo so your connected people can recognize you.")
    new_photo = profile_photo_crop("settings_photo", "Choose a profile photo")
    photo_col, remove_col = st.columns([1, 1])
    if photo_col.button("Save profile photo", type="primary", disabled=not bool(new_photo), use_container_width=True):
        code, data = api("PUT", "/profile/photo", json={"photo": new_photo})
        if code == 200:
            st.toast("Profile photo updated")
            st.rerun()
        elif code:
            st.error(problem(data))
    if remove_col.button("Remove photo", disabled=not bool(me.get("profile_photo")), use_container_width=True):
        code, data = api("DELETE", "/profile/photo")
        if code == 200:
            st.toast("Profile photo removed")
            st.rerun()
        elif code:
            st.error(problem(data))
    st.caption("Anyone connected to you can see your profile photo.")
    st.markdown("### Tracking and privacy")
    if me["consented"]:
        tracking = st.toggle("Allow product tracking in the app and extension", value=me["tracking_on"])
        if tracking != me["tracking_on"]:
            api("PATCH", "/tracking", json={"on": tracking})
            st.rerun()
        st.caption("This is one shared setting. When enabled, the extension can save product views and cart actions on supported stores.")
    else:
        st.info("Tracking is not enabled. The extension cannot save shopping activity until you consent here.")
        if st.button("Turn on tracking", type="primary"):
            api("POST", "/consent")
            st.rerun()
    st.caption("Only your item list is shared, never your browsing history. Private items are never shared.")
    with st.expander("🔌 Connect the browser extension"):
        st.caption("Install the Thinking of You extension, open its toolbar button, and sign in with this account. The tracking switch above controls both the app and extension.")
    with st.expander("🗑 Delete my account and data"):
        st.warning("This permanently deletes your account and every item on your list, and removes your connections. It can't be undone.")
        pw = st.text_input("Confirm your password", type="password", key="del_pw")
        sure = st.checkbox("Yes, delete everything", key="del_sure")
        if st.button("Delete my account", disabled=not sure):
            code, data = api("DELETE", "/account", json={"password": pw})
            if code == 200:
                logout()
            elif code:
                st.error(problem(data))


def main_app():
    code, me = api("GET", "/me")
    if code != 200:
        return
    if not me["consented"] and not st.session_state.get("skip_consent"):
        consent_screen(me["name"])
        return
    with st.container(key="app_header"):
        brand(f"Hi {html.escape(me['name'])} 👋")
        with st.container(horizontal=True, horizontal_alignment="right", gap="small", key="app_header_actions"):
            st.button("🔄", help="Refresh", key="header_refresh")  # any button click re-runs the page
            if st.button("Log out", key="header_logout"):
                logout()

    with st.container(key="app_navigation"):
        t_people, t_mine, t_add, t_set = st.tabs(["🏠 People", "🛍️ My list", "➕ Add item", "⚙️ Settings"])
    with t_people:
        people_tab()
    with t_mine:
        st.markdown("### Your list")
        st.caption("Most-wanted items float to the top. Use ⋯ Edit on any card to make it private or change its category. Click on the 🔥 to add or subtracts priority points manually.")
        code, items = api("GET", "/items/me")
        if code == 200:
            render_items(filter_and_sort(items, "me"), True, "me")
    with t_add:
        st.markdown("### Add something you love")
        with st.expander("📱 Quick add from a product link"):
            st.caption("On your phone, copy a product link, paste it here, and fetch its title, price, and photo. You can review everything before saving.")
            quick_url = st.text_input("Product link", key="quick_product_url", placeholder="https://…")
            if st.button("Fetch product details", key="fetch_product_details"):
                code, data = api("POST", "/items/preview", json={"url": quick_url.strip()})
                if code == 200:
                    st.session_state.new_title = data.get("title", "")
                    st.session_state.new_description = data.get("description", "")
                    st.session_state.new_price = data.get("price") or 0.0
                    st.session_state.new_url = quick_url.strip()
                    st.session_state.new_image = data.get("image_url", "")
                    st.toast("Details loaded. Review them below before adding.")
                    st.rerun()
                elif code:
                    st.error(problem(data, "Couldn't read that link. You can still fill in the item details below."))
        with st.form("add", clear_on_submit=True):
            title = st.text_input("What is it?", key="new_title")
            desc = st.text_area("Description (optional)", height=90, key="new_description")
            price = st.number_input("Price ($, leave 0 if unknown)", min_value=0.0, step=1.0, format="%.2f", key="new_price")
            url = st.text_input("Link to buy it (optional)", key="new_url")
            image = st.text_input("Picture link (optional, must start with https://)", key="new_image")
            category = st.selectbox("Category", ["Auto-detect"] + CATS, key="new_category")
            private = st.checkbox("🔒 Keep private (hide from everyone I'm connected with)", key="new_private")
            if st.form_submit_button("Add to my list", type="primary", use_container_width=True):
                if not title.strip():
                    st.warning("Give it a name first.")
                else:
                    code, data = api("POST", "/items", json={
                        "title": title.strip(), "description": desc.strip(), "price": price or None,
                        "url": url.strip(), "image_url": image.strip(), "private": private,
                        "category": "" if category == "Auto-detect" else category})
                    if code == 200:
                        st.toast("Added to your list 🎁")
                    elif code:
                        st.error(problem(data))
    with t_set:
        settings_tab(me)


# ---------- routing ----------
if st.session_state.token or st.session_state.get("auth_view"):
    if not st.session_state.get("awake"):  # wake the backend when a visitor needs an account
        with st.spinner("Waking up the server. The first visit can take up to a minute…"):
            try:
                requests.get(API + "/health", timeout=90)
                st.session_state.awake = True
            except requests.RequestException:
                pass
    if st.session_state.token:
        main_app()
    else:
        auth_screen()
else:
    welcome_screen()
