from django.urls import path
from .views import CertificateListView, CertificateDetailView, CertificateTemplateListView, CertificateTemplateDetailView


urlpatterns = [
    path('api/v1/certificates/', CertificateListView.as_view()),
    path('api/v1/certificates/<int:pk>/', CertificateDetailView.as_view()),    
    path('api/v1/certificates/templates/', CertificateTemplateListView.as_view()),
    path('api/v1/certificates/templates/<int:pk>/', CertificateTemplateDetailView.as_view()),
    
]
