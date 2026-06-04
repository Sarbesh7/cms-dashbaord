from django.urls import path
from .views import NoticeListView, NoticeDetailView


urlpatterns = [
    path('api/notices/', NoticeListView.as_view()),
    path('api/notices/<int:pk>/', NoticeDetailView.as_view()),
]
