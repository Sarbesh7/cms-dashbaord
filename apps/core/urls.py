from django.urls import path
from .views import DashboardStatsView

urlpatterns = [
    path('api/v1/dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
]
