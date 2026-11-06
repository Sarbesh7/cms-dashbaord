from rest_framework import serializers

from apps.core.permissions import role_label
from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    role_label = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = [
            'id',
            'user',
            'user_name',
            'actor_id_snapshot',
            'actor_name_snapshot',
            'user_email_snapshot',
            'user_role_snapshot',
            'role_label',
            'action',
            'module',
            'target_id',
            'target_repr',
            'description',
            'changes',
            'details',
            'ip_address',
            'user_agent',
            'timestamp',
        ]
        read_only_fields = fields

    def get_user_name(self, obj):
        # Snapshot first: it stays correct even after the account is renamed or deleted.
        return obj.actor_name_snapshot or obj.user_email_snapshot or "System"

    def get_role_label(self, obj):
        return role_label(obj.user_role_snapshot) if obj.user_role_snapshot else ""
