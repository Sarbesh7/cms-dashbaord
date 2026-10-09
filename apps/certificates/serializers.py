from . import models
from rest_framework import serializers

class CertificateTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CertificateTemplate
        fields = ['id', 'template_name', 'template_file']
        
class CertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Certificate
        fields = ['id', 'certificate_id', 'full_name', 'event', 'is_project_completed', 'issued_at']


class BulkStatusSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        error_messages={'min_length': 'At least one certificate ID is required.'}
    )
    is_project_completed = serializers.BooleanField()
