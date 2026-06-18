from django.urls import path
from .views import LoginView,UserView,ChangePasswordView,LogoutView,ResetPasswordView
from .views import LoginView,UserView,ChangePasswordView,TestEmailView,ForgotPasswordView,ResetPasswordView


urlpatterns = [
    path('api/v1/login/',LoginView.as_view()),
    path('api/v1/users/',UserView.as_view()),
    path('api/v1/users/change-password/',ChangePasswordView.as_view()),
    path("api/v1/test-email/", TestEmailView.as_view()),
    path("api/v1/users/forgot-password/", ForgotPasswordView.as_view()),
    path("api/v1/users/reset-password/", ResetPasswordView.as_view()),
     
     

]
