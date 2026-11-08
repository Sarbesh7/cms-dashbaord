from rest_framework import serializers

from apps.core.permissions import role_label
from apps.core.user_agent import parse_user_agent
from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    role_label = serializers.SerializerMethodField()
    actor_id = serializers.SerializerMethodField()
    actor_sys_id = serializers.SerializerMethodField()
    actor_name = serializers.SerializerMethodField()
    actor_username = serializers.SerializerMethodField()
    actor_email = serializers.SerializerMethodField()
    actor_role = serializers.SerializerMethodField()
    actor_role_label = serializers.SerializerMethodField()
    is_resource_applicable = serializers.SerializerMethodField()
    browser_name = serializers.SerializerMethodField()
    browser_version = serializers.SerializerMethodField()
    os_name = serializers.SerializerMethodField()
    device_type = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = [
            'id',
            'user',
            'user_name',
            'actor_id',
            'actor_sys_id',
            'actor_name',
            'actor_username',
            'actor_email',
            'actor_role',
            'actor_role_label',
            'actor_id_snapshot',
            'actor_sys_id_snapshot',
            'actor_name_snapshot',
            'actor_username_snapshot',
            'user_email_snapshot',
            'user_role_snapshot',
            'role_label',
            'action',
            'module',
            'target_id',
            'target_repr',
            'is_resource_applicable',
            'description',
            'changes',
            'details',
            'ip_address',
            'user_agent',
            'browser_name',
            'browser_version',
            'os_name',
            'device_type',
            'timestamp',
        ]
        read_only_fields = fields

    def _get_ua_info(self, obj):
        if not hasattr(obj, "_ua_cached"):
            obj._ua_cached = parse_user_agent(obj.user_agent)
        return obj._ua_cached

    def get_actor_id(self, obj):
        return obj.actor_id_snapshot or (obj.user.pk if obj.user else None)

    def get_actor_sys_id(self, obj):
        if getattr(obj, 'actor_sys_id_snapshot', ''):
            return obj.actor_sys_id_snapshot
        pk = obj.actor_id_snapshot or (obj.user.pk if obj.user else None)
        if pk is not None:
            return f"SYS-{pk}"
        if obj.user_role_snapshot == "system" or (not obj.user and not obj.user_email_snapshot):
            return "SYS-0"
        return "—"

    def get_actor_name(self, obj):
        if obj.user_role_snapshot == "superadmin" or (obj.user and getattr(obj.user, 'is_superuser', False)) or obj.actor_username_snapshot == "CSITABMC_SUPER":
            return "CSITABMC SUPERADMIN"
        if obj.actor_name_snapshot and obj.actor_name_snapshot != "Name unavailable":
            return obj.actor_name_snapshot
        if obj.user:
            first = (getattr(obj.user, 'first_name', '') or '').strip()
            last = (getattr(obj.user, 'last_name', '') or '').strip()
            name = f"{first} {last}".strip()
            if name:
                return name
        if obj.actor_name_snapshot:
            return obj.actor_name_snapshot
        if not obj.user and not obj.user_email_snapshot:
            return "System"
        return "Name unavailable"

    def get_actor_username(self, obj):
        if obj.user_role_snapshot == "superadmin" or (obj.user and getattr(obj.user, 'is_superuser', False)):
            return "CSITABMC_SUPER"
        if obj.actor_username_snapshot:
            return obj.actor_username_snapshot
        if obj.user and getattr(obj.user, 'username', ''):
            return obj.user.username
        if obj.module == "auth" and obj.action == "failed_login":
            return "anonymous"
        if not obj.user and not obj.user_email_snapshot:
            return "system"
        return ""

    def get_actor_email(self, obj):
        return obj.user_email_snapshot or (getattr(obj.user, 'email', '') if obj.user else "")

    def get_actor_role(self, obj):
        return obj.user_role_snapshot or (getattr(obj.user, 'role', '') if obj.user else "")

    def get_actor_role_label(self, obj):
        role = self.get_actor_role(obj)
        return role_label(role) if role else ""

    def get_user_name(self, obj):
        return self.get_actor_name(obj)

    def get_role_label(self, obj):
        return self.get_actor_role_label(obj)

    def get_is_resource_applicable(self, obj):
        if obj.module == "auth" or obj.action in ("login", "logout", "failed_login", "password_change"):
            return False
        return bool(obj.target_repr or obj.target_id)

    def get_browser_name(self, obj):
        return self._get_ua_info(obj).get("browser_name", "Unknown")

    def get_browser_version(self, obj):
        return self._get_ua_info(obj).get("browser_version", "")

    def get_os_name(self, obj):
        return self._get_ua_info(obj).get("os_name", "Unknown")

    def get_device_type(self, obj):
        return self._get_ua_info(obj).get("device_type", "Unknown")
