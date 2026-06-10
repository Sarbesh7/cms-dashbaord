from django.urls import path
from .views import LoginView,UserView,ChangePasswordView


urlpatterns = [
    path('api/login/',LoginView.as_view()),
    path('api/users/',UserView.as_view()),
    path('api/users/change-password/',ChangePasswordView.as_view())
]
