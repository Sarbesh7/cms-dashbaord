from django.urls import path
from rest_framework_simplejwt.views import (TokenObtainPairView,TokenRefreshView)
from .views import LoginView,UserView


urlpatterns = [
    path('api/login/',LoginView.as_view()),
    path('api/token/',TokenObtainPairView.as_view(),name='token_obtain_pair'),
    path('api/token/refresh/',TokenRefreshView.as_view(),name='refresh_token'),
    path('api/users/',UserView.as_view()),
]
