"""
Re-export everything from apps.core.permissions for backwards compatibility.
"""
from apps.core.permissions import (
    ROLES,
    PERMISSION_CATALOG,
    PROTECTED_PERMISSIONS,
    has_role_permission,
    HasModulePermission,
    IsSuperadminOnly,
    CanViewActivityLogs,
    IsAdmin,
    IsCMSUser,
)

PROTECTED_OPERATIONS = PROTECTED_PERMISSIONS

__all__ = [
    "ROLES",
    "PERMISSION_CATALOG",
    "PROTECTED_PERMISSIONS",
    "PROTECTED_OPERATIONS",
    "has_role_permission",
    "HasModulePermission",
    "IsSuperadminOnly",
    "CanViewActivityLogs",
    "IsAdmin",
    "IsCMSUser",
]
