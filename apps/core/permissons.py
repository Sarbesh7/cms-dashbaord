from rest_framework.permissions import BasePermission
from .models import BaseModel
from apps.users.models import User

# yo chae hamro core bhayo yaha chae sab thau ma common use hune lekhxan jasto ki base models models.py ma  pagiantion permission haru etc.haii tw 

class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == UserRoles.Admin or request.user.is_superuser)    
        
        
class IsCMSManagerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in [
                UserRoles.Admin or request.user.is_superuser,
                UserRoles.CMS_MANAGER
            ]
        )