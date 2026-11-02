from django.urls import path
from .views import (
    DashboardOverviewView,
    ActivityLogListView,
    ActivityLogSummaryView,
    ActivityLogDetailView,
    MediaUsageView,
    MediaDeleteView,
)

urlpatterns = [
    path('api/v1/dashboard/overview/', DashboardOverviewView.as_view(), name='dashboard-overview'),
    # Legacy alias kept for compatibility; serves the same role-aware overview.
    path('api/v1/dashboard/stats/', DashboardOverviewView.as_view(), name='dashboard-stats'),
    path('api/v1/activity-logs/', ActivityLogListView.as_view(), name='activity-logs-list'),
    path('api/v1/activity-logs/summary/', ActivityLogSummaryView.as_view(), name='activity-logs-summary'),
    path('api/v1/activity-logs/<int:pk>/', ActivityLogDetailView.as_view(), name='activity-logs-detail'),
    path('api/v1/media/usage/', MediaUsageView.as_view(), name='media-usage'),
    path('api/v1/media/delete/', MediaDeleteView.as_view(), name='media-delete'),
]
