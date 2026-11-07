from rest_framework.permissions import BasePermission
from apps.core.permissions import effective_role

ELIGIBLE_NOTIFICATION_ROLES = frozenset({"superadmin", "admin", "cms_user"})


class IsEligibleNotificationUser(BasePermission):
    """
    Allows access exclusively to authenticated users with roles:
    Superadmin, Admin, or CMS User.
    All three roles have equal access to send, view, and manage in-app notifications.
    """
    message = "You do not have permission to access notifications."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return effective_role(user) in ELIGIBLE_NOTIFICATION_ROLES

