from django.urls import path
from .views import (
    LoginView, UserView, ChangePasswordView,
    UserDetailView, RefreshTokenView, LogoutView,
    AccountListCreateView, AccountDetailView,
    UserMeView, RoleListView,
)

urlpatterns = [
    path('api/v1/login/', LoginView.as_view()),
    path('api/v1/users/me/', UserMeView.as_view(), name='user-me'),
    path('api/v1/users/roles/', RoleListView.as_view(), name='user-roles'),
    path('api/v1/users/', UserView.as_view()),
    path('api/v1/users/<int:user_id>/', UserDetailView.as_view()),
    path('api/v1/users/accounts/', AccountListCreateView.as_view()),
    path('api/v1/users/accounts/<int:user_id>/', AccountDetailView.as_view()),
    path('api/v1/users/change-password/', ChangePasswordView.as_view()),
    path("api/v1/users/logout/", LogoutView.as_view()),
    path("api/v1/users/refresh-token/", RefreshTokenView.as_view()),
]
