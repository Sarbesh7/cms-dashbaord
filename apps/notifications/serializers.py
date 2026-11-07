from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.core.permissions import effective_role, role_label
from .models import Notification, NotificationRecipient, NotificationSource
from .permissions import ELIGIBLE_NOTIFICATION_ROLES

User = get_user_model()


class SenderSummarySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    role_label = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'name', 'role', 'role_label']

    def get_name(self, obj):
        full = f"{obj.first_name} {obj.last_name}".strip()
        return full or obj.username

    def get_role(self, obj):
        return effective_role(obj)

    def get_role_label(self, obj):
        return role_label(effective_role(obj))


class EligibleRecipientSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    role_label = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'name', 'role', 'role_label']

    def get_name(self, obj):
        full = f"{obj.first_name} {obj.last_name}".strip()
        return full or obj.username

    def get_role(self, obj):
        return effective_role(obj)

    def get_role_label(self, obj):
        return role_label(effective_role(obj))


class NotificationRecipientInboxSerializer(serializers.ModelSerializer):
    """
    Represents a received notification in the current user's inbox.
    Includes the notification payload, sender summary, and recipient read status.
    """
    notification_id = serializers.IntegerField(source='notification.id', read_only=True)
    title = serializers.CharField(source='notification.title', read_only=True)
    message = serializers.CharField(source='notification.message', read_only=True)
    source_module = serializers.CharField(source='notification.source_module', read_only=True)
    source_id = serializers.CharField(source='notification.source_id', read_only=True)
    data = serializers.JSONField(source='notification.data', read_only=True)
    sender = SenderSummarySerializer(source='notification.sender', read_only=True)
    sent_at = serializers.DateTimeField(source='notification.created_at', read_only=True)

    class Meta:
        model = NotificationRecipient
        fields = [
            'id',
            'notification_id',
            'title',
            'message',
            'source_module',
            'source_id',
            'data',
            'sender',
            'sent_at',
            'is_read',
            'read_at',
            'created_at',
        ]


class NotificationRecipientSummarySerializer(serializers.ModelSerializer):
    recipient = SenderSummarySerializer(read_only=True)

    class Meta:
        model = NotificationRecipient
        fields = ['id', 'recipient', 'is_read', 'read_at', 'created_at']


class NotificationSentSerializer(serializers.ModelSerializer):
    """
    Represents a notification authored and sent by the current user.
    """
    recipients = NotificationRecipientSummarySerializer(many=True, read_only=True)
    recipient_count = serializers.IntegerField(source='recipients.count', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id',
            'title',
            'message',
            'source_module',
            'source_id',
            'data',
            'created_at',
            'recipient_count',
            'recipients',
        ]


class NotificationComposeSerializer(serializers.Serializer):
    """
    Validates manual composition and dispatch of an in-app notification.
    """
    title = serializers.CharField(
        max_length=255,
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            'required': 'Notification title is required.',
            'blank': 'Notification title cannot be blank.',
        }
    )
    message = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            'required': 'Notification message is required.',
            'blank': 'Notification message cannot be blank.',
        }
    )
    all_eligible = serializers.BooleanField(default=False)
    recipient_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        default=list
    )

    def validate(self, attrs):
        all_eligible = attrs.get('all_eligible', False)
        recipient_ids = attrs.get('recipient_ids', [])

        if not all_eligible and not recipient_ids:
            raise serializers.ValidationError({
                'recipient_ids': 'Select at least one recipient or select All Eligible Users.'
            })

        request = self.context.get('request')
        sender = getattr(request, 'user', None)

        if all_eligible:
            eligible_qs = User.objects.filter(
                is_active=True,
                role__in=ELIGIBLE_NOTIFICATION_ROLES
            )
            if sender:
                eligible_qs = eligible_qs.exclude(id=sender.id)
            attrs['resolved_recipients'] = list(eligible_qs)
            if not attrs['resolved_recipients']:
                raise serializers.ValidationError({
                    'recipient_ids': 'No other eligible recipients found to receive this notification.'
                })
        else:
            recipients = list(User.objects.filter(id__in=recipient_ids, is_active=True))
            found_ids = {r.id for r in recipients}
            missing_ids = set(recipient_ids) - found_ids
            if missing_ids:
                raise serializers.ValidationError({
                    'recipient_ids': f'One or more recipient users not found: {list(missing_ids)}'
                })

            ineligible = [r for r in recipients if effective_role(r) not in ELIGIBLE_NOTIFICATION_ROLES]
            if ineligible:
                ineligible_names = [r.username for r in ineligible]
                raise serializers.ValidationError({
                    'recipient_ids': f'The following users are not eligible to receive notifications: {ineligible_names}'
                })

            attrs['resolved_recipients'] = recipients

        return attrs
