from django.contrib import admin
from .models import Event, Mentor


@admin.register(Mentor)
class MentorAdmin(admin.ModelAdmin):
    list_display = ('name', 'member', 'email', 'expertise', 'slug')
    list_filter = ('expertise',)
    search_fields = ('name', 'email', 'expertise', 'member__name')
    prepopulated_fields = {'slug': ('name',)}
    raw_id_fields = ('member',)  # Look up existing team members efficiently
    list_select_related = ('member',)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'tenure', 'category', 'status', 'date', 'available_seats')
    list_filter = ('status', 'category', 'tenure', 'date')
    search_fields = ('title', 'description', 'organiser', 'location')
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('mentors',)  # Dual-list box interface for assigning multiple mentors
    list_select_related = ('tenure',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'tenure', 'category', 'tags', 'status', 'description', 'image')
        }),
        ('Event Logistics', {
            'fields': ('date', 'start_time', 'end_time', 'location', 'organiser', 'available_seats')
        }),
        ('Registration Details', {
            'fields': ('registration_fee_bmc', 'registration_fee_non_bmc', 'registration_link')
        }),
        ('Mentorship', {
            'fields': ('mentors',)
        }),
    )