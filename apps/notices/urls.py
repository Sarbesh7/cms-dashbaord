from django.urls import path
from .views import NoticeListView, NoticeDetailView


urlpatterns = [
    path('api/v1/notices/', NoticeListView.as_view()),
    path('api/v1/notices/<slug:slug>/', NoticeDetailView.as_view()),
]
