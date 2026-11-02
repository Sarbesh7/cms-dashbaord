from rest_framework import serializers
from .models import DeviceToken


class DeviceTokenSerializer(serializers.ModelSerializer):
    """Safe read serializer for device tokens. Protects raw tokens by displaying only masked previews."""
    masked_token = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(source='user.id', read_only=True, allow_null=True)
    username = serializers.CharField(source='user.username', read_only=True, allow_null=True)

    class Meta:
        model = DeviceToken
        fields = [
            'id',
            'platform',
            'enabled',
            'masked_token',
            'user_id',
            'username',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_masked_token(self, obj):
        token = obj.token or ""
        if len(token) > 16:
            return f"{token[:8]}...{token[-6:]}"
        elif len(token) > 6:
            return f"{token[:3]}...{token[-3:]}"
        return "***"


class DeviceTokenRegistrationSerializer(serializers.Serializer):
    """Validates registration or refresh of a device push token."""
    token = serializers.CharField(
        max_length=512,
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            'required': 'Push notification device token is required.',
            'blank': 'Push notification device token cannot be blank.',
        }
    )
    platform = serializers.CharField(
        max_length=20,
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            'required': 'Device platform is required.',
            'blank': 'Device platform cannot be blank.',
        }
    )

    def validate_platform(self, value):
        normalized = (value or "").strip().lower()
        valid_platforms = [c[0] for c in DeviceToken.Platform.choices]
        if normalized not in valid_platforms:
            raise serializers.ValidationError(
                f"Unsupported platform '{value}'. Supported platforms: {', '.join(valid_platforms)}."
            )
        return normalized

    def save(self, user=None):
        token = self.validated_data['token']
        platform = self.validated_data['platform']

        # Idempotent registration with safe token reassignment
        device_token, created = DeviceToken.objects.get_or_create(
            token=token,
            defaults={
                'platform': platform,
                'enabled': True,
                'user': user,
            }
        )

        if not created:
            device_token.platform = platform
            device_token.user = user
            device_token.enabled = True
            device_token.save(update_fields=['platform', 'user', 'enabled', 'updated_at'])

        return device_token, created


class DeviceTokenStatusSerializer(serializers.Serializer):
    """Strictly validates updates to notification delivery status (enabled/disabled only)."""
    enabled = serializers.BooleanField(
        required=True,
        error_messages={
            'required': 'The enabled field is required.',
            'invalid': 'The enabled field must be a valid boolean (true or false).',
        }
    )

    def update(self, instance, validated_data):
        instance.enabled = validated_data['enabled']
        instance.save(update_fields=['enabled', 'updated_at'])
        return instance


class DeviceTokenUpdateSerializer(serializers.ModelSerializer):
    """Allows updating device token value or platform when refreshed by client provider."""
    token = serializers.CharField(max_length=512, required=False, allow_blank=False, trim_whitespace=True)
    platform = serializers.CharField(max_length=20, required=False, allow_blank=False, trim_whitespace=True)

    class Meta:
        model = DeviceToken
        fields = ['token', 'platform']

    def validate_platform(self, value):
        if value:
            normalized = value.strip().lower()
            valid_platforms = [c[0] for c in DeviceToken.Platform.choices]
            if normalized not in valid_platforms:
                raise serializers.ValidationError(
                    f"Unsupported platform '{value}'. Supported platforms: {', '.join(valid_platforms)}."
                )
            return normalized
        return value

    def validate_token(self, value):
        if value:
            existing = DeviceToken.objects.filter(token=value).exclude(pk=self.instance.pk).first()
            if existing:
                raise serializers.ValidationError("This device token is already registered to another record.")
        return value


class PushDeviceRegisterSerializer(serializers.Serializer):
    """Validates public mobile app Expo push token registration request."""
    token = serializers.CharField(
        max_length=512,
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            'required': 'Push token is required',
            'blank': 'Push token is required',
        }
    )
    platform = serializers.CharField(
        max_length=20,
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            'required': 'Platform must be android or ios',
            'blank': 'Platform must be android or ios',
        }
    )

    def validate_token(self, value):
        token_str = (value or "").strip()
        if not (token_str.startswith('ExponentPushToken[') or token_str.startswith('ExpoPushToken[')):
            raise serializers.ValidationError("Invalid Expo push token")
        return token_str

    def validate_platform(self, value):
        normalized = (value or "").strip().lower()
        if normalized not in ['android', 'ios']:
            raise serializers.ValidationError("Platform must be android or ios")
        return normalized


class PushDeviceUnregisterSerializer(serializers.Serializer):
    """Validates public mobile app Expo push token unregistration request."""
    token = serializers.CharField(
        max_length=512,
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            'required': 'Push token is required',
            'blank': 'Push token is required',
        }
    )


class NotificationAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import NotificationAttempt
        model = NotificationAttempt
        fields = [
            'id',
            'attempt_number',
            'targeted_count',
            'accepted_count',
            'failed_count',
            'status',
            'error_summary',
            'created_at',
        ]
        read_only_fields = fields


class NotificationHistorySerializer(serializers.ModelSerializer):
    attempts = NotificationAttemptSerializer(many=True, read_only=True)

    class Meta:
        from .models import NotificationHistory
        model = NotificationHistory
        fields = [
            'id',
            'source_module',
            'source_id',
            'source_title',
            'title',
            'body',
            'data',
            'status',
            'total_devices',
            'accepted_count',
            'failed_count',
            'retry_count',
            'error_summary',
            'created_at',
            'updated_at',
            'attempts',
        ]
        read_only_fields = fields


