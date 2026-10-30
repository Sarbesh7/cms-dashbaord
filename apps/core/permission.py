from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and (
                request.user.role in ['admin', 'superadmin']
                or request.user.is_superuser
            )
        )


class IsCMSUser(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and (
                request.user.role in ['admin', 'superadmin', 'cms_user']
                or request.user.is_superuser
            )
        )
