from django.contrib import admin
from .models import Notification, NotificationRecipient


class NotificationRecipientInline(admin.TabularInline):
    model = NotificationRecipient
    extra = 0
    readonly_fields = ('recipient', 'is_read', 'read_at', 'created_at')
    can_delete = False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'sender', 'source_module', 'created_at')
    list_filter = ('source_module', 'created_at')
    search_fields = ('title', 'message', 'sender__username', 'sender__email')
    readonly_fields = ('id', 'created_at', 'updated_at')
    list_select_related = ('sender',)
    inlines = [NotificationRecipientInline]


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(admin.ModelAdmin):
    list_display = ('id', 'notification', 'recipient', 'is_read', 'read_at', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('notification__title', 'recipient__username', 'recipient__email')
    readonly_fields = ('id', 'created_at')
    list_select_related = ('notification', 'recipient')
