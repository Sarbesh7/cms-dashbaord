from django.urls import path
from .views import CertificateListView, CertificateDetailView, CertificateTemplateListView, CertificateTemplateDetailView


urlpatterns = [
    path('api/certificates/', CertificateListView.as_view()),
    path('api/certificates/<int:pk>/', CertificateDetailView.as_view()),    
    path('api/certificates/templates/', CertificateTemplateListView.as_view()),
    path('api/certificates/templates/<int:pk>/', CertificateTemplateDetailView.as_view()),
    
]
