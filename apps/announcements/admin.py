from django.contrib import admin
from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'link', 'created_at', 'updated_at')
    search_fields = ('title', 'description')
    ordering = ('-created_at',)
