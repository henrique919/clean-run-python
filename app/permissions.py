from __future__ import annotations

import os
from collections.abc import Iterable

from fastapi import HTTPException, status

from app.auth import AuthUser, is_production
from app.models import Item, Settings


COMPANY_ADMIN_ROLES = {"owner", "admin", "company_admin"}
COMPANY_PROJECT_WIDE_ROLES = {"owner", "admin", "company_admin", "project_manager", "quality_manager"}
PROJECT_WRITE_ROLES = {"project_admin", "project_manager", "site_manager", "foreman", "quality_manager", "owner", "admin", "company_admin"}
PROJECT_CLOSE_ROLES = {"project_admin", "project_manager", "site_manager", "foreman", "quality_manager", "owner", "admin", "company_admin"}
PROJECT_REPORT_ROLES = PROJECT_WRITE_ROLES | {"viewer"}


def forbidden(detail: str = "Not permitted") -> None:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def not_found() -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")


def project_names(settings: Settings) -> set[str]:
    return set(settings.projects or settings.project_configs.keys())


def project_role(user: AuthUser, project: str) -> str | None:
    return user.project_roles.get(project) or user.project_roles.get("*")


def has_company_wide_access(user: AuthUser) -> bool:
    return bool(user.is_service_admin or user.company_role in COMPANY_PROJECT_WIDE_ROLES)


def can_access_project(user: AuthUser, project: str) -> bool:
    return bool(user.is_service_admin or project_role(user, project))


def require_project_access(user: AuthUser, project: str, allowed_roles: Iterable[str] | None = None) -> None:
    role = project_role(user, project)
    if user.is_service_admin:
        return
    if not role:
        forbidden("Project access required")
    if allowed_roles is not None and role not in set(allowed_roles):
        forbidden("Project permission required")


def can_access_item(user: AuthUser, item: Item) -> bool:
    if can_access_project(user, item.project):
        if project_role(user, item.project) == "subcontractor":
            return item.subcontractor in user.subcontractors
        return True
    return bool(item.subcontractor and item.subcontractor in user.subcontractors)


def require_item_access(user: AuthUser, item: Item) -> None:
    if not can_access_item(user, item):
        not_found()


def require_create_item(user: AuthUser, project: str) -> None:
    require_project_access(user, project, PROJECT_WRITE_ROLES)


def require_update_item(user: AuthUser, item: Item) -> None:
    require_item_access(user, item)
    require_project_access(user, item.project, PROJECT_WRITE_ROLES)


def require_issue_item(user: AuthUser, item: Item) -> None:
    require_update_item(user, item)


def require_close_item(user: AuthUser, item: Item) -> None:
    require_item_access(user, item)
    require_project_access(user, item.project, PROJECT_CLOSE_ROLES)


def require_rectification_access(user: AuthUser, item: Item) -> None:
    require_item_access(user, item)
    if project_role(user, item.project) == "subcontractor" and item.subcontractor not in user.subcontractors:
        not_found()


def require_comment_access(user: AuthUser, item: Item) -> None:
    require_item_access(user, item)


def require_report_access(user: AuthUser, project: str) -> None:
    require_project_access(user, project, PROJECT_REPORT_ROLES)


def visible_items(user: AuthUser, items: list[Item]) -> list[Item]:
    return [item for item in items if can_access_item(user, item)]


def visible_projects(user: AuthUser, settings: Settings) -> list[str]:
    if user.is_service_admin:
        return settings.projects
    return [project for project in settings.projects if can_access_project(user, project)]


def require_storage_status_access(user: AuthUser) -> None:
    if not (user.is_service_admin or user.company_role in COMPANY_ADMIN_ROLES):
        forbidden("Admin permission required")


def require_demo_reset(user: AuthUser) -> None:
    enabled = os.getenv("CLEANRUN_ENABLE_DEMO_RESET", "").lower() in {"1", "true", "yes"}
    if is_production() and not enabled:
        forbidden("Demo reset is disabled in production")
    if not enabled and not user.is_demo_admin:
        forbidden("Demo reset is disabled")
    if not user.is_demo_admin:
        forbidden("Demo admin permission required")
