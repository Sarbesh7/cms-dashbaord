from django.contrib import admin
from .models import Blog


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'author', 'status', 'published_at', 'created_at', 'updated_at')
    list_select_related = ('author',)
    raw_id_fields = ('author',)
    list_filter = ('status',)
    search_fields = ('title', 'slug')
    readonly_fields = ('slug', 'published_at', 'created_at', 'updated_at')
