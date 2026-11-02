from django.urls import path
from .views import AnnouncementDetailView, AnnouncementListView

urlpatterns = [
    # Canonical v1 API routes
    path('api/v1/announcements/', AnnouncementListView.as_view(), name='announcement-list'),
    path('api/v1/announcements/<int:pk>/', AnnouncementDetailView.as_view(), name='announcement-detail'),
    # Backward-compatible legacy aliases
    path('announcements/', AnnouncementListView.as_view(), name='announcement-list-legacy'),
    path('announcements/<int:pk>/', AnnouncementDetailView.as_view(), name='announcement-detail-legacy'),
]
