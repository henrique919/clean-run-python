from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import is_production
from app.supabase_client import reset_supabase_access_token, set_supabase_access_token

try:
    import jwt
except Exception:  # pragma: no cover - production dependency guard
    jwt = None


bearer_scheme = HTTPBearer(auto_error=False)


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


def _claim_list(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value if item}
    return set()


def _user_from_claims(claims: dict[str, Any]) -> AuthUser:
    app_meta = claims.get("app_metadata") or {}
    cleanrun = app_meta.get("cleanrun") or {}
    project_roles = cleanrun.get("project_roles") or {}
    if not isinstance(project_roles, dict):
        project_roles = {}
    return AuthUser(
        id=str(claims.get("sub") or ""),
        email=str(claims.get("email") or app_meta.get("email") or ""),
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
    if not jwt_secret:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Auth is not configured")
    if jwt is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="JWT library is not installed")
    try:
        claims = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience=os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated"),
            options={"verify_aud": bool(os.getenv("SUPABASE_JWT_AUDIENCE"))},
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")
    user = _user_from_claims(claims)
    if not user.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    return user


def _request_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> str | None:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        return credentials.credentials.strip()
    return (request.cookies.get("cleanrun_access_token") or "").strip() or None


def _authenticate(token: str | None) -> AuthUser:
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
    supabase_token = token if user.auth_method == "jwt" else None
    context_token = set_supabase_access_token(supabase_token)
    request.state.user = user
    request.state.supabase_access_token = supabase_token
    try:
        yield RequestContext(user=user, access_token=supabase_token)
    finally:
        reset_supabase_access_token(context_token)
