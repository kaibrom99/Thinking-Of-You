"""Thinking of You - Streamlit front end.

Run (with the backend already running):  streamlit run app.py
"""
import html
import os
from urllib.parse import quote

import requests
import streamlit as st

from thumbs import photo, warm


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

.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] { border-radius: 999px; padding: 6px 16px; font-weight: 500; }
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
.thumb { position: relative; flex: 0 0 92px; height: 92px; border-radius: 14px; background: #F7F5FF; overflow: hidden; border: 1px solid #EEE9FF;
  display: flex; align-items: center; justify-content: center; font-size: 2rem; }
.thumb img { width: 100%; height: 100%; object-fit: contain; background: #fff; }
.thumb.photo { background-color: #fff; background-size: contain; background-repeat: no-repeat; background-position: center; }
.info { min-width: 0; }
.ttl { font-weight: 600; line-height: 1.3; }
.price { font-weight: 700; font-size: 1.05rem; margin: 2px 0; }
.desc { color: #6B7089; font-size: .82rem; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.chip { padding: 2px 10px; border-radius: 999px; font-size: .74rem; font-weight: 500; background: #F1F2F6; color: #555B73; }
a.buy { display: inline-block; padding: 4px 16px; border-radius: 999px; font-size: .85rem; font-weight: 600;
  background: linear-gradient(90deg, #FF6B8B, #7C5CFF); color: #fff !important; text-decoration: none; }
.person { text-align: center; padding: 12px 6px 6px; border-radius: 16px; }
.person.sel { background: #F7F5FF; outline: 2px solid #7C5CFF33; }
.avatar { width: 54px; height: 54px; border-radius: 50%; margin: 0 auto 6px; color: #fff; font-weight: 700;
  font-size: 1.3rem; display: flex; align-items: center; justify-content: center; }
.pname { font-weight: 600; } .pcount { color: #6B7089; font-size: .8rem; margin-top: 4px; }
@media (max-width: 640px) { .thumb { flex-basis: 72px; height: 72px; } .name { font-size: 1.6rem; } }
</style>
""", unsafe_allow_html=True)

st.session_state.setdefault("token", None)


# ---------- helpers ----------
def logout():
    if st.session_state.token:  # end this login on the server too
        try:
            requests.post(API + "/logout", headers={"Authorization": f"Bearer {st.session_state.token}"}, timeout=3)
        except requests.RequestException:
            pass
    st.session_state.token = None
    for k in ("code", "skip_consent", "person"):
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
    return where.popover(label) if hasattr(where, "popover") else where.expander(label)


def chip(text, i=None):
    style = f' style="background:{PASTELS[i % len(PASTELS)][0]};color:{PASTELS[i % len(PASTELS)][1]}"' if i is not None else ""
    return f'<span class="chip"{style}>{html.escape(text)}</span>'


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
    tags = chip(cat, CATS.index(cat)) + (chip(i["store"]) if i["store"] else "") + chip(f"🔥 {i['score']}", 3)
    if i["private"]:
        tags += chip("🔒 Only you", 0)
    body = (f'<div class="item">{thumb}<div class="info">'
            f'<div class="ttl">{html.escape(i["title"])}</div>{price}{desc}<div class="tags">{tags}</div></div></div>')
    url = i["url"] if i["url"].startswith(("http://", "https://")) else ""
    buy = f'<a class="buy" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">Buy ↗</a>' if url else ""
    return body, buy


def render_items(items, mine, ctx):
    if not items:
        st.info("Nothing here yet, or nothing matches your filters. ✨")
    warm((i["image_url"], i["url"]) for i in items if (i.get("image_url") or "").startswith("https://"))
    for i in items:
        body, buy = item_card(i)
        with st.container(border=True):
            left, right = st.columns([5, 1.6])
            left.markdown(body, unsafe_allow_html=True)
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


def filter_and_sort(items, ctx):
    stores = sorted({i["store"] for i in items if i["store"]})
    cats = sorted({i["category"] for i in items})
    a, b, c = st.columns([3, 2, 1.4])
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
        render_items(filter_and_sort(items, f"u{uid}"), False, f"u{uid}")


# ---------- screens ----------
def brand(tagline):
    st.markdown('<div class="brand"><span class="logo">🎁</span><span class="name">Thinking of You</span></div>'
                f'<p class="tagline">{tagline}</p>', unsafe_allow_html=True)


def auth_screen():
    brand("Gifts people actually want.")
    login_tab, signup_tab = st.tabs(["Log in", "Sign up"])
    with login_tab:
        with st.form("login"):
            email = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", type="primary"):
                code, data = api("POST", "/login", json={"email": email, "password": pw})
                if code == 200:
                    st.session_state.token = data["token"]
                    st.rerun()
                elif code:
                    st.error(problem(data))
    with signup_tab:
        with st.form("signup"):
            name = st.text_input("Your name")
            email = st.text_input("Email", key="su_email")
            pw = st.text_input("Password (at least 8 characters)", type="password", key="su_pw")
            age = st.checkbox("I'm 13 or older")
            if st.form_submit_button("Create account", type="primary"):
                if not (name and email and pw):
                    st.warning("Please fill in every field.")
                elif not age:
                    st.warning("You need to be 13 or older to sign up.")
                else:
                    code, data = api("POST", "/register", json={"email": email, "name": name, "password": pw,
                                                                "age_confirmed": True})
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
    if a.button("Start", type="primary", disabled=not agree):
        api("POST", "/consent")
        st.rerun()
    if b.button("Not now, I'll add items by hand"):
        st.session_state.skip_consent = True
        st.rerun()
    if c.button("Log out"):
        logout()


def connect_box(expanded):
    with st.expander("➕ Connect with someone", expanded=expanded):
        left, right = st.columns(2)
        with left:
            st.markdown("**Invite someone**")
            label = st.selectbox("They are my…", LABELS, index=3, key="inv_label")
            if st.button("Create invite code", type="primary"):
                code, data = api("POST", "/invites", json={"label": label})
                if code == 200:
                    st.session_state.code = data["code"]
            if st.session_state.get("code"):
                st.code(st.session_state.code)
                st.caption("Send this to them. It works once and expires in 7 days.")
        with right:
            st.markdown("**Got a code?**")
            entered = st.text_input("Code", placeholder="e.g. A1B2C3", label_visibility="collapsed")
            if st.button("Connect"):
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
    for r in range(0, len(conns), 3):
        for col, c in zip(st.columns(3), conns[r:r + 3]):
            sel = c["user_id"] == st.session_state.person
            n = f"{c['item_count']} item" + ("" if c["item_count"] == 1 else "s")
            col.markdown(f'<div class="person{" sel" if sel else ""}"><div class="avatar" style="background:{AVATARS[c["user_id"] % len(AVATARS)]}">'
                         f'{html.escape(c["name"][:1].upper())}</div><div class="pname">{html.escape(c["name"])}</div>'
                         f'{chip(c["label"], c["user_id"])}<div class="pcount">{n}</div></div>', unsafe_allow_html=True)
            if col.button("Viewing" if sel else "Open", key=f"open{c['user_id']}", disabled=sel, use_container_width=True):
                st.session_state.person = c["user_id"]
                st.rerun()
    cur = next(c for c in conns if c["user_id"] == st.session_state.person)
    st.markdown(f"### {html.escape(cur['name'])}'s wishlist")
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
    st.markdown("### Privacy")
    if me["consented"]:
        tracking = st.toggle("Track my shopping activity", value=me["tracking_on"])
        if tracking != me["tracking_on"]:
            api("PATCH", "/tracking", json={"on": tracking})
            st.rerun()
    else:
        st.info("Shopping tracking is off. Nothing from the extension is saved.")
        if st.button("Turn on tracking", type="primary"):
            api("POST", "/consent")
            st.rerun()
    st.caption("Only your item list is shared, never your browsing history. Private items are never shared.")
    with st.expander("🔌 Browser extension token"):
        st.caption("Paste this into the extension so it can add items for you. Keep it private.")
        st.code(st.session_state.token)
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
    head, refresh, out = st.columns([6, 1, 1.4])
    with head:
        brand(f"Hi {html.escape(me['name'])} 👋")
    refresh.button("🔄", help="Refresh")  # any button click re-runs the page
    if out.button("Log out"):
        logout()

    t_people, t_mine, t_add, t_set = st.tabs(["🏠 People", "🛍️ My list", "➕ Add item", "⚙️ Settings"])
    with t_people:
        people_tab()
    with t_mine:
        st.markdown("### Your list")
        st.caption("Most-wanted items float to the top. Use ⋯ Edit on any card to make it private or change its category.")
        code, items = api("GET", "/items/me")
        if code == 200:
            render_items(filter_and_sort(items, "me"), True, "me")
    with t_add:
        st.markdown("### Add something you love")
        with st.form("add", clear_on_submit=True):
            title = st.text_input("What is it?")
            desc = st.text_area("Description (optional)", height=90)
            price = st.number_input("Price ($, leave 0 if unknown)", min_value=0.0, step=1.0, format="%.2f")
            url = st.text_input("Link to buy it (optional)")
            image = st.text_input("Picture link (optional, must start with https://)")
            category = st.selectbox("Category", ["Auto-detect"] + CATS)
            private = st.checkbox("🔒 Keep private (hide from everyone I'm connected with)")
            if st.form_submit_button("Add to my list", type="primary"):
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


if not st.session_state.get("awake"):  # free servers sleep when idle; wake it once per visit
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