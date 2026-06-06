from rest_framework.permissions import BasePermission
from .models import BaseModel
from apps.users.models import User


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == UserRoles.SUPER_ADMIN
        )    
        
        
class IsCMSManagerOrAdmin(BasePermission):

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in [
                UserRoles.SUPER_ADMIN,
                UserRoles.CMS_MANAGER
            ]
        )