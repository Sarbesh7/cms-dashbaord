"""
Centralized, code-controlled role and permission definitions (RBAC).

Roles and permissions are predefined here and cannot be created at runtime.

* ``PERMISSION_CATALOG`` registers every permission, grouped by module.
* ``ROLE_DEFINITIONS`` lists the seven roles and what each one is granted.
  A grant is an exact permission (``"events.create"``), a module wildcard
  (``"events.all"``) that expands only to that module's *normal* permissions,
  or ``"*"`` (every registered permission).
* ``PROTECTED_PERMISSIONS`` maps sensitive permissions to the only roles that
  may hold them. Wildcards never bypass this table.

Matching is exact: a permission must be registered and explicitly granted.
There is no prefix matching.
"""
from rest_framework.permissions import BasePermission

# --------------------------------------------------------------------------
# Permission catalog: module -> (label, actions)
# --------------------------------------------------------------------------
PERMISSION_CATALOG = {
    "dashboard": {"label": "Dashboard", "actions": ["view", "overview.view", "stats.view"]},
    "tenures": {"label": "Tenures", "actions": ["view", "create", "update", "delete"]},
    "members": {"label": "Members", "actions": ["view", "create", "update", "delete", "view_history"]},
    "alumni": {"label": "Alumni", "actions": ["view", "create", "update", "delete"]},
    "events": {"label": "Events", "actions": ["view", "create", "update", "delete"]},
    "mentors": {"label": "Mentors", "actions": ["view", "create", "update", "delete"]},
    "notices": {"label": "Notices", "actions": ["view", "create", "update", "delete", "publish", "unpublish"]},
    "blogs": {"label": "Blogs", "actions": ["view", "create", "update", "delete", "publish", "unpublish"]},
    "certificates": {
        "label": "Certificates",
        "actions": ["view", "create", "update", "delete", "verify", "manage_templates"],
    },
    "papers": {"label": "Past Papers", "actions": ["view", "create", "update", "delete"]},
    "media": {"label": "Media", "actions": ["view", "upload", "delete"]},
    "admin_access": {"label": "Admin Access", "actions": ["view", "change_own_password"]},
    "accounts": {
        "label": "Accounts",
        "actions": [
            "view", "create", "update", "delete",
            "change_status", "assign_role", "change_password", "manage",
        ],
    },
    "activity_logs": {"label": "Activity Logs", "actions": ["view"]},
    "announcements": {"label": "Announcements", "actions": ["view", "create", "update", "delete"]},
    "notifications": {"label": "Notifications", "actions": ["view", "send"]},
}

ALL_PERMISSIONS = frozenset(
    f"{module}.{action}" for module, spec in PERMISSION_CATALOG.items() for action in spec["actions"]
)

# Sensitive permissions and the only roles allowed to hold them.
PROTECTED_PERMISSIONS = {
    **{f"accounts.{a}": ("superadmin",) for a in PERMISSION_CATALOG["accounts"]["actions"]},
    "members.delete": ("superadmin",),
    "activity_logs.view": ("superadmin", "admin"),
    "admin_access.view": ("superadmin", "admin"),
    "admin_access.change_own_password": ("superadmin", "admin"),
}

_CONTENT_MODULES = ("tenures", "members", "alumni", "events", "mentors", "notices", "blogs", "certificates", "papers", "announcements")
# Existing policy kept: deleting blog articles is reserved for Admin and Superadmin.
_BLOG_EDITOR_GRANTS = ("blogs.view", "blogs.create", "blogs.update", "blogs.publish", "blogs.unpublish")

ORDINARY_CMS_ROLES = ("cms_user", "operations", "papers", "notice", "blog")

ROLE_DEFINITIONS = {
    "superadmin": {
        "label": "Superadmin",
        "description": "Full system access, including account management.",
        "grants": ["*"],
    },
    "admin": {
        "label": "Admin",
        "description": "Full content management and activity logs; no account management.",
        "grants": ["dashboard.all", "media.all", *(f"{m}.all" for m in _CONTENT_MODULES),
                   "activity_logs.view", "admin_access.view", "admin_access.change_own_password",
                   "notifications.view", "notifications.send"],
    },
    "cms_user": {
        "label": "CMS User",
        "description": "Tenures, members, alumni, events, notices, blogs, mentors, certificates, past papers and announcements.",
        "grants": ["dashboard.all", "media.all", *(f"{m}.all" for m in _CONTENT_MODULES if m != "blogs"),
                   *_BLOG_EDITOR_GRANTS, "notifications.view", "notifications.send"],
    },
    "operations": {
        "label": "Operations",
        "description": "Events, notices, certificates, past papers, mentors, announcements and notifications.",
        "grants": ["dashboard.all", "media.all", "events.all", "notices.all", "certificates.all",
                   "papers.all", "mentors.all", "announcements.all"],
    },
    "papers": {
        "label": "Past Papers Manager",
        "description": "Past papers only.",
        "grants": ["dashboard.all", "papers.all"],
    },
    "notice": {
        "label": "Notices Manager",
        "description": "Notices only, including publishing.",
        "grants": ["dashboard.all", "media.all", "notices.all"],
    },
    "blog": {
        "label": "Blog Editor",
        "description": "Blogs only, including publishing.",
        "grants": ["dashboard.all", "media.all", *_BLOG_EDITOR_GRANTS],
    },
}


ROLES = list(ROLE_DEFINITIONS.keys())


def _expand_grants(role):
    grants = ROLE_DEFINITIONS.get(role, {}).get("grants", [])
    expanded = set()
    for grant in grants:
        if grant == "*":
            expanded |= ALL_PERMISSIONS
        elif grant.endswith(".all"):
            module = grant[: -len(".all")]
            # `.all` expands only to registered *normal* permissions of the module.
            expanded |= {
                f"{module}.{a}" for a in PERMISSION_CATALOG.get(module, {}).get("actions", [])
                if f"{module}.{a}" not in PROTECTED_PERMISSIONS
            }
        elif grant in ALL_PERMISSIONS:
            expanded.add(grant)
    # Protected permissions survive only for roles explicitly listed for them.
    return frozenset(p for p in expanded if p not in PROTECTED_PERMISSIONS or role in PROTECTED_PERMISSIONS[p])


ROLE_PERMISSIONS = {role: _expand_grants(role) for role in ROLE_DEFINITIONS}


def effective_role(user):
    """The RBAC role of a user; Django superusers are treated as superadmin."""
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "is_superuser", False):
        return "superadmin"
    role = getattr(user, "role", None)
    return role if role in ROLE_DEFINITIONS else None


def role_label(role):
    return ROLE_DEFINITIONS.get(role, {}).get("label", role or "")


def has_permission(role, permission):
    """Exact permission check for a role."""
    if permission not in ALL_PERMISSIONS or role not in ROLE_PERMISSIONS:
        return False
    if permission in PROTECTED_PERMISSIONS and role not in PROTECTED_PERMISSIONS[permission]:
        return False
    return permission in ROLE_PERMISSIONS[role]


def user_has_permission(user, permission):
    return has_permission(effective_role(user), permission)


def user_permissions(user):
    return sorted(ROLE_PERMISSIONS.get(effective_role(user), ()))


# Legacy names kept so older call sites (and tests) keep working.
_LEGACY_MODULES = {"tenure": "tenures"}
_LEGACY_ACTIONS = {"edit": "update", "all": None}
_LEGACY_PERMISSIONS = {("tenure", "member_delete"): "members.delete"}


def normalize_permission(module, action):
    if (module, action) in _LEGACY_PERMISSIONS:
        return _LEGACY_PERMISSIONS[(module, action)]
    module = _LEGACY_MODULES.get(module, module)
    action = _LEGACY_ACTIONS.get(action, action)
    return f"{module}.{action}" if action else None


def has_role_permission(role, module, action, is_superuser=False):
    """Backwards-compatible (role, module, action) check using exact matching."""
    permission = normalize_permission(module, action)
    if permission is None:
        return False
    return has_permission("superadmin" if is_superuser else role, permission)


# --------------------------------------------------------------------------
# DRF permission classes
# --------------------------------------------------------------------------
METHOD_ACTIONS = {"GET": "view", "HEAD": "view", "OPTIONS": "view", "POST": "create",
                  "PUT": "update", "PATCH": "update", "DELETE": "delete"}


class HasModulePermission(BasePermission):
    """
    Maps the HTTP method to a module action and checks it exactly.
    Views may override via ``get_permission_action(request)`` or
    ``delete_permission_action`` / ``permission_actions`` ({method: action}).
    """
    module = None
    message = "You do not have permission to perform this action."

    def __init__(self, module=None, action=None):
        if module:
            self.module = module
        self.action = action

    def __call__(self):
        return self

    def _action(self, request, view):
        if self.action:
            return self.action
        method = request.method.upper()
        if hasattr(view, "get_permission_action"):
            return view.get_permission_action(request)
        actions = getattr(view, "permission_actions", None) or {}
        if method in actions:
            return actions[method]
        if method == "DELETE" and hasattr(view, "delete_permission_action"):
            return view.delete_permission_action
        return METHOD_ACTIONS.get(method, method.lower())

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        module = self.module or getattr(view, "permission_module", None)
        if not module:
            return False  # fail closed: every protected view must declare its module
        action = self._action(request, view)
        permission = normalize_permission(module, action)
        allowed = bool(permission) and user_has_permission(request.user, permission)
        if not allowed:
            if permission == "members.delete":
                self.message = "Only Superadmin can delete members."
            elif permission and permission.startswith("accounts."):
                self.message = "Only Superadmin can manage administrative accounts."
            else:
                self.message = f"You do not have permission to perform {action} on {module}."
        return allowed


class HasPermission(BasePermission):
    """Require one exact permission, e.g. ``HasPermission("activity_logs.view")``."""

    def __init__(self, permission):
        self.permission = permission
        self.message = f"You do not have the '{permission}' permission."

    def __call__(self):
        return self

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and user_has_permission(request.user, self.permission))


class IsSuperadminOnly(BasePermission):
    """Account management: superadmins (and Django superusers) only."""

    def has_permission(self, request, view):
        return user_has_permission(request.user, "accounts.manage")


class CanManageAccounts(BasePermission):
    """
    Administrative account management:
    - Superadmin: can manage regular Admins and ordinary CMS users.
    - Admin: can manage ordinary CMS users.
    - Ordinary CMS users / unauthenticated: denied.
    """
    message = "You do not have permission to manage accounts."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return effective_role(request.user) in ("superadmin", "admin")


class CanViewActivityLogs(BasePermission):
    def has_permission(self, request, view):
        return user_has_permission(request.user, "activity_logs.view")


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return effective_role(request.user) in ("admin", "superadmin")


class IsCMSUser(BasePermission):
    def has_permission(self, request, view):
        return effective_role(request.user) in ("admin", "superadmin", "cms_user")


def can_view_module(user, module):
    """Whether the user may see unpublished/protected records of a module."""
    return user_has_permission(user, f"{module}.view")
