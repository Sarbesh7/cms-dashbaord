from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
 def has_permission(self, request, view):
  return (
   request.user.is_authenticated and
   request.user.role =='admin'
  )
 

class IsCMSUser(BasePermission):
 def has_permission(self, request, view):
  return (
   request.user.is_authenticated and
   request.user.role in [
    'admin','cms_user'
    ]
  )
