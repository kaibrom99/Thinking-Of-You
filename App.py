"""Thinking of You - Streamlit front end.

Run (with the backend already running):  streamlit run app.py
"""
import html
import os

import requests
import streamlit as st

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
st.set_page_config(page_title="Thinking of You", page_icon="💌", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
html, body, .stApp, button, input, textarea { font-family: 'Poppins', sans-serif !important; }
.stApp { background: #fff; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { max-width: 760px; padding-top: 2rem; }

.brand { font-size: 2.3rem; font-weight: 700; margin: 0; line-height: 1.2;
  background: linear-gradient(90deg, #FF6B8B, #7C5CFF); -webkit-background-clip: text;
  -webkit-text-fill-color: transparent; }
.tagline { color: #8A8FA3; margin: 0 0 1.2rem 0; }

.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] { border-radius: 999px; padding: 6px 16px; font-weight: 500; }
.stTabs [aria-selected="true"] { color: #FF6B8B; }
.stTabs [data-baseweb="tab-highlight"] { background: #FF6B8B; }

button[kind="primary"], button[kind="primaryFormSubmit"] {
  background: linear-gradient(90deg, #FF6B8B, #7C5CFF); border: 0; color: #fff;
  border-radius: 999px; font-weight: 600; padding: 0.4rem 1.4rem; }
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover { filter: brightness(1.07); color: #fff; }
button[kind="secondary"] { border-radius: 999px; border: 1px solid #E6E1FF; background: #fff; }

div[data-testid="stVerticalBlockBorderWrapper"] { border: 1px solid #EEE9FF; border-radius: 18px;
  box-shadow: 0 4px 18px rgba(124, 92, 255, .07); }
input, textarea { border-radius: 12px !important; }

.row { display: flex; gap: 14px; align-items: flex-start; }
.rank { min-width: 38px; height: 38px; border-radius: 50%; background: #FFF0F3; color: #FF6B8B;
  font-weight: 700; display: flex; align-items: center; justify-content: center; }
.ttl { font-weight: 600; font-size: 1.05rem; color: #1F2340; }
.desc { color: #6B7089; font-size: .9rem; margin: 2px 0 6px 0; }
.meta { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 6px; }
.pill { padding: 2px 10px; border-radius: 999px; font-size: .78rem; font-weight: 500; }
.mint { background: #E3F8F5; color: #14907F; }
.sun  { background: #FFF3D6; color: #B77900; }
.vio  { background: #EFEBFF; color: #6142E0; }
.rose { background: #FFE9EE; color: #D6336C; }
a.buy { margin-left: auto; padding: 3px 14px; border-radius: 999px; font-size: .82rem; font-weight: 600;
  background: #7C5CFF; color: #fff !important; text-decoration: none; }
a.buy:hover { background: #6142E0; }
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
    for k in ("code", "skip_consent"):
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


def card(i, rank):
    url = i["url"] if i["url"].startswith(("http://", "https://")) else ""
    price = f'<span class="pill mint">${i["price"]:,.2f}</span>' if i["price"] is not None else ""
    src = "✍️ Added by hand" if i["source"] == "manual" else "👀 Spotted while browsing"
    buy = (f'<a class="buy" href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">Buy ↗</a>'
           if url else "")
    desc = f'<div class="desc">{html.escape(i["description"])}</div>' if i["description"] else ""
    lock = '<span class="pill rose">🔒 Only you</span>' if i.get("private") else ""
    return (f'<div class="row"><div class="rank">{rank}</div><div>'
            f'<div class="ttl">{html.escape(i["title"])}</div>{desc}'
            f'<div class="meta">{price}<span class="pill sun">🔥 {i["score"]}</span>'
            f'<span class="pill vio">{src}</span>{lock}</div></div></div>'), buy


def render_list(items, mine):
    if not items:
        st.info("Nothing here yet. ✨" if mine else "Nothing here yet. Check back soon! ✨")
    for n, i in enumerate(items, 1):
        body, buy = card(i, n)
        with st.container(border=True):
            left, right = st.columns([8, 2])
            left.markdown(body, unsafe_allow_html=True)
            if buy:
                right.markdown(buy, unsafe_allow_html=True)
            if mine:
                was = i.get("private", False)
                now = right.toggle("🔒 Private", value=was, key=f"priv{i['id']}", help="Hide this from your partner")
                if now != was:
                    api("PATCH", f"/items/{i['id']}/private", json={"private": now})
                    st.rerun()
            if mine and right.button("🗑 Remove", key=f"del{i['id']}"):
                api("DELETE", f"/items/{i['id']}")
                st.rerun()


def live(seconds=15):
    """Re-runs the decorated function on a timer (Streamlit 1.37+), so screens stay fresh."""
    def wrap(fn):
        frag = getattr(st, "fragment", None)
        return frag(run_every=seconds)(fn) if frag else fn
    return wrap


@live(15)
def partner_list():
    code, items = api("GET", "/items/partner")
    if code == 200:
        render_list(items, mine=False)


@live(4)
def wait_for_link():
    """While unlinked, quietly check whether the partner accepted; reload the whole app if so."""
    code, m = api("GET", "/me")
    if code == 200 and m["partner"]:
        st.rerun()


# ---------- logged-out screen ----------
def auth_screen():
    st.markdown('<p class="brand">💌 Thinking of You</p>', unsafe_allow_html=True)
    st.markdown('<p class="tagline">Know what they love. Surprise them anyway.</p>', unsafe_allow_html=True)
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
            if st.form_submit_button("Create account", type="primary"):
                if not (name and email and pw):
                    st.warning("Please fill in every field.")
                else:
                    code, data = api("POST", "/register", json={"email": email, "name": name, "password": pw})
                    if code == 200:
                        st.session_state.token = data["token"]
                        st.rerun()
                    elif code:
                        st.error(problem(data))


# ---------- consent ----------
def consent_screen(name):
    st.markdown('<p class="brand">💌 Thinking of You</p>', unsafe_allow_html=True)
    st.markdown(f"### Before we start, {html.escape(name)}")
    st.markdown("""
- 🛍️ With the browser extension, we note the **products** you view or add to your cart on a few shopping sites (Amazon, Etsy, Target, Walmart, eBay, Shein). Nothing else, and never your general browsing.
- 💞 **Only your item list** is shared, and only with the partner you link. They never see your browsing history.
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


# ---------- logged-in app ----------
def main_app():
    code, me = api("GET", "/me")
    if code != 200:
        return
    if not me["consented"] and not st.session_state.get("skip_consent"):
        consent_screen(me["name"])
        return
    head, refresh, out = st.columns([6, 1, 1.4])
    head.markdown('<p class="brand">💌 Thinking of You</p>', unsafe_allow_html=True)
    head.markdown(f'<p class="tagline">Hi {html.escape(me["name"])} 👋</p>', unsafe_allow_html=True)
    refresh.button("🔄", help="Refresh")  # any button click re-runs the page
    if out.button("Log out"):
        logout()

    t_them, t_mine, t_add, t_set = st.tabs(["💝 Their list", "🛍️ My list", "➕ Add item", "💞 Partner & settings"])

    with t_them:
        if me["partner"]:
            st.markdown(f"### {html.escape(me['partner'])}'s wishlist")
            partner_list()
        else:
            st.info("You're not linked yet. Head to **Partner & settings** to connect. 💞")

    with t_mine:
        st.markdown("### Your list")
        st.caption("Most-viewed items float to the top. Flip 🔒 Private to hide an item from your partner.")
        code, items = api("GET", "/items/me")
        if code == 200:
            render_list(items, mine=True)

    with t_add:
        st.markdown("### Add something you love")
        with st.form("add", clear_on_submit=True):
            title = st.text_input("What is it?")
            desc = st.text_area("Description (optional)", height=90)
            price = st.number_input("Price ($, leave 0 if unknown)", min_value=0.0, step=1.0, format="%.2f")
            url = st.text_input("Link to buy it (optional)")
            private = st.checkbox("🔒 Keep private (hide from my partner)")
            if st.form_submit_button("Add to my list", type="primary"):
                if not title.strip():
                    st.warning("Give it a name first.")
                else:
                    code, data = api("POST", "/items", json={
                        "title": title.strip(), "description": desc.strip(),
                        "price": price or None, "url": url.strip(), "private": private})
                    if code == 200:
                        st.toast("Added to your list 💌")
                    elif code:
                        st.error(problem(data))

    with t_set:
        st.markdown("### Your partner")
        if me["partner"]:
            st.success(f"💞 You're linked with {me['partner']}.")
            if st.checkbox("I want to unlink") and st.button("Unlink"):
                api("DELETE", "/partner")
                st.rerun()
        else:
            wait_for_link()
            a, b = st.columns(2)
            with a:
                st.markdown("**Invite them**")
                if st.button("Create invite code", type="primary"):
                    code, data = api("POST", "/partner/invite")
                    if code == 200:
                        st.session_state.code = data["code"]
                if st.session_state.get("code"):
                    st.code(st.session_state.code)
                    st.caption("Send this to your partner.")
            with b:
                st.markdown("**Got a code?**")
                entered = st.text_input("Partner's code", label_visibility="collapsed", placeholder="e.g. A1B2C3")
                if st.button("Link us"):
                    code, data = api("POST", "/partner/accept", json={"code": entered.strip()})
                    if code == 200:
                        st.session_state.pop("code", None)
                        st.rerun()
                    elif code:
                        st.error(problem(data))

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
        with st.expander("🗑 Delete my account and data"):
            st.warning("This permanently deletes your account and every item on your list, and unlinks your partner. It can't be undone.")
            pw = st.text_input("Confirm your password", type="password", key="del_pw")
            sure = st.checkbox("Yes, delete everything", key="del_sure")
            if st.button("Delete my account", disabled=not sure):
                code, data = api("DELETE", "/account", json={"password": pw})
                if code == 200:
                    logout()
                elif code:
                    st.error(problem(data))
        with st.expander("🔌 Browser extension token"):
            st.caption("Paste this into the extension so it can add items for you. Keep it private.")
            st.code(st.session_state.token)


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