"""Social login (Google / GitHub / Facebook) via plain OAuth2 + httpx.

No extra dependencies: authorization-code flow is a redirect, one token
exchange, and one userinfo call per provider. A provider with empty
client_id/secret is disabled (400). Users are matched by verified email, so
an OAuth login lands in the same account as an email registration.

CSRF protection without server state: the `state` param is an HMAC-signed
payload (nonce + expiry) verified with the JWT secret.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
import urllib.parse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_token
from app.db import models
from app.db.session import get_db

oauth = APIRouter()

_STATE_TTL = 600  # seconds


def _provider_conf(provider: str) -> dict | None:
    conf = {
        "google": {
            "id": settings.google_client_id,
            "secret": settings.google_client_secret,
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scope": "openid email profile",
        },
        "github": {
            "id": settings.github_client_id,
            "secret": settings.github_client_secret,
            "auth_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "scope": "user:email",
        },
        "facebook": {
            "id": settings.facebook_client_id,
            "secret": settings.facebook_client_secret,
            "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
            "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
            "scope": "email",
        },
    }.get(provider)
    if not conf or not conf["id"] or not conf["secret"]:
        return None
    return conf


def _callback_url(request: Request, provider: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/auth/oauth/{provider}/callback"


def _sign_state(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(settings.jwt_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def _verify_state(state: str) -> None:
    try:
        raw, sig = state.rsplit(".", 1)
    except ValueError:
        raise HTTPException(400, "Invalid OAuth state")
    expect = hmac.new(settings.jwt_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig):
        raise HTTPException(400, "Invalid OAuth state")
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw.encode()).decode())
    except Exception:
        raise HTTPException(400, "Invalid OAuth state")
    if time.time() - float(payload.get("ts", 0)) > _STATE_TTL:
        raise HTTPException(400, "OAuth session expired; please try again")


@oauth.get("/auth/providers")
def oauth_providers():
    return {p: _provider_conf(p) is not None for p in ("google", "github", "facebook")}


@oauth.get("/auth/oauth/{provider}")
def oauth_login(provider: str, request: Request):
    conf = _provider_conf(provider)
    if conf is None:
        raise HTTPException(400, f"{provider} login is not configured")
    state = _sign_state({"nonce": secrets.token_hex(16), "ts": time.time()})
    params = {
        "client_id": conf["id"],
        "redirect_uri": _callback_url(request, provider),
        "response_type": "code",
        "scope": conf["scope"],
        "state": state,
    }
    return RedirectResponse(f"{conf['auth_url']}?{urllib.parse.urlencode(params)}")


async def _fetch_profile(provider: str, conf: dict, code: str, redirect_uri: str) -> tuple[str, str]:
    """Exchange code, fetch profile. Returns (email, name)."""
    async with httpx.AsyncClient(timeout=20) as client:
        if provider == "facebook":
            tr = await client.get(
                conf["token_url"],
                params={
                    "client_id": conf["id"],
                    "client_secret": conf["secret"],
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            token = tr.json().get("access_token")
            if not token:
                raise HTTPException(400, "Facebook token exchange failed")
            ur = await client.get(
                "https://graph.facebook.com/me",
                params={"fields": "id,name,email", "access_token": token},
            )
            profile = ur.json()
            email = (profile.get("email") or "").strip().lower()
            if not email:
                raise HTTPException(
                    400, "Facebook did not share an email address (email permission required)"
                )
            return email, profile.get("name") or ""
        if provider == "github":
            tr = await client.post(
                conf["token_url"],
                headers={"Accept": "application/json"},
                json={
                    "client_id": conf["id"],
                    "client_secret": conf["secret"],
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            token = tr.json().get("access_token")
            if not token:
                raise HTTPException(400, "GitHub token exchange failed")
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            ur = await client.get("https://api.github.com/user", headers=headers)
            profile = ur.json()
            email = (profile.get("email") or "").strip().lower()
            if not email:
                er = await client.get("https://api.github.com/user/emails", headers=headers)
                candidates = er.json() if isinstance(er.json(), list) else []
                verified = [e for e in candidates
                            if e.get("verified") and e.get("email")]
                primary = next((e for e in verified if e.get("primary")), None)
                email = ((primary or (verified[0] if verified else {})).get("email") or "").strip().lower()
            if not email:
                raise HTTPException(400, "GitHub did not share a verified email address")
            return email, profile.get("name") or profile.get("login") or ""
        # google
        tr = await client.post(
            conf["token_url"],
            data={
                "client_id": conf["id"],
                "client_secret": conf["secret"],
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        token = tr.json().get("access_token")
        if not token:
            raise HTTPException(400, "Google token exchange failed")
        ur = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {token}"},
        )
        profile = ur.json()
        if not profile.get("email_verified", False):
            raise HTTPException(400, "Google email is not verified")
        email = (profile.get("email") or "").strip().lower()
        if not email:
            raise HTTPException(400, "Google did not share an email address")
        return email, profile.get("name") or ""


@oauth.get("/auth/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    conf = _provider_conf(provider)
    if conf is None:
        raise HTTPException(400, f"{provider} login is not configured")
    if not state:
        raise HTTPException(400, "Missing OAuth state")
    _verify_state(state)
    if not code:
        raise HTTPException(400, "Login was not approved")
    email, name = await _fetch_profile(provider, conf, code, _callback_url(request, provider))
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        user = models.User(email=email, name=name[:255] if name else None,
                            password_hash=None)
        db.add(user)
        db.commit()
        db.refresh(user)
    token = create_token(user.id, user.email, bool(user.is_admin))
    # Token in the URL fragment (after #): never sent to any server, the
    # callback page reads it client-side and stores it in localStorage.
    dest = settings.frontend_url.rstrip("/") + f"/auth/callback#token={token}"
    return RedirectResponse(dest)
