from django.urls import path
from .views import NoticeListView, NoticeDetailView


urlpatterns = [
    path('api/notices/', NoticeListView.as_view()),
    path('api/notices/<slug:slug>/', NoticeDetailView.as_view()),
]
