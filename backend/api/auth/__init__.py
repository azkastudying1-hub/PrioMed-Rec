"""
api/auth/__init__.py
"""
from api.auth.jwt import (
    create_access_token,
    create_refresh_token,
    verify_token,
    TokenData,
)
from api.auth.rbac import (
    UserRole,
    require_roles,
    get_current_user,
    get_current_user_optional,
    require_pharmacist,
    require_coordinator,
    require_admin,
    require_auditor,
    SERVICE_TOKEN_ROLES,
    verify_service_token,
)
from api.auth.password import hash_password, verify_password

__all__ = [
    "create_access_token", "create_refresh_token", "verify_token", "TokenData",
    "UserRole", "require_roles", "get_current_user", "get_current_user_optional",
    "require_pharmacist", "require_coordinator", "require_admin", "require_auditor",
    "SERVICE_TOKEN_ROLES", "verify_service_token",
    "hash_password", "verify_password",
]
