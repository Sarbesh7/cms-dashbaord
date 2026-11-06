from django.contrib import admin
from .models import DeviceToken, NotificationHistory



@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'masked_token_display',
        'user',
        'platform',
        'enabled',
        'created_at',
        'updated_at',
    )
    list_filter = ('platform', 'enabled', 'created_at')
    search_fields = ('user__username', 'user__email', 'token')
    readonly_fields = ('id', 'created_at', 'updated_at')
    list_select_related = ('user',)

    def masked_token_display(self, obj):
        token = obj.token or ""
        if len(token) > 16:
            return f"{token[:10]}...{token[-6:]}"
        return token
    masked_token_display.short_description = "Token"


class NotificationAttemptInline(admin.TabularInline):
    from .models import NotificationAttempt
    model = NotificationAttempt
    extra = 0
    readonly_fields = ('attempt_number', 'targeted_count', 'accepted_count', 'failed_count', 'status', 'error_summary', 'created_at')
    can_delete = False


@admin.register(NotificationHistory)
class NotificationHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'title',
        'source_module',
        'status',
        'total_devices',
        'accepted_count',
        'failed_count',
        'retry_count',
        'created_at',
    )
    list_filter = ('source_module', 'status', 'created_at')
    search_fields = ('title', 'body', 'source_title')
    readonly_fields = (
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
    )
    inlines = [NotificationAttemptInline]

