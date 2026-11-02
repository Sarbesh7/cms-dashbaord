from django.urls import path
from .views import (
    DeviceTokenListCreateView,
    DeviceTokenStatusView,
    DeviceTokenDetailView,
    PushDeviceRegisterView,
    PushDeviceUnregisterView,
    NotificationHistoryListView,
    NotificationHistoryDetailView,
    NotificationRetryView,
)


urlpatterns = [
    # Mobile app compatibility routes (drop-in replacement for Strapi /api/push-devices/*)
    path('api/push-devices/register', PushDeviceRegisterView.as_view(), name='push-device-register'),
    path('api/push-devices/register/', PushDeviceRegisterView.as_view(), name='push-device-register-slash'),
    path('api/push-devices/unregister', PushDeviceUnregisterView.as_view(), name='push-device-unregister'),
    path('api/push-devices/unregister/', PushDeviceUnregisterView.as_view(), name='push-device-unregister-slash'),

    # Administrative & API v1 routes
    path('api/v1/device-tokens/', DeviceTokenListCreateView.as_view(), name='device-token-list-create'),
    path('api/v1/device-tokens/<int:pk>/status/', DeviceTokenStatusView.as_view(), name='device-token-status'),
    path('api/v1/device-tokens/<int:pk>/', DeviceTokenDetailView.as_view(), name='device-token-detail'),

    # Notification History & Retries
    path('api/v1/notifications/', NotificationHistoryListView.as_view(), name='notification-history-list'),
    path('api/v1/notifications/<int:pk>/', NotificationHistoryDetailView.as_view(), name='notification-history-detail'),
    path('api/v1/notifications/<int:pk>/retry/', NotificationRetryView.as_view(), name='notification-history-retry'),
]


