

from django.urls import path
from .views import (
    EventListView,
    EventDetailsView,
    MentorListView,
    MentorDetailsView,
)

urlpatterns = [
    # Event endpoints
    path('api/v1/events/', EventListView.as_view(), name='event-list'),
    path('api/v1/events/<str:slug>/', EventDetailsView.as_view(), name='event-detail'),

    # Mentor endpoints
    path('api/v1/mentors/', MentorListView.as_view(), name='mentor-list'),
    path('api/v1/mentors/<int:identifier>/', MentorDetailsView.as_view(), name='mentor-detail'),
]