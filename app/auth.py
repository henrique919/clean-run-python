from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import is_production, login_required
from app.supabase_client import reset_supabase_access_token, set_supabase_access_token

try:
    import jwt
except Exception:  # pragma: no cover - production dependency guard
    jwt = None


bearer_scheme = HTTPBearer(auto_error=False)
DEFAULT_COMPANY_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_LAUNCH_ADMIN_EMAILS = "info@cleanruniq.com,harrysfuel@outlook.com"
_OPEN_ACCESS_TOKEN_TTL_SECONDS = 50 * 60
_open_access_token_cache: tuple[float, str] | None = None


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str
    company_id: str | None = None
    company_role: str | None = None
    project_roles: dict[str, str] = field(default_factory=dict)
    subcontractors: set[str] = field(default_factory=set)
    is_demo_admin: bool = False
    is_service_admin: bool = False
    auth_method: str = "jwt"

    @property
    def audit_label(self) -> str:
        return self.email or self.id


@dataclass(frozen=True)
class RequestContext:
    user: AuthUser
    access_token: str | None = None


def _dev_users() -> dict[str, AuthUser]:
    return {
        "dev-site-manager": AuthUser(
            id="dev-site-manager",
            email="site.manager@cleanrun.local",
            company_id="demo-company",
            company_role="admin",
            project_roles={"Jura Noosa": "site_manager", "Meta Street": "site_manager"},
            is_demo_admin=True,
            auth_method="dev",
        ),
        "dev-project-manager": AuthUser(
            id="dev-project-manager",
            email="project.manager@cleanrun.local",
            company_id="demo-company",
            company_role="project_manager",
            project_roles={"Jura Noosa": "project_manager", "Meta Street": "project_manager"},
            is_demo_admin=True,
            auth_method="dev",
        ),
        "dev-viewer": AuthUser(
            id="dev-viewer",
            email="viewer@cleanrun.local",
            company_id="demo-company",
            company_role="viewer",
            project_roles={"Jura Noosa": "viewer"},
            auth_method="dev",
        ),
        "dev-subcontractor": AuthUser(
            id="dev-subcontractor",
            email="astw.tiling@cleanrun.local",
            company_id="demo-company",
            company_role="subcontractor",
            project_roles={"Jura Noosa": "subcontractor"},
            subcontractors={"ASTW Tiling", "Sterling Tiling"},
            auth_method="dev",
        ),
        "dev-other-company": AuthUser(
            id="dev-other-company",
            email="other.company@cleanrun.local",
            company_id="other-company",
            company_role="admin",
            project_roles={"Other Project": "site_manager"},
            auth_method="dev",
        ),
    }


def _open_access_user() -> AuthUser:
    actor_email = (os.getenv("CLEANRUN_OPEN_ACCESS_ACTOR_EMAIL") or "info@cleanruniq.com").strip()
    return AuthUser(
        id="open-access",
        email=actor_email,
        company_id=DEFAULT_COMPANY_ID,
        company_role="admin",
        project_roles={"*": "project_manager"},
        is_demo_admin=True,
        auth_method="open_access",
    )


def _fetch_password_token(email: str, password: str) -> str:
    supabase_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY")
    if not supabase_url or not publishable_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Auth is not configured")

    request = UrlRequest(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        data=json.dumps({"email": email, "password": password}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "apikey": publishable_key,
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {400, 401, 403}:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Open access login is not configured. Set CLEANRUN_OPEN_ACCESS_EMAIL and CLEANRUN_OPEN_ACCESS_PASSWORD on Render.",
            ) from exc
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Auth provider unavailable") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Auth provider unavailable") from exc

    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Open access login is not configured. Set CLEANRUN_OPEN_ACCESS_EMAIL and CLEANRUN_OPEN_ACCESS_PASSWORD on Render.",
        )
    return token


def _open_access_supabase_token() -> str | None:
    global _open_access_token_cache

    direct = (os.getenv("CLEANRUN_OPEN_ACCESS_SUPABASE_TOKEN") or "").strip()
    if direct:
        return direct

    email = (os.getenv("CLEANRUN_OPEN_ACCESS_EMAIL") or "").strip()
    password = os.getenv("CLEANRUN_OPEN_ACCESS_PASSWORD") or ""
    if not email or not password:
        return None

    now = time.time()
    if _open_access_token_cache and _open_access_token_cache[0] > now:
        return _open_access_token_cache[1]

    token = _fetch_password_token(email, password)
    _open_access_token_cache = (now + _OPEN_ACCESS_TOKEN_TTL_SECONDS, token)
    return token


def _claim_list(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value if item}
    return set()


def _launch_admin_emails() -> set[str]:
    raw = os.getenv("CLEANRUN_LAUNCH_ADMIN_EMAILS", DEFAULT_LAUNCH_ADMIN_EMAILS)
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def _user_from_claims(claims: dict[str, Any]) -> AuthUser:
    app_meta = claims.get("app_metadata") or {}
    cleanrun = app_meta.get("cleanrun") or {}
    project_roles = cleanrun.get("project_roles") or {}
    if not isinstance(project_roles, dict):
        project_roles = {}
    email = str(claims.get("email") or app_meta.get("email") or "")
    if email.lower() in _launch_admin_emails():
        cleanrun = {
            **cleanrun,
            "company_id": cleanrun.get("company_id") or DEFAULT_COMPANY_ID,
            "company_role": "admin",
            "project_roles": {"*": "project_manager", **project_roles},
            "demo_admin": True,
        }
        project_roles = cleanrun["project_roles"]
    return AuthUser(
        id=str(claims.get("sub") or ""),
        email=email,
        company_id=cleanrun.get("company_id"),
        company_role=cleanrun.get("company_role") or app_meta.get("role"),
        project_roles={str(key): str(value) for key, value in project_roles.items()},
        subcontractors=_claim_list(cleanrun.get("subcontractors")),
        is_demo_admin=bool(cleanrun.get("demo_admin")),
        is_service_admin=bool(cleanrun.get("service_admin")),
        auth_method="jwt",
    )


def _decode_supabase_jwt(token: str) -> AuthUser:
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    if jwt_secret and jwt is not None:
        try:
            claims = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                audience=os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated"),
                options={"verify_aud": bool(os.getenv("SUPABASE_JWT_AUDIENCE"))},
            )
            user = _user_from_claims(claims)
            if not user.id:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
            return user
        except HTTPException:
            raise
        except Exception:
            # Fall through to Supabase's Auth API. This keeps production login
            # working if the project rotates signing keys or Render has a stale
            # JWT secret, without ever using a service-role key in the web app.
            pass

    claims = _fetch_supabase_auth_user(token)
    user = _user_from_claims(claims)
    if not user.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    return user


def _fetch_supabase_auth_user(token: str) -> dict[str, Any]:
    supabase_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY")
    if not supabase_url or not publishable_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Auth is not configured")

    request = UrlRequest(
        f"{supabase_url}/auth/v1/user",
        headers={
            "apikey": publishable_key,
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Auth provider rejected token verification")
    except (URLError, TimeoutError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Auth provider unavailable")

    return {
        "sub": payload.get("id"),
        "email": payload.get("email"),
        "app_metadata": payload.get("app_metadata") or {},
        "user_metadata": payload.get("user_metadata") or {},
    }


def _request_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> str | None:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        return credentials.credentials.strip()
    return (request.cookies.get("cleanrun_access_token") or "").strip() or None


def _authenticate(token: str | None) -> AuthUser:
    if not login_required():
        if not token:
            return _open_access_user()
        if not is_production() and token in _dev_users():
            return _dev_users()[token]
        try:
            return _decode_supabase_jwt(token)
        except HTTPException:
            return _open_access_user()

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    if not is_production() and token in _dev_users():
        return _dev_users()[token]

    return _decode_supabase_jwt(token)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthUser:
    return _authenticate(_request_token(request, credentials))


async def get_request_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    user: AuthUser = Depends(get_current_user),
) -> RequestContext:
    token = _request_token(request, credentials)
    if user.auth_method == "jwt":
        supabase_token = token
    elif user.auth_method == "open_access":
        supabase_token = _open_access_supabase_token()
    else:
        supabase_token = None
    context_token = set_supabase_access_token(supabase_token)
    request.state.user = user
    request.state.supabase_access_token = supabase_token
    try:
        yield RequestContext(user=user, access_token=supabase_token)
    finally:
        reset_supabase_access_token(context_token)
