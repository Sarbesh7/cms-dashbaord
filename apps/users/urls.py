from django.urls import path
from .views import LoginView,UserView


urlpatterns = [
    path('api/v1/login/',LoginView.as_view()),
    path('api/v1/users/',UserView.as_view()),
]
