from django.urls import path
from .views import EvenListtView,EventDetailsView


urlpatterns = [
    path('api/events/',EvenListtView.as_view()),
    path('api/events/<slug:slug>/',EventDetailsView.as_view()),
]