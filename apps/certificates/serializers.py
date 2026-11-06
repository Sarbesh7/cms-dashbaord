from apps.core.uploads import IMAGE_EXTENSIONS, validate_upload
from . import models
from rest_framework import serializers

class CertificateTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CertificateTemplate
        fields = ['id', 'template_name', 'template_file']

    def validate_template_file(self, value):
        return validate_upload(value, IMAGE_EXTENSIONS + ("pdf",), "Certificate template")
        
class CertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Certificate
        fields = ['id', 'certificate_id', 'full_name', 'event', 'event_title', 'is_project_completed', 'issued_at']
        read_only_fields = ['event_title']


class CertificateVerificationSerializer(serializers.ModelSerializer):
    """Minimal public view of one certificate (no internal IDs or storage details)."""
    event_title = serializers.SerializerMethodField()

    class Meta:
        model = models.Certificate
        fields = ['certificate_id', 'full_name', 'event_title', 'is_project_completed', 'issued_at']
        read_only_fields = fields

    def get_event_title(self, obj):
        return obj.event_title or (obj.event.title if obj.event_id else "")


class BulkStatusSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        error_messages={'min_length': 'At least one certificate ID is required.'}
    )
    is_project_completed = serializers.BooleanField()
