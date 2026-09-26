"""Postgres-backed auth. Contract: POST /api/v1/auth/signin {email,password} -> {token, token_type}."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import asyncpg
from fastapi import APIRouter, Header, HTTPException, status
from jose import jwt
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anime:animepass@localhost:5432/anime")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MIN", "1440"))


class SignIn(BaseModel):
    email: str
    password: str


class SignUp(SignIn):
    display_name: str | None = None


def _hash(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
    return f"pbkdf2$100000${salt}${dk.hex()}"


def _verify(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$")
        if algo != "pbkdf2":
            raise ValueError("legacy hash")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), digest)
    except ValueError:
        pass  # legacy bcrypt hash from users.json migration -> try passlib
    except Exception:
        return False
    try:
        from passlib.hash import bcrypt

        return bcrypt.verify(password, stored)
    except Exception:
        return False


async def _conn():
    try:
        return await asyncpg.connect(DATABASE_URL)
    except Exception:
        raise HTTPException(status_code=503, detail="auth db unavailable")


def _token(email: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MIN)
    return jwt.encode({"sub": email, "exp": exp}, JWT_SECRET, algorithm="HS256")


@router.post("/signup", status_code=201)
async def signup(data: SignUp):
    conn = await _conn()
    try:
        row = await conn.fetchrow(
            "INSERT INTO users (email, password_hash, display_name) VALUES ($1, $2, $3)"
            " ON CONFLICT (email) DO NOTHING RETURNING id, email",
            data.email, _hash(data.password), data.display_name)
    finally:
        await conn.close()
    if not row:
        raise HTTPException(status_code=400, detail="Email already exists")
    return dict(row)


@router.post("/signin")
async def signin(data: SignIn):
    conn = await _conn()
    try:
        row = await conn.fetchrow("SELECT email, password_hash FROM users WHERE email=$1", data.email)
    finally:
        await conn.close()
    if not row or not _verify(data.password, row["password_hash"] or ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return {"token": _token(row["email"]), "token_type": "bearer"}


@router.get("/me")
async def me(authorization: str = Header("")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Missing token")
    try:
        email = jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"]).get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    conn = await _conn()
    try:
        row = await conn.fetchrow("SELECT email, display_name, avatar_url FROM users WHERE email=$1", email)
    finally:
        await conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)
