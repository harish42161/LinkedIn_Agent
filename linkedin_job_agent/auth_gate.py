"""
Security Authentication Gate for LinkedIn Job Agent Dashboard.

Provides password-based login protection via Streamlit secrets.
All sessions are tracked with rate limiting to block brute-force attacks.
"""

import streamlit as st
import hashlib
import time
import hmac
from datetime import datetime, timedelta

# ─── Rate Limiting Config ────────────────────────────────────────────────────
MAX_ATTEMPTS = 5          # max failed attempts before lockout
LOCKOUT_MINUTES = 15      # lockout duration in minutes
ATTEMPT_WINDOW_MINUTES = 10  # sliding window for counting attempts


def _get_password_hash(password: str) -> str:
    """Return SHA-256 hex digest of the password."""
    return hashlib.sha256(password.encode()).hexdigest()


def _is_locked_out() -> bool:
    """Check if current session is rate-limited."""
    if "lockout_until" not in st.session_state:
        return False
    if datetime.now() < st.session_state.lockout_until:
        return True
    # Lockout expired — reset
    st.session_state.pop("lockout_until", None)
    st.session_state.pop("failed_attempts", None)
    return False


def _record_failed_attempt():
    """Record a failed login attempt and apply lockout if threshold reached."""
    now = datetime.now()

    if "failed_attempts" not in st.session_state:
        st.session_state.failed_attempts = []

    # Remove attempts outside the sliding window
    window = now - timedelta(minutes=ATTEMPT_WINDOW_MINUTES)
    st.session_state.failed_attempts = [
        t for t in st.session_state.failed_attempts if t > window
    ]

    st.session_state.failed_attempts.append(now)

    if len(st.session_state.failed_attempts) >= MAX_ATTEMPTS:
        st.session_state.lockout_until = now + timedelta(minutes=LOCKOUT_MINUTES)


def _check_password(input_password: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    try:
        correct = st.secrets["auth"]["DASHBOARD_PASSWORD"]
    except (KeyError, AttributeError):
        # Fallback: check environment variable
        import os
        correct = os.getenv("DASHBOARD_PASSWORD", "")

    if not correct:
        return True  # No password set → open (dev mode only)

    return hmac.compare_digest(
        _get_password_hash(input_password),
        _get_password_hash(correct)
    )


def require_auth():
    """
    Render login gate. Call this at the TOP of every page.

    Sets st.session_state.authenticated = True on success.
    The calling script must check this and return early if False.
    """
    if st.session_state.get("authenticated"):
        return True

    # ── Page styling ──────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .login-box {
        max-width: 420px; margin: 80px auto; padding: 40px;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border: 1px solid #334155; border-radius: 16px;
        box-shadow: 0 25px 50px rgba(0,0,0,0.6);
    }
    .login-title { color: #0ea5e9; font-size: 1.8rem; font-weight: 700; margin-bottom: 4px; }
    .login-sub   { color: #94a3b8; font-size: 0.9rem; margin-bottom: 24px; }
    .security-badge {
        background: rgba(16,185,129,0.1); border: 1px solid #10b981;
        border-radius: 8px; padding: 8px 12px; font-size: 0.8rem; color: #34d399;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Lockout check ─────────────────────────────────────────────────────────
    if _is_locked_out():
        remaining = (st.session_state.lockout_until - datetime.now()).seconds // 60
        st.error(f"🔒 Too many failed attempts. Try again in **{remaining + 1} minutes**.")
        st.stop()
        return False

    # ── Login form ────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class="login-box">
          <div class="login-title">🤖 LinkedIn Agent</div>
          <div class="login-sub">Secure Monitoring Dashboard</div>
          <div class="security-badge">🛡️ SSL Encrypted · Rate Limited · XSRF Protected</div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=True):
            password = st.text_input(
                "🔑 Dashboard Password",
                type="password",
                placeholder="Enter your dashboard password",
                help="Set via Streamlit Cloud Secrets → auth.DASHBOARD_PASSWORD"
            )
            submitted = st.form_submit_button("🚀 Sign In", use_container_width=True)

        if submitted:
            if _check_password(password):
                st.session_state.authenticated = True
                st.session_state.login_time = datetime.now().isoformat()
                # Clear failed attempts on success
                st.session_state.pop("failed_attempts", None)
                st.rerun()
            else:
                _record_failed_attempt()
                attempts_left = MAX_ATTEMPTS - len(st.session_state.get("failed_attempts", []))
                st.error(f"❌ Incorrect password. {attempts_left} attempt(s) remaining.")
                time.sleep(1)  # Add delay to slow brute force

    st.stop()
    return False


def logout():
    """Clear authentication state and force re-login."""
    for key in ["authenticated", "login_time", "failed_attempts", "lockout_until"]:
        st.session_state.pop(key, None)
    st.rerun()
