from django.urls import path
from .views import PastPaperListView, PastPaperDetailView


urlpatterns = [
    path('api/past-papers/', PastPaperListView.as_view()),
    path('api/past-papers/<int:pk>/', PastPaperDetailView.as_view()),
    
]