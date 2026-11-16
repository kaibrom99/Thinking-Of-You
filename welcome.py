"""The public welcome page. All sample wishlist content here is illustrative."""

import streamlit as st


STYLE = """
<style>
.stApp:has(.welcome-root) { background: #FFFCFA; }
.stApp:has(.welcome-root) .block-container { max-width: 1120px; padding-top: 1.7rem; padding-bottom: 1rem; }
.st-key-welcome_nav { padding-bottom: 18px; border-bottom: 1px solid #EEE7EC; justify-content: space-between; }
.welcome-wordmark { display: flex; align-items: center; gap: 10px; color: #302943;
  font-size: 1.2rem; font-weight: 600; letter-spacing: -.6px; }
.welcome-mark { display: inline-flex; width: 42px; height: 42px; align-items: center;
  justify-content: center; background: #FFF0F1; border-radius: 14px; font-size: 1.4rem; }
.st-key-welcome_hero { padding: 30px 0 20px; }
.welcome-eyebrow { color: #AC647E; font-size: .68rem; letter-spacing: 2.2px; font-weight: 600; margin-bottom: 21px; }
.welcome-title { font-size: clamp(2.8rem, 5vw, 3.8rem) !important; color: #302943 !important;
  font-weight: 600 !important; letter-spacing: -2.8px !important; line-height: 1.12 !important;
  padding: 0 !important; margin: 0 0 22px !important; }
.welcome-title .welcome-accent { background: linear-gradient(100deg, #F07897 5%, #956CE7 94%);
  background-clip: text; -webkit-background-clip: text; color: transparent; }
.welcome-description { max-width: 435px; font-size: .97rem; line-height: 1.9; color: #797181; margin: 0 0 22px; }
.st-key-welcome_actions { margin-top: 2px; }
.st-key-welcome_actions button { min-height: 48px; padding: 10px 24px !important; }
.st-key-welcome_actions button p { font-size: .84rem; }
.welcome-small { font-size: .7rem; color: #918591; margin: 12px 0 0; }
.welcome-small span { color: #A478BA; padding-right: 5px; }
.welcome-scene { height: 410px; position: relative; isolation: isolate; border-radius: 36px;
  background: radial-gradient(ellipse at 20% 80%, #FCE4E5 0, transparent 65%),
              radial-gradient(ellipse at 85% 15%, #E7DDFA 0, transparent 65%), #F5EDF5;
  overflow: hidden; }
.welcome-scene::before { content: ''; position: absolute; width: 325px; height: 325px;
  border: 1px solid #FFFFFFB0; border-radius: 50%; left: 56px; top: 40px; }
.welcome-scene::after { content: ''; position: absolute; width: 440px; height: 440px;
  border: 1px solid #FFFFFF80; border-radius: 50%; left: 0; top: -18px; z-index: -1; }
.welcome-spark { position: absolute; color: #BE91CD; font-size: 1.8rem; font-weight: 400; }
.welcome-spark.one { top: 24px; left: 30px; } .welcome-spark.two { right: 24px; bottom: 47px; }
.welcome-sample { position: absolute; left: 50%; top: 48px; transform: translateX(-50%) rotate(-3deg);
  width: 290px; background: #FFFFFFF5; border-radius: 23px; padding: 22px;
  box-shadow: 0 16px 36px #79567614; border: 1px solid #FFFFFF; }
.welcome-sample-head { display: flex; align-items: center; gap: 10px; margin-bottom: 19px; }
.welcome-sample-avatar { background: #EEE5FC; color: #9266BF; width: 39px; height: 39px;
  display: flex; align-items: center; justify-content: center; border-radius: 50%; font-size: .9rem; }
.welcome-sample-name { font-size: .83rem; font-weight: 600; color: #483B53; }
.welcome-sample-relation { font-size: .6rem; color: #A496AA; margin-top: 2px; }
.welcome-sample-title { font-size: .67rem; font-weight: 500; color: #9C83AF; margin-bottom: 12px; }
.welcome-product { display: flex; gap: 12px; align-items: center; padding: 11px 0; border-top: 1px solid #F4EFF5; }
.welcome-product-art { flex: 0 0 64px; height: 66px; border-radius: 13px; background: #F8EBEB;
  display: flex; align-items: center; justify-content: center; }
.welcome-product-art svg { width: 51px; height: 51px; }
.welcome-product-art.lilac { background: #F0EBF9; }
.welcome-product-name { font-size: .72rem; font-weight: 500; color: #55475E; }
.welcome-product-price { font-size: .66rem; color: #9C8DA5; margin-top: 3px; }
.welcome-product-score { display: inline-block; background: #FFF4DF; border-radius: 9px;
  padding: 2px 7px; font-size: .58rem; color: #B2853E; margin-top: 5px; }
.welcome-note { position: absolute; background: #FFFDFC; padding: 12px 17px; border-radius: 15px;
  box-shadow: 0 8px 24px #80617C12; display: flex; align-items: center; gap: 10px; }
.welcome-note.saved { right: 16px; top: 34px; transform: rotate(6deg); }
.welcome-note.surprise { left: 22px; bottom: 27px; transform: rotate(2deg); }
.welcome-note-icon { width: 30px; height: 30px; background: #FFEDF0; border-radius: 10px;
  display: flex; align-items: center; justify-content: center; color: #DA7D9B; font-size: 1rem; }
.welcome-note.surprise .welcome-note-icon { background: #EFE9FA; color: #9770C3; }
.welcome-note-title { font-size: .65rem; color: #6B526F; font-weight: 500; }
.welcome-note-subtitle { font-size: .56rem; color: #AC99AF; margin-top: 2px; }
.welcome-scene-label { text-align: center; font-size: .61rem; color: #A594AD; margin-top: 10px; }
.welcome-steps { border-top: 1px solid #EEE7EC; border-bottom: 1px solid #EEE7EC;
  display: grid; grid-template-columns: repeat(3, 1fr); padding: 25px 0; gap: 35px; margin-top: 8px; }
.welcome-step-top { display: flex; align-items: center; gap: 10px; margin-bottom: 9px; }
.welcome-step-number { font-size: .65rem; color: #B98BBD; background: #F5EDF7; padding: 4px 7px; border-radius: 7px; }
.welcome-step-title { font-size: .78rem; font-weight: 600; color: #5C4863; }
.welcome-step-copy { font-size: .72rem; color: #918393; line-height: 1.8; margin: 0; }
.welcome-footer { display: flex; justify-content: space-between; gap: 20px; align-items: center;
  padding-top: 19px; font-size: .65rem; color: #AC9AAD; }
.welcome-footer strong { font-weight: 500; color: #8B7098; }
@media (max-width: 640px) {
  .stApp:has(.welcome-root) .block-container { padding: 1rem 1rem max(2rem, env(safe-area-inset-bottom)); }
  .st-key-welcome_nav { padding-bottom: 14px; gap: 8px; }
  .welcome-wordmark { font-size: clamp(.85rem, 3.8vw, 1rem); gap: 7px; letter-spacing: -.4px; white-space: nowrap; }
  .welcome-mark { width: 30px; height: 32px; flex: 0 0 30px; font-size: 1.1rem; border-radius: 10px; }
  .st-key-welcome_nav button { padding: 6px 12px; }
  .st-key-welcome_nav button p { font-size: .77rem; white-space: nowrap; }
  .st-key-welcome_hero { padding: 16px 0 8px; }
  .welcome-title { letter-spacing: -1.8px !important; font-size: clamp(2.25rem, 10.5vw, 3rem) !important;
    line-height: 1.12 !important; margin-bottom: 18px !important; }
  .welcome-description { max-width: none; font-size: .91rem; line-height: 1.8; margin-bottom: 16px; }
  .welcome-eyebrow { font-size: .64rem; letter-spacing: 1.7px; margin-bottom: 14px; }
  .st-key-welcome_actions [data-testid="stHorizontalBlock"] { gap: 8px; }
  .st-key-welcome_actions button { width: 100%; min-height: 48px; }
  .welcome-small { font-size: .75rem; line-height: 1.7; color: #7D6F82; margin-top: 10px; }
  .welcome-scene { height: 370px; margin-top: 8px; border-radius: 25px; }
  .welcome-sample { box-sizing: border-box; top: 48px; width: min(290px, calc(100% - 40px)); padding: 19px;
    transform: translateX(-50%); border-radius: 20px; }
  .welcome-sample-head { gap: 8px; margin-bottom: 16px; }
  .welcome-sample-avatar { flex: 0 0 36px; width: 36px; height: 36px; }
  .welcome-sample-name { font-size: .85rem; }
  .welcome-sample-relation { font-size: .65rem; line-height: 1.6; color: #84718F; }
  .welcome-sample-title { font-size: .73rem; color: #81688E; }
  .welcome-product { gap: 10px; }
  .welcome-product-art { flex-basis: 54px; height: 58px; }
  .welcome-product-art svg { width: 45px; height: 45px; }
  .welcome-product-name { font-size: .73rem; line-height: 1.5; }
  .welcome-product-price { font-size: .7rem; color: #81718D; }
  .welcome-note { padding: 10px 12px; gap: 8px; }
  .welcome-note.saved { top: 13px; right: 12px; transform: rotate(3deg); }
  .welcome-note.surprise { left: 12px; right: 12px; bottom: 14px; transform: none; }
  .welcome-note-title { font-size: .72rem; line-height: 1.5; }
  .welcome-note-subtitle { font-size: .65rem; line-height: 1.5; color: #897390; }
  .welcome-scene-label { font-size: .7rem; color: #897390; }
  .welcome-steps { grid-template-columns: 1fr; gap: 22px; padding: 24px 0; margin-top: 0; }
  .welcome-step-title { font-size: .88rem; }
  .welcome-step-copy { font-size: .81rem; line-height: 1.8; color: #7D6F82; padding-left: 36px; }
  .welcome-footer { align-items: flex-start; flex-direction: column; gap: 8px; padding-top: 16px;
    font-size: .74rem; line-height: 1.8; color: #84718F; }
}
@media (max-width: 860px) {
  .st-key-welcome_hero [data-testid="stHorizontalBlock"] {
    flex-direction: column !important; align-items: stretch !important;
  }
  .st-key-welcome_hero [data-testid="stColumn"] {
    width: 100% !important; min-width: 100% !important; flex: 1 1 auto !important;
  }
  .st-key-welcome_actions button { width: 100%; white-space: normal; }
  .st-key-welcome_actions button p { overflow: visible; text-overflow: clip; white-space: normal; }
  .welcome-description { max-width: 550px; }
  .welcome-scene { margin-top: 14px; }
}
@media (prefers-reduced-motion: no-preference) {
  .welcome-scene, .welcome-title { animation: welcome-appear .55s ease-out both; }
  @keyframes welcome-appear { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
}
</style>
"""

ILLUSTRATION = """
<div class="welcome-scene" role="img" aria-label="Example wishlist: Maya's headphones and candle, with private birthday gift planning">
  <span class="welcome-spark one" aria-hidden="true">✧</span>
  <span class="welcome-spark two" aria-hidden="true">✧</span>
  <div class="welcome-sample">
    <div class="welcome-sample-head">
      <div class="welcome-sample-avatar">M</div>
      <div><div class="welcome-sample-name">Maya’s wishlist</div><div class="welcome-sample-relation">Your sister · Connected with you</div></div>
    </div>
    <div class="welcome-sample-title">A few things she’s been loving</div>
    <div class="welcome-product">
      <div class="welcome-product-art">
        <svg viewBox="0 0 64 64" fill="none" aria-hidden="true"><path d="M13 37V29a19 19 0 0 1 38 0v8" stroke="#BD7884" stroke-width="7" stroke-linecap="round"/><path d="M16 28v20M48 28v20" stroke="#DCA2AA" stroke-width="10" stroke-linecap="round"/><path d="M21 33v15M43 33v15" stroke="#EDC3C9" stroke-width="6" stroke-linecap="round"/><path d="M16 23a17 17 0 0 1 32 0" stroke="#F3D4D7" stroke-width="3" stroke-linecap="round"/></svg>
      </div>
      <div><div class="welcome-product-name">Her everyday headphones</div><div class="welcome-product-price">$49.00</div><div class="welcome-product-score">🔥 12</div></div>
    </div>
    <div class="welcome-product">
      <div class="welcome-product-art lilac">
        <svg viewBox="0 0 64 64" fill="none" aria-hidden="true"><path d="M32 8c8 7 7 12 0 14-7-2-8-7 0-14Z" fill="#EDB780"/><path d="M32 20v8" stroke="#8C6994" stroke-width="2"/><path d="M15 28h34v24c0 4-34 4-34 0V28Z" fill="#C7B2DD"/><ellipse cx="32" cy="28" rx="17" ry="5" fill="#E8DDF3"/><path d="M22 32v17" stroke="#DCCBEA" stroke-width="3" stroke-linecap="round"/><rect x="26" y="37" width="13" height="9" rx="2" fill="#F6EFFA"/></svg>
      </div>
      <div><div class="welcome-product-name">A cozy little candle</div><div class="welcome-product-price">$18.00</div><div class="welcome-product-score">🔥 8</div></div>
    </div>
  </div>
  <div class="welcome-note saved"><div class="welcome-note-icon">♡</div><div><div class="welcome-note-title">Birthday ideas</div><div class="welcome-note-subtitle">A little list, just for you</div></div></div>
  <div class="welcome-note surprise"><div class="welcome-note-icon">🎁</div><div><div class="welcome-note-title">The perfect gift. Still a surprise.</div><div class="welcome-note-subtitle">Your gift plans stay your secret.</div></div></div>
</div>
<div class="welcome-scene-label">A little peek at an example wishlist</div>
"""


def open_auth(view):
    st.session_state.auth_view = view
    st.rerun()


def welcome_screen():
    st.markdown(STYLE + '<div class="welcome-root"></div>', unsafe_allow_html=True)
    with st.container(horizontal=True, wrap=False, vertical_alignment="center", gap="small", key="welcome_nav"):
        st.markdown('<div class="welcome-wordmark"><span class="welcome-mark">🎁</span>Thinking of You</div>',
                    unsafe_allow_html=True)
        if st.button("Sign in ↗", key="welcome_signin"):
            open_auth("login")

    with st.container(key="welcome_hero"):
        words, scene = st.columns([1.08, 1], gap="large", vertical_alignment="center")
        with words:
            st.markdown('''<div class="welcome-eyebrow">FOR YOUR FAVORITE PEOPLE</div>
<h1 class="welcome-title">A little hint.<br><span class="welcome-accent">A lot of love.</span></h1>
<p class="welcome-description">Keep the things you love in one place. Connect with your favorite people, discover what’s on their minds, and turn everyday hints into thoughtful gifts.</p>''', unsafe_allow_html=True)
            with st.container(key="welcome_actions"):
                create, signin = st.columns([1.6, 1], gap="small")
                if create.button("Create your account →", type="primary", key="welcome_signup", use_container_width=True):
                    open_auth("signup")
                if signin.button("Sign in", key="welcome_login", use_container_width=True):
                    open_auth("login")
            st.markdown('<p class="welcome-small"><span>♡</span> For birthdays, big moments, and absolutely no reason.</p>',
                        unsafe_allow_html=True)
        scene.markdown(ILLUSTRATION, unsafe_allow_html=True)

    st.markdown('''<div class="welcome-steps">
<div><div class="welcome-step-top"><span class="welcome-step-number">01</span><span class="welcome-step-title">Save a little inspiration</span></div><p class="welcome-step-copy">Add things you love, or let the optional shopping extension spot ideas as you browse.</p></div>
<div><div class="welcome-step-top"><span class="welcome-step-number">02</span><span class="welcome-step-title">Bring your people closer</span></div><p class="welcome-step-copy">Connect with your partner, family, and friends. Give them a window into what you’d love.</p></div>
<div><div class="welcome-step-top"><span class="welcome-step-number">03</span><span class="welcome-step-title">Keep the surprise</span></div><p class="welcome-step-copy">Plan gifts and claim the perfect find, with your plans hidden from the person you’re celebrating.</p></div>
</div>
<div class="welcome-footer"><strong>Less guessing. More “you remembered.”</strong><span>Only your connected people see your shared list. You’re always in control.</span></div>''', unsafe_allow_html=True)
