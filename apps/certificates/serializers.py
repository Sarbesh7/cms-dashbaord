from . import models
from rest_framework import serializers

class CertificateTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CertificateTemplate
        fields = ['id', 'template_name', 'template_file']
        
class CertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Certificate
        fields = ['certificate_id', 'full_name', 'event', 'issued_at']
