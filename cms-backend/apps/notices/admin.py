from django.contrib import admin
from .models import Notice
from . import models


@admin.register(models.Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_at", "updated_at")
    search_fields = ("title",)
    list_filter = ("created_at", "updated_at")
    
