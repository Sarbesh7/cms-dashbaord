from django.urls import path
from .views import RegisterView,LoginView,TestView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)


urlpatterns = [
    path('api/register/',RegisterView.as_view()),
    path('api/login/',LoginView.as_view()),
    path('test/',TestView.as_view()),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
]
