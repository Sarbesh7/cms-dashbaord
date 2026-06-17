from django.urls import path
from .views import EventListView,EventDetailsView,MentorListView,MentorDetailsView


urlpatterns = [
    path('api/v1/events/',EventListView.as_view()),
    path('api/v1/events/<slug:slug>/',EventDetailsView.as_view()),
    path('api/v1/mentors/',MentorListView.as_view()),
    path('api/v1/mentors/<slug:slug>/',MentorDetailsView.as_view()),
]