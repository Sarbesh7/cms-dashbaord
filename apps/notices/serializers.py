from rest_framework import serializers
from . import models


class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Notice
        fields = "__all__"

    def validate_image(self, value):
        if value is not None:

            max_size = 5 * 1024 * 1024  # 5 Megabytes
            if value.size > max_size:
                raise serializers.ValidationError("Image size cannot exceed 5MB.")

            valid_extensions = ["jpg", "jpeg", "png", "webp"]
            extension = value.name.split(".")[-1].lower()
            if extension not in valid_extensions:
                raise serializers.ValidationError(
                    f"Unsupported file extension .{extension}. Supported types: {', '.join(valid_extensions)}"
                )

        return value
