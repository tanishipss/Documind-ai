"""
DocuMind AI — Authentication API
FastAPI + SQLite + JWT (python-jose)
Run: uvicorn backend.auth_api:app --reload --port 8001
"""

import os
import sqlite3
import hashlib
import hmac
import secrets
import re
import base64
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator
from jose import jwt, JWTError  # type: ignore

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
SECRET_KEY  = os.environ.get("DOCUMIND_SECRET", secrets.token_hex(32))
ALGORITHM   = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24   # 24 hours
DB_PATH     = "data/documind_users.db"

app = FastAPI(title="DocuMind Auth API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()


# ──────────────────────────────────────────────
# DATABASE SETUP
# ──────────────────────────────────────────────
def get_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            email           TEXT    NOT NULL UNIQUE,
            password_hash   TEXT    NOT NULL,
            salt            TEXT    NOT NULL,
            institution     TEXT    DEFAULT '',
            standard        TEXT    DEFAULT '',
            profile_pic     TEXT    DEFAULT '',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
            last_login      TEXT
        )
    """)
    # Migrate older DBs that don't have the new columns yet
    existing = [
        row[1] for row in
        conn.execute("PRAGMA table_info(users)").fetchall()
    ]
    for col, definition in [
        ("institution",  "TEXT DEFAULT ''"),
        ("standard",     "TEXT DEFAULT ''"),
        ("profile_pic",  "TEXT DEFAULT ''"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
    conn.commit()
    conn.close()


init_db()


# ──────────────────────────────────────────────
# PASSWORD HASHING
# ──────────────────────────────────────────────
def hash_password(password: str, salt: str) -> str:
    return hmac.new(
        salt.encode(),
        password.encode(),
        hashlib.sha256
    ).hexdigest()


def verify_password(password: str, salt: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt), hashed)


# ──────────────────────────────────────────────
# JWT HELPERS
# ──────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again."
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    payload = decode_token(credentials.credentials)
    email: str = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload."
        )
    conn = get_db()
    user = conn.execute(
        "SELECT id, name, email, institution, standard, "
        "profile_pic, created_at, last_login "
        "FROM users WHERE email = ?",
        (email,)
    ).fetchone()
    conn.close()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found."
        )
    return dict(user)


# ──────────────────────────────────────────────
# SCHEMAS
# ──────────────────────────────────────────────
class SignupRequest(BaseModel):
    name: str
    email: str
    password: str

    @validator("name")
    def name_valid(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters.")
        if len(v) > 50:
            raise ValueError("Name must be under 50 characters.")
        return v

    @validator("email")
    def email_valid(cls, v):
        v = v.strip().lower()
        if not re.match(r"^[\w\.\+\-]+@[\w\-]+\.[a-z]{2,}$", v):
            raise ValueError("Enter a valid email address.")
        return v

    @validator("password")
    def password_valid(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str

    @validator("email")
    def email_lowercase(cls, v):
        return v.strip().lower()


class ProfileUpdateRequest(BaseModel):
    name:        Optional[str] = None
    institution: Optional[str] = None
    standard:    Optional[str] = None
    profile_pic: Optional[str] = None   # base64 encoded image string


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         dict


# ──────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────
@app.post("/auth/signup", response_model=TokenResponse, status_code=201)
def signup(req: SignupRequest):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM users WHERE email = ?", (req.email,)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists."
        )

    salt          = secrets.token_hex(16)
    password_hash = hash_password(req.password, salt)

    conn.execute(
        "INSERT INTO users (name, email, password_hash, salt) "
        "VALUES (?, ?, ?, ?)",
        (req.name, req.email, password_hash, salt)
    )
    conn.commit()

    user = conn.execute(
        "SELECT id, name, email, institution, standard, "
        "profile_pic, created_at FROM users WHERE email = ?",
        (req.email,)
    ).fetchone()
    conn.close()

    token = create_access_token({"sub": req.email, "name": req.name})
    return TokenResponse(access_token=token, user=dict(user))


@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (req.email,)
    ).fetchone()

    if not user or not verify_password(
        req.password, user["salt"], user["password_hash"]
    ):
        conn.close()
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password."
        )

    conn.execute(
        "UPDATE users SET last_login = datetime('now') WHERE email = ?",
        (req.email,)
    )
    conn.commit()

    user_data = {
        "id":          user["id"],
        "name":        user["name"],
        "email":       user["email"],
        "institution": user["institution"] or "",
        "standard":    user["standard"]    or "",
        "profile_pic": user["profile_pic"] or "",
        "created_at":  user["created_at"],
        "last_login":  user["last_login"],
    }
    conn.close()

    token = create_access_token({"sub": req.email, "name": user["name"]})
    return TokenResponse(access_token=token, user=user_data)


@app.get("/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


@app.put("/auth/profile")
def update_profile(
    req: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    conn   = get_db()
    fields = []
    values = []

    if req.name is not None:
        name = req.name.strip()
        if len(name) < 2:
            raise HTTPException(400, "Name must be at least 2 characters.")
        fields.append("name = ?");        values.append(name)

    if req.institution is not None:
        fields.append("institution = ?"); values.append(req.institution.strip())

    if req.standard is not None:
        fields.append("standard = ?");    values.append(req.standard.strip())

    if req.profile_pic is not None:
        # Validate it's a valid base64 image (basic check)
        if req.profile_pic and not req.profile_pic.startswith("data:image"):
            raise HTTPException(400, "profile_pic must be a base64 data URL.")
        fields.append("profile_pic = ?"); values.append(req.profile_pic)

    if not fields:
        raise HTTPException(400, "No fields provided to update.")

    values.append(current_user["email"])
    conn.execute(
        f"UPDATE users SET {', '.join(fields)} WHERE email = ?",
        values
    )
    conn.commit()

    updated = conn.execute(
        "SELECT id, name, email, institution, standard, "
        "profile_pic, created_at, last_login "
        "FROM users WHERE email = ?",
        (current_user["email"],)
    ).fetchone()
    conn.close()

    return dict(updated)


@app.post("/auth/logout")
def logout():
    return {"message": "Logged out successfully."}


@app.get("/health")
def health():
    return {"status": "ok", "service": "DocuMind Auth API v2"}