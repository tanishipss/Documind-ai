"""
DocuMind AI — Auth utilities for Streamlit
File location: frontend/auth_utils.py
"""

import requests
import streamlit as st

AUTH_API_BASE = "http://127.0.0.1:8001"


# ──────────────────────────────────────────────
# TOKEN HELPERS
# ──────────────────────────────────────────────
def _auth_headers() -> dict:
    token = st.session_state.get("auth_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def is_logged_in() -> bool:
    return bool(st.session_state.get("auth_token"))


def get_current_user() -> dict:
    return st.session_state.get("auth_user", {})


def logout():
    for key in ["auth_token", "auth_user", "token_verified"]:
        st.session_state.pop(key, None)
    st.switch_page("login.py")


# ──────────────────────────────────────────────
# AUTH API CALLS
# ──────────────────────────────────────────────
def api_signup(name: str, email: str, password: str):
    try:
        resp = requests.post(
            f"{AUTH_API_BASE}/auth/signup",
            json={"name": name, "email": email, "password": password},
            timeout=10
        )
        data = resp.json()
        if resp.status_code == 201:
            st.session_state["auth_token"] = data["access_token"]
            st.session_state["auth_user"]  = data["user"]
            return data["user"], None
        return None, data.get("detail", "Signup failed.")
    except requests.exceptions.ConnectionError:
        return None, "Cannot reach Auth API. Is it running on port 8001?"
    except Exception as e:
        return None, str(e)


def api_login(email: str, password: str):
    try:
        resp = requests.post(
            f"{AUTH_API_BASE}/auth/login",
            json={"email": email, "password": password},
            timeout=10
        )
        data = resp.json()
        if resp.status_code == 200:
            st.session_state["auth_token"] = data["access_token"]
            st.session_state["auth_user"]  = data["user"]
            return data["user"], None
        return None, data.get("detail", "Login failed.")
    except requests.exceptions.ConnectionError:
        return None, "Cannot reach Auth API. Is it running on port 8001?"
    except Exception as e:
        return None, str(e)


def api_verify_token() -> bool:
    if not is_logged_in():
        return False
    try:
        resp = requests.get(
            f"{AUTH_API_BASE}/auth/me",
            headers=_auth_headers(),
            timeout=5
        )
        if resp.status_code == 200:
            st.session_state["auth_user"] = resp.json()
            return True
        st.session_state.pop("auth_token", None)
        st.session_state.pop("auth_user",  None)
        return False
    except Exception:
        return False


def api_update_profile(
    name: str = None,
    institution: str = None,
    standard: str = None,
    profile_pic: str = None
):
    """
    Update user profile fields.
    profile_pic should be a base64 data URL string e.g. "data:image/png;base64,..."
    Returns (updated_user_dict, None) or (None, error_str)
    """
    payload = {}
    if name        is not None: payload["name"]        = name
    if institution is not None: payload["institution"]  = institution
    if standard    is not None: payload["standard"]     = standard
    if profile_pic is not None: payload["profile_pic"]  = profile_pic

    try:
        resp = requests.put(
            f"{AUTH_API_BASE}/auth/profile",
            json=payload,
            headers=_auth_headers(),
            timeout=15        # larger timeout — profile pic can be big
        )
        data = resp.json()
        if resp.status_code == 200:
            st.session_state["auth_user"] = data
            return data, None
        return None, data.get("detail", "Profile update failed.")
    except requests.exceptions.ConnectionError:
        return None, "Cannot reach Auth API. Is it running on port 8001?"
    except Exception as e:
        return None, str(e)