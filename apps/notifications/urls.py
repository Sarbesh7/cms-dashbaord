from django.urls import path
from .views import (
    NotificationInboxListView,
    NotificationUnreadCountView,
    NotificationMarkAllReadView,
    NotificationToggleReadView,
    NotificationComposeView,
    NotificationSentListView,
    EligibleRecipientsListView,
)

urlpatterns = [
    # In-App User Notifications (Role-based for superadmin, admin, cms_user)
    path('api/v1/notifications/', NotificationInboxListView.as_view(), name='notification-inbox'),
    path('api/v1/notifications/unread-count/', NotificationUnreadCountView.as_view(), name='notification-unread-count'),
    path('api/v1/notifications/mark-all-read/', NotificationMarkAllReadView.as_view(), name='notification-mark-all-read'),
    path('api/v1/notifications/<int:pk>/read/', NotificationToggleReadView.as_view(), name='notification-toggle-read'),
    path('api/v1/notifications/compose/', NotificationComposeView.as_view(), name='notification-compose'),
    path('api/v1/notifications/sent/', NotificationSentListView.as_view(), name='notification-sent-list'),
    path('api/v1/notifications/recipients/', EligibleRecipientsListView.as_view(), name='notification-eligible-recipients'),
]
