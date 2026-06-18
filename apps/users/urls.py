from django.urls import path
from .views import LoginView,UserView,ChangePasswordView,LogoutView,ResetPasswordView


urlpatterns = [
    path('api/v1/login/',LoginView.as_view()),
    path('api/v1/users/',UserView.as_view()),
    path('api/v1/users/change-password/',ChangePasswordView.as_view()),
    path('api/v1/user/logout/',LoginView.as_view()),
    path('api/v1/users/reset-password/',ResetPasswordView.as_view()),
]
