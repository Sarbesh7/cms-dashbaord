from django.urls import path
from .views import (
    CertificateListView, CertificateDetailView, CertificateTemplateListView, CertificateTemplateDetailView,
    CertificateVerifyView,
)


urlpatterns = [
    path('api/v1/certificates/', CertificateListView.as_view()),
    # Public: verify one certificate by exact UUID (malformed IDs get a 400, not a 404 page).
    path('api/v1/certificates/verify/<str:certificate_id>/', CertificateVerifyView.as_view(), name='certificate-verify'),
    path('api/v1/certificates/<uuid:certificate_id>/', CertificateDetailView.as_view()),
    path('api/v1/certificates/templates/', CertificateTemplateListView.as_view()),
    path('api/v1/certificates/templates/<int:pk>/', CertificateTemplateDetailView.as_view()),
]
