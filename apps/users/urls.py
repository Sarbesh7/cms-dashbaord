from django.urls import path
from .views import LoginView,UserView,ChangePasswordView


urlpatterns = [
    path('api/v1/login/',LoginView.as_view()),
    path('api/v1/users/',UserView.as_view()),
    path('api/users/change-password/',ChangePasswordView.as_view())
]
