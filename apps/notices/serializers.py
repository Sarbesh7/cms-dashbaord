from rest_framework import serializers
from . import models


class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Notice
        fields = ["id", "title", "content", "created_at", "updated_at", "image"]

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

    def create(self, validated_data):

        return models.Notice.objects.create(**validated_data)

    def update(self, instance, validated_data):

        instance.title = validated_data.get("title", instance.title)
        instance.content = validated_data.get("content", instance.content)

        if "image" in validated_data:
            instance.image = validated_data.get("image", instance.image)

        instance.save()
        return instance
