import os

from rest_framework import serializers

IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "gif", "avif")
MAX_UPLOAD_SIZE = 5 * 1024 * 1024


def validate_upload(value, allowed_extensions, label="File"):
    """Allowlist extensions so uploads cannot be active content (HTML, SVG, JS)."""
    if value is None or not hasattr(value, "name"):
        return value
    ext = os.path.splitext(value.name)[1].lower().lstrip(".")
    if ext not in allowed_extensions:
        raise serializers.ValidationError(
            f"Unsupported file type .{ext or '?'}. Allowed: {', '.join(allowed_extensions)}."
        )
    if getattr(value, "size", 0) > MAX_UPLOAD_SIZE:
        raise serializers.ValidationError(f"{label} cannot exceed 5MB.")
    return value
