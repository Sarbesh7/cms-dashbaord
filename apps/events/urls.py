from django.urls import path
from .views import EventView,EventDetailsView


urlpatterns = [
    path('api/events/',EventView.as_view()),
    path('api/events/<int:id>/',EventDetailsView.as_view()),
]