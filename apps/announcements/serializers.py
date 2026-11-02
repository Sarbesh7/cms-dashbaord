from rest_framework import serializers
from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = [
            'id',
            'title',
            'description',
            'image',
            'link',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_title(self, value):
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Title is required.")
        return cleaned

    def validate_description(self, value):
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Description is required.")
        return cleaned

    def validate_link(self, value):
        if value:
            cleaned = value.strip()
            if cleaned and not (cleaned.startswith("http://") or cleaned.startswith("https://")):
                raise serializers.ValidationError("Link must start with http:// or https://")
            return cleaned
        return value
