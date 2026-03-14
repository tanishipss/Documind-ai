"""
DocuMind AI — Login / Signup Page  (Full 3D)
File: login.py  (project root)
Run:  streamlit run login.py
"""

import re
import time
import streamlit as st
from frontend.auth_utils import (
    api_signup, api_login, is_logged_in, get_current_user, logout
)

st.set_page_config(
    page_title="DocuMind AI — Welcome",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Hide Streamlit chrome ────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stSidebar"],
[data-testid="collapsedControl"],
[data-testid="stStatusWidget"],
.stDeployButton { display: none !important; }

html, body, [class*="css"] {
    background: #040710 !important;
    overflow-x: hidden !important;
    margin: 0 !important; padding: 0 !important;
}
.block-container {
    padding: 0 !important; margin: 0 !important;
    max-width: 100vw !important; width: 100vw !important;
}
section.main > div { padding: 0 !important; }

/* Hide the native Streamlit form widgets — they are only used as a relay */
div[data-testid="stForm"] {
    position: fixed !important;
    top: -9999px !important;
    left: -9999px !important;
    opacity: 0 !important;
    pointer-events: none !important;
    height: 0 !important;
    overflow: hidden !important;
}
</style>
""", unsafe_allow_html=True)

# ── Session defaults ─────────────────────────────────────────────
for k, v in {
    "auth_tab":   "signin",
    "auth_token": None,
    "auth_user":  None,
    "login_err":  "",
    "signup_err": "",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


def validate_email(e):
    return bool(re.match(r"^[\w\.\+\-]+@[\w\-]+\.[a-z]{2,}$", e.lower()))


# ── Already logged in ────────────────────────────────────────────
if is_logged_in():
    user = get_current_user()
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap');
    html,body,[class*="css"]{{background:#040710!important;color:#e6edf3;
        font-family:'DM Sans',sans-serif;}}
    </style>
    <div style='text-align:center;padding:3rem 1rem;'>
        <div style='font-size:3rem;margin-bottom:1rem;'>✅</div>
        <div style='font-family:Syne,sans-serif;font-size:1.5rem;
                    font-weight:800;color:#e6edf3;margin-bottom:0.4rem;'>
            Already signed in!
        </div>
        <div style='font-size:0.88rem;color:#8b949e;'>
            Welcome back,
            <strong style='color:#388bfd;'>{user.get("name","")}</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button("🚀 Go to DocuMind", type="primary",
                     use_container_width=True, key="goto"):
            st.switch_page("pages/app.py")
        st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
        if st.button("🚪 Sign out", use_container_width=True, key="sout"):
            logout()
    st.stop()


# ── Pull error messages ───────────────────────────────────────────
login_err  = st.session_state.get("login_err",  "")
signup_err = st.session_state.get("signup_err", "")
tab        = st.session_state.get("auth_tab", "signin")

def js_esc(s):
    return s.replace("\\","\\\\").replace("'","\\'").replace('"','\\"')

LOGIN_ERR  = js_esc(login_err)
SIGNUP_ERR = js_esc(signup_err)

ACTIVE_SIGNIN = "active" if tab == "signin" else ""
ACTIVE_SIGNUP = "active" if tab == "signup" else ""
TAB_SI_CLASS  = "tab active" if tab == "signin" else "tab"
TAB_SU_CLASS  = "tab active" if tab == "signup" else "tab"

# ================================================================
# HIDDEN STREAMLIT FORMS — receive data relayed from JS via
# st.session_state keys written by the component postMessage handler
# ================================================================

# ── Sign In form (hidden off-screen via CSS above) ───────────────
with st.form("_signin_relay", clear_on_submit=True):
    si_email = st.text_input("si_email", key="relay_si_email")
    si_pw    = st.text_input("si_pw",    key="relay_si_pw", type="password")
    si_sub   = st.form_submit_button("signin")

if si_sub and si_email and si_pw:
    user, err = api_login(si_email, si_pw)
    if err:
        st.session_state["login_err"] = err
        st.session_state["auth_tab"]  = "signin"
        st.rerun()
    else:
        st.session_state["login_err"]  = ""
        st.session_state["signup_err"] = ""
        st.switch_page("pages/app.py")

# ── Sign Up form (hidden off-screen via CSS above) ───────────────
with st.form("_signup_relay", clear_on_submit=True):
    su_name  = st.text_input("su_name",  key="relay_su_name")
    su_email = st.text_input("su_email", key="relay_su_email")
    su_pw    = st.text_input("su_pw",    key="relay_su_pw",   type="password")
    su_sub   = st.form_submit_button("signup")

if su_sub and su_name and su_email and su_pw:
    user, err = api_signup(su_name, su_email, su_pw)
    if err:
        st.session_state["signup_err"] = err
        st.session_state["auth_tab"]   = "signup"
        st.rerun()
    else:
        st.session_state["login_err"]  = ""
        st.session_state["signup_err"] = ""
        st.switch_page("pages/app.py")

# ── Tab-switch relay ─────────────────────────────────────────────
with st.form("_tab_relay", clear_on_submit=True):
    tab_val = st.text_input("tab_val", key="relay_tab_val")
    tab_sub = st.form_submit_button("switchtab")

if tab_sub and tab_val in ("signin", "signup"):
    st.session_state["auth_tab"] = tab_val
    st.rerun()


# ================================================================
# 3-D FULL PAGE HTML
# ================================================================
import streamlit.components.v1 as components

components.html(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
:root{{
  --bg:#040710; --card:rgba(14,20,35,0.86); --border:rgba(56,139,253,0.2);
  --blue:#388bfd; --blue-d:#1f6feb; --green:#3fb950;
  --text:#e6edf3; --muted:#8b949e; --danger:#f85149;
  --inp:rgba(5,10,20,0.92);
}}
html,body{{
  width:100%;height:100vh;overflow:hidden;
  background:var(--bg);
  font-family:'DM Sans',sans-serif;
  color:var(--text);
}}
/* cursor */
#cur{{position:fixed;width:10px;height:10px;border-radius:50%;
  background:var(--blue);pointer-events:none;z-index:9999;
  transform:translate(-50%,-50%);
  box-shadow:0 0 10px var(--blue),0 0 25px rgba(56,139,253,0.4);
  transition:width .18s,height .18s;}}
#ring{{position:fixed;width:34px;height:34px;border-radius:50%;
  border:1.5px solid rgba(56,139,253,0.45);pointer-events:none;z-index:9998;
  transform:translate(-50%,-50%);transition:width .25s,height .25s;}}
/* canvas */
#cv{{position:fixed;inset:0;width:100%;height:100%;z-index:0;pointer-events:none;}}
/* particles */
.pt{{position:fixed;border-radius:50%;pointer-events:none;z-index:1;
  animation:rise linear infinite;opacity:0;}}
@keyframes rise{{
  0%{{transform:translateY(108vh) rotate(0deg);opacity:0;}}
  6%{{opacity:.9;}} 94%{{opacity:.4;}}
  100%{{transform:translateY(-8vh) rotate(540deg);opacity:0;}}
}}
/* page */
#page{{position:fixed;inset:0;display:flex;align-items:center;
  justify-content:center;z-index:10;perspective:1400px;}}
/* scene */
#scene{{width:430px;transform-style:preserve-3d;
  animation:enter .8s cubic-bezier(.16,1,.3,1) forwards;}}
@keyframes enter{{
  from{{opacity:0;transform:rotateX(16deg) rotateY(-8deg) translateY(55px) scale(.92);}}
  to  {{opacity:1;transform:rotateX(0)     rotateY(0)     translateY(0)    scale(1);}}
}}
/* card */
#card{{
  background:var(--card);border:1px solid var(--border);border-radius:22px;
  padding:2.2rem 2.4rem 1.8rem;
  backdrop-filter:blur(32px);-webkit-backdrop-filter:blur(32px);
  box-shadow:0 0 0 1px rgba(56,139,253,.07),
             0 32px 80px rgba(0,0,0,.6),
             0 6px 22px rgba(0,0,0,.4),
             inset 0 1px 0 rgba(255,255,255,.06);
  transform-style:preserve-3d;
  transition:transform .14s ease-out,box-shadow .14s ease-out;
  position:relative;overflow:hidden;
}}
#card::before{{content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.1),transparent);}}
/* glow spot */
#spot{{position:absolute;width:280px;height:280px;border-radius:50%;
  pointer-events:none;
  background:radial-gradient(circle,rgba(56,139,253,.11) 0%,transparent 70%);
  transform:translate(-50%,-50%);z-index:0;opacity:0;transition:opacity .3s;}}
/* brand */
.brand{{display:flex;align-items:center;gap:.8rem;
  justify-content:center;margin-bottom:1.6rem;position:relative;z-index:1;}}
.bicon{{width:42px;height:42px;background:linear-gradient(135deg,#1f6feb,#388bfd);
  border-radius:11px;display:flex;align-items:center;justify-content:center;
  font-size:1.3rem;box-shadow:0 5px 18px rgba(56,139,253,.42),
  inset 0 1px 0 rgba(255,255,255,.15);flex-shrink:0;}}
.bname{{font-family:'Syne',sans-serif;font-size:1.25rem;font-weight:800;
  color:var(--text);letter-spacing:-.02em;}}
.btag{{font-size:.6rem;color:var(--muted);text-transform:uppercase;
  letter-spacing:.1em;}}
/* tabs */
.tabs{{display:flex;background:rgba(0,0,0,.4);border:1px solid rgba(48,54,61,.6);
  border-radius:11px;padding:4px;gap:4px;margin-bottom:1.5rem;
  position:relative;z-index:1;}}
.tab{{flex:1;padding:.52rem;border:none;border-radius:8px;
  font-family:'DM Sans',sans-serif;font-size:.87rem;font-weight:600;
  cursor:pointer;transition:all .2s ease;color:var(--muted);background:transparent;}}
.tab.active{{background:linear-gradient(135deg,var(--blue-d),var(--blue));
  color:#fff;box-shadow:0 2px 12px rgba(56,139,253,.32);}}
.tab:not(.active):hover{{color:var(--text);background:rgba(48,54,61,.5);}}
/* panels */
.panel{{display:none;position:relative;z-index:1;}}
.panel.active{{display:block;}}
/* titles */
.ttl{{font-family:'Syne',sans-serif;font-size:1.5rem;font-weight:800;
  color:var(--text);letter-spacing:-.02em;margin-bottom:.2rem;}}
.sub{{font-size:.82rem;color:var(--muted);line-height:1.55;margin-bottom:.1rem;}}
/* divider */
.dv{{height:1px;background:linear-gradient(90deg,transparent,
  rgba(56,139,253,.38),rgba(48,54,61,.4),transparent);margin:.9rem 0 1.2rem;}}
/* field */
.field{{margin-bottom:.9rem;}}
.field label{{display:block;font-size:.7rem;font-weight:600;color:var(--muted);
  text-transform:uppercase;letter-spacing:.07em;margin-bottom:.3rem;}}
.field input{{width:100%;padding:.65rem .95rem;background:var(--inp);
  border:1px solid rgba(48,54,61,.85);border-radius:10px;color:var(--text);
  font-family:'DM Sans',sans-serif;font-size:.9rem;outline:none;
  transition:border-color .2s,box-shadow .2s;cursor:text;}}
.field input:focus{{border-color:var(--blue);
  box-shadow:0 0 0 3px rgba(56,139,253,.15);}}
.field input::placeholder{{color:rgba(139,148,158,.45);}}
/* pw wrap */
.pw{{position:relative;}}
.pw input{{padding-right:2.8rem;}}
.pwtg{{position:absolute;right:.8rem;top:50%;transform:translateY(-50%);
  background:none;border:none;cursor:pointer;color:var(--muted);
  font-size:.95rem;transition:color .15s;padding:0;}}
.pwtg:hover{{color:var(--text);}}
/* strength */
.sbar-w{{height:3px;background:rgba(48,54,61,.5);
  border-radius:2px;margin-top:5px;overflow:hidden;}}
.sbar{{height:100%;border-radius:2px;width:0;
  transition:width .3s,background .3s;}}
.slbl{{font-size:.67rem;margin-top:2px;font-weight:600;}}
/* submit */
.btn{{width:100%;padding:.72rem;
  background:linear-gradient(135deg,var(--blue-d),var(--blue));
  color:#fff;border:none;border-radius:11px;
  font-family:'DM Sans',sans-serif;font-size:.94rem;font-weight:600;
  cursor:pointer;margin-top:.5rem;
  box-shadow:0 4px 18px rgba(56,139,253,.3);
  transition:all .2s ease;letter-spacing:.01em;}}
.btn:hover{{transform:translateY(-2px);
  box-shadow:0 8px 28px rgba(56,139,253,.45);}}
.btn:active{{transform:translateY(0);}}
/* loading spinner on btn */
.btn.loading{{opacity:.7;cursor:not-allowed;}}
/* error */
.err{{background:rgba(61,26,26,.75);border:1px solid rgba(248,81,73,.4);
  border-radius:9px;padding:.55rem .85rem;font-size:.78rem;color:var(--danger);
  margin-bottom:.8rem;display:flex;align-items:center;gap:.35rem;}}
/* switch link */
.sw{{text-align:center;margin-top:.9rem;font-size:.78rem;color:var(--muted);}}
.sw a{{color:var(--blue);text-decoration:none;font-weight:500;cursor:pointer;}}
.sw a:hover{{text-decoration:underline;}}
/* terms */
.terms{{font-size:.68rem;color:#484f58;margin-top:.2rem;line-height:1.6;}}
/* pills */
.pills{{display:flex;justify-content:center;gap:.45rem;
  flex-wrap:wrap;margin-top:1.3rem;position:relative;z-index:1;}}
.pill{{padding:.22rem .65rem;background:rgba(14,20,35,.7);
  border:1px solid rgba(48,54,61,.4);border-radius:20px;
  font-size:.67rem;color:var(--muted);}}
/* overlay spinner */
#overlay{{display:none;position:fixed;inset:0;z-index:9999;
  background:rgba(4,7,16,.7);backdrop-filter:blur(4px);
  align-items:center;justify-content:center;flex-direction:column;gap:1rem;}}
#overlay.show{{display:flex;}}
.spin{{width:42px;height:42px;border:3px solid rgba(56,139,253,.2);
  border-top-color:#388bfd;border-radius:50%;animation:sp .7s linear infinite;}}
@keyframes sp{{to{{transform:rotate(360deg);}}}}
.spin-lbl{{color:#8b949e;font-size:.85rem;}}
</style>
</head>
<body>

<div id="cur"></div>
<div id="ring"></div>
<canvas id="cv"></canvas>
<div id="pt-wrap"></div>

<!-- Loading overlay shown while Streamlit processes -->
<div id="overlay">
  <div class="spin"></div>
  <div class="spin-lbl" id="spin-lbl">Signing in…</div>
</div>

<div id="page">
 <div id="scene">
  <div id="card">
   <div id="spot"></div>

   <!-- Brand -->
   <div class="brand">
    <div class="bicon">📘</div>
    <div>
     <div class="bname">DocuMind AI</div>
     <div class="btag">Smart Learning Platform</div>
    </div>
   </div>

   <!-- Tabs -->
   <div class="tabs">
    <button class="{TAB_SI_CLASS}" id="tsi"
            onclick="swTab('signin')">Sign In</button>
    <button class="{TAB_SU_CLASS}" id="tsu"
            onclick="swTab('signup')">Create Account</button>
   </div>

   <!-- SIGN IN -->
   <div class="panel {ACTIVE_SIGNIN}" id="psi">
    <div class="ttl">Welcome back 👋</div>
    <div class="sub">Sign in to continue your learning journey.</div>
    <div class="dv"></div>
    {"<div class='err'>⚠ " + LOGIN_ERR + "</div>" if LOGIN_ERR else ""}
    <div class="field">
     <label>Email Address</label>
     <input type="email" id="si-e" placeholder="you@example.com" required>
    </div>
    <div class="field">
     <label>Password</label>
     <div class="pw">
      <input type="password" id="si-p" placeholder="••••••••" required>
      <button type="button" class="pwtg" onclick="tpw('si-p',this)">👁</button>
     </div>
    </div>
    <button class="btn" id="si-btn" onclick="doSignin()">Sign In →</button>
    <div class="sw">Don't have an account?
     <a onclick="swTab('signup')">Create one free →</a>
    </div>
   </div>

   <!-- SIGN UP -->
   <div class="panel {ACTIVE_SIGNUP}" id="psu">
    <div class="ttl">Create account ✨</div>
    <div class="sub">Join DocuMind and start learning smarter.</div>
    <div class="dv"></div>
    {"<div class='err'>⚠ " + SIGNUP_ERR + "</div>" if SIGNUP_ERR else ""}
    <div class="field">
     <label>Your Name</label>
     <input type="text" id="su-n" placeholder="e.g. Tanisha" required>
    </div>
    <div class="field">
     <label>Email Address</label>
     <input type="email" id="su-e" placeholder="you@example.com" required>
    </div>
    <div class="field">
     <label>Password</label>
     <div class="pw">
      <input type="password" id="su-p" placeholder="Min 8 characters"
             required oninput="chkStr(this.value)">
      <button type="button" class="pwtg" onclick="tpw('su-p',this)">👁</button>
     </div>
     <div class="sbar-w"><div class="sbar" id="sb"></div></div>
     <div class="slbl" id="sl"></div>
    </div>
    <div class="field">
     <label>Confirm Password</label>
     <div class="pw">
      <input type="password" id="su-c" placeholder="Re-enter password" required>
      <button type="button" class="pwtg" onclick="tpw('su-c',this)">👁</button>
     </div>
    </div>
    <div class="terms">By creating an account you agree to our Terms of Service.</div>
    <button class="btn" id="su-btn" onclick="doSignup()">Create Account →</button>
    <div class="sw">Already have an account?
     <a onclick="swTab('signin')">Sign in →</a>
    </div>
   </div>

   <!-- Pills -->
   <div class="pills">
    <span class="pill">🔒 JWT secured</span>
    <span class="pill">📘 RAG quizzes</span>
    <span class="pill">🃏 Flashcards</span>
    <span class="pill">📊 Analytics</span>
   </div>

  </div><!-- /card -->
 </div><!-- /scene -->
</div><!-- /page -->

<script>
/* ══════════════════════════════════════════════
   Helper: find a Streamlit input by its label
   text and set its value, then fire React events
   so Streamlit registers the change.
   ══════════════════════════════════════════════ */
function setStInput(labelText, value) {{
  // Walk the parent document for the hidden label
  const doc = window.parent.document;
  const labels = doc.querySelectorAll('label');
  for (const lbl of labels) {{
    if (lbl.textContent.trim() === labelText) {{
      const inp = doc.querySelector(
        `input[aria-labelledby="${{lbl.id}}"], #${{lbl.htmlFor}}`
      ) || lbl.closest('[data-testid="stFormRow"]')
              ?.querySelector('input');
      if (inp) {{
        const nativeSetter = Object.getOwnPropertyDescriptor(
          window.parent.HTMLInputElement.prototype, 'value'
        ).set;
        nativeSetter.call(inp, value);
        inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
        inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
        return true;
      }}
    }}
  }}
  return false;
}}

/* Click a Streamlit submit button by its text */
function clickStBtn(text) {{
  const doc = window.parent.document;
  const btns = doc.querySelectorAll('button[kind="secondaryFormSubmit"], button[data-testid="baseButton-secondaryFormSubmit"], button');
  for (const b of btns) {{
    if (b.textContent.trim() === text) {{
      b.click();
      return true;
    }}
  }}
  return false;
}}

/* ── Show loading overlay ── */
function showOverlay(msg) {{
  document.getElementById('spin-lbl').textContent = msg;
  document.getElementById('overlay').classList.add('show');
}}

/* ── Sign In ── */
function doSignin() {{
  const email = document.getElementById('si-e').value.trim();
  const pw    = document.getElementById('si-p').value;
  if (!email || !pw) {{ alert('Please fill in all fields.'); return; }}

  const btn = document.getElementById('si-btn');
  btn.textContent = 'Signing in…';
  btn.classList.add('loading');
  btn.disabled = true;

  // Set values in the hidden Streamlit relay form
  const ok1 = setStInput('si_email', email);
  const ok2 = setStInput('si_pw',    pw);

  if (ok1 && ok2) {{
    showOverlay('Signing in…');
    setTimeout(() => clickStBtn('signin'), 120);
  }} else {{
    // Fallback: URL params (works on most Streamlit setups)
    showOverlay('Signing in…');
    window.parent.location.href =
      window.parent.location.pathname +
      '?action=signin' +
      '&email=' + encodeURIComponent(email) +
      '&pw='    + encodeURIComponent(pw);
  }}
}}

/* ── Sign Up ── */
function doSignup() {{
  const name  = document.getElementById('su-n').value.trim();
  const email = document.getElementById('su-e').value.trim();
  const pw    = document.getElementById('su-p').value;
  const cf    = document.getElementById('su-c').value;

  if (!name || !email || !pw || !cf) {{ alert('Please fill in all fields.'); return; }}
  if (pw !== cf)    {{ alert('Passwords do not match!'); return; }}
  if (pw.length<8)  {{ alert('Password must be at least 8 characters.'); return; }}

  const btn = document.getElementById('su-btn');
  btn.textContent = 'Creating account…';
  btn.classList.add('loading');
  btn.disabled = true;

  const ok1 = setStInput('su_name',  name);
  const ok2 = setStInput('su_email', email);
  const ok3 = setStInput('su_pw',    pw);

  if (ok1 && ok2 && ok3) {{
    showOverlay('Creating your account…');
    setTimeout(() => clickStBtn('signup'), 120);
  }} else {{
    showOverlay('Creating your account…');
    window.parent.location.href =
      window.parent.location.pathname +
      '?action=signup' +
      '&name='  + encodeURIComponent(name) +
      '&email=' + encodeURIComponent(email) +
      '&pw='    + encodeURIComponent(pw);
  }}
}}

/* ── Tab switch ── */
function swTab(tab) {{
  document.getElementById('tsi').className = 'tab' + (tab==='signin' ? ' active' : '');
  document.getElementById('tsu').className = 'tab' + (tab==='signup' ? ' active' : '');
  document.getElementById('psi').className = 'panel' + (tab==='signin' ? ' active' : '');
  document.getElementById('psu').className = 'panel' + (tab==='signup' ? ' active' : '');

  // Persist in Streamlit via hidden relay
  const ok = setStInput('tab_val', tab);
  if (ok) {{
    setTimeout(() => clickStBtn('switchtab'), 80);
  }} else {{
    window.parent.location.href =
      window.parent.location.pathname + '?action=switchtab&tab=' + tab;
  }}
}}

/* ── Password toggle ── */
function tpw(id, btn) {{
  const i = document.getElementById(id);
  i.type = i.type === 'password' ? 'text' : 'password';
  btn.textContent = i.type === 'password' ? '👁' : '🙈';
}}

/* ── Password strength ── */
function chkStr(pw) {{
  let s = 0;
  if (pw.length>=8) s++; if (pw.length>=12) s++;
  if (/[A-Z]/.test(pw)) s++; if (/[0-9!@#$%^&*]/.test(pw)) s++;
  const L = ['','Weak','Fair','Good','Strong'];
  const C = ['','#f85149','#d29922','#388bfd','#3fb950'];
  document.getElementById('sb').style.width    = (s/4*100)+'%';
  document.getElementById('sb').style.background = C[s]||'#f85149';
  document.getElementById('sl').textContent    = L[s]||'';
  document.getElementById('sl').style.color    = C[s]||'#f85149';
}}

/* ── Custom cursor ── */
const cur=document.getElementById('cur'),ring=document.getElementById('ring');
let mx=0,my=0,rx=0,ry=0;
document.addEventListener('mousemove',e=>{{
  mx=e.clientX; my=e.clientY;
  cur.style.left=mx+'px'; cur.style.top=my+'px';
}});
(function anim(){{
  rx+=(mx-rx)*.13; ry+=(my-ry)*.13;
  ring.style.left=rx+'px'; ring.style.top=ry+'px';
  requestAnimationFrame(anim);
}})();
document.querySelectorAll('button,a,input').forEach(el=>{{
  el.addEventListener('mouseenter',()=>{{
    cur.style.width='18px'; cur.style.height='18px';
    ring.style.width='48px'; ring.style.height='48px';
  }});
  el.addEventListener('mouseleave',()=>{{
    cur.style.width='10px'; cur.style.height='10px';
    ring.style.width='34px'; ring.style.height='34px';
  }});
}});

/* ── Animated mesh canvas ── */
const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
function rsz(){{cv.width=innerWidth;cv.height=innerHeight;}}
rsz(); window.addEventListener('resize',rsz);
const dots=[];
for(let i=0;i<88;i++) dots.push({{
  x:Math.random()*cv.width, y:Math.random()*cv.height,
  vx:(Math.random()-.5)*.38, vy:(Math.random()-.5)*.38,
  r:Math.random()*1.7+.4
}});
function frame(){{
  ctx.clearRect(0,0,cv.width,cv.height);
  const g=ctx.createRadialGradient(cv.width*.28,cv.height*.22,0,
    cv.width*.5,cv.height*.5,cv.width*.85);
  g.addColorStop(0,'rgba(24,55,130,.22)');
  g.addColorStop(.5,'rgba(8,16,50,.08)');
  g.addColorStop(1,'rgba(4,7,16,0)');
  ctx.fillStyle=g; ctx.fillRect(0,0,cv.width,cv.height);
  dots.forEach(d=>{{
    d.x+=d.vx; d.y+=d.vy;
    if(d.x<0||d.x>cv.width)  d.vx*=-1;
    if(d.y<0||d.y>cv.height) d.vy*=-1;
  }});
  for(let i=0;i<dots.length;i++){{
    for(let j=i+1;j<dots.length;j++){{
      const dx=dots[i].x-dots[j].x, dy=dots[i].y-dots[j].y;
      const dist=Math.sqrt(dx*dx+dy*dy);
      if(dist<138){{
        ctx.beginPath();
        ctx.moveTo(dots[i].x,dots[i].y);
        ctx.lineTo(dots[j].x,dots[j].y);
        ctx.strokeStyle=`rgba(56,139,253,${{(1-dist/138)*.22}})`;
        ctx.lineWidth=.7; ctx.stroke();
      }}
    }}
  }}
  dots.forEach(d=>{{
    ctx.beginPath(); ctx.arc(d.x,d.y,d.r,0,Math.PI*2);
    ctx.fillStyle='rgba(56,139,253,.52)'; ctx.fill();
  }});
  requestAnimationFrame(frame);
}}
frame();

/* ── Floating particles ── */
const pw2=document.getElementById('pt-wrap');
for(let i=0;i<22;i++){{
  const p=document.createElement('div');
  p.className='pt';
  const sz=Math.random()*5+2;
  const h=Math.random()>.5?215:145;
  p.style.cssText=[
    `width:${{sz}}px`,`height:${{sz}}px`,
    `left:${{Math.random()*100}}vw`,
    `background:hsla(${{h}},80%,65%,.8)`,
    `animation-duration:${{Math.random()*13+9}}s`,
    `animation-delay:${{Math.random()*13}}s`,
    `box-shadow:0 0 ${{sz*2}}px hsla(${{h}},80%,65%,.4)`
  ].join(';');
  pw2.appendChild(p);
}}

/* ── 3-D card tilt ── */
const scene=document.getElementById('scene');
const card=document.getElementById('card');
const spot=document.getElementById('spot');
document.addEventListener('mousemove',e=>{{
  const r=card.getBoundingClientRect();
  const cx=r.left+r.width/2, cy=r.top+r.height/2;
  const dx=(e.clientX-cx)/(innerWidth/2);
  const dy=(e.clientY-cy)/(innerHeight/2);
  scene.style.transform=
    `rotateX(${{-dy*10}}deg) rotateY(${{dx*12}}deg)`;
  card.style.boxShadow=`
    0 0 0 1px rgba(56,139,253,.07),
    ${{dx*3*10}}px ${{-dy*3*10}}px 65px rgba(0,0,0,.55),
    0 6px 22px rgba(0,0,0,.4),
    inset 0 1px 0 rgba(255,255,255,.06)`;
  spot.style.left=(e.clientX-r.left)+'px';
  spot.style.top=(e.clientY-r.top)+'px';
  spot.style.opacity='1';
}});
document.addEventListener('mouseleave',()=>{{
  scene.style.transform='rotateX(0) rotateY(0)';
  spot.style.opacity='0';
}});
</script>
</body>
</html>
""", height=720, scrolling=False)

# ================================================================
# URL-PARAM FALLBACK (catches the window.parent.location.href path)
# ================================================================
params = st.query_params
action = params.get("action", "")

if action == "signin":
    email = params.get("email", "")
    pw    = params.get("pw", "")
    st.query_params.clear()
    if email and pw:
        user, err = api_login(email, pw)
        if err:
            st.session_state["login_err"] = err
            st.session_state["auth_tab"]  = "signin"
            st.rerun()
        else:
            st.session_state["login_err"]  = ""
            st.session_state["signup_err"] = ""
            st.switch_page("pages/app.py")

elif action == "signup":
    name  = params.get("name",  "")
    email = params.get("email", "")
    pw    = params.get("pw",    "")
    st.query_params.clear()
    if name and email and pw:
        user, err = api_signup(name, email, pw)
        if err:
            st.session_state["signup_err"] = err
            st.session_state["auth_tab"]   = "signup"
            st.rerun()
        else:
            st.session_state["login_err"]  = ""
            st.session_state["signup_err"] = ""
            st.switch_page("pages/app.py")

elif action == "switchtab":
    t = params.get("tab", "signin")
    st.query_params.clear()
    st.session_state["auth_tab"] = t
    st.rerun()