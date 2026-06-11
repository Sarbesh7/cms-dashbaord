from django.urls import path
from .views import EventListView,EventDetailsView


urlpatterns = [
    path('api/v1/events/',EventListView.as_view()),
    path('api/v1/events/<slug:slug>/',EventDetailsView.as_view()),
]