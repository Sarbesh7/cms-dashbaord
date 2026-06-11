from django.urls import path
from .views import PastPaperListView, PastPaperDetailView


urlpatterns = [
    path('api/v1/past-papers/', PastPaperListView.as_view()),
    path('api/v1/past-papers/<int:pk>/', PastPaperDetailView.as_view()),
    
]