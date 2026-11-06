from django.contrib import admin
from .models import Event, Mentor, EventMentorAssignment


@admin.register(Mentor)
class MentorAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'expertise')
    list_filter = ('expertise',)
    search_fields = ('name', 'email', 'expertise')


class EventMentorAssignmentInline(admin.TabularInline):
    model = EventMentorAssignment
    extra = 1


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'tenure', 'category', 'status', 'date', 'available_seats')
    list_filter = ('status', 'category', 'tenure', 'date')
    search_fields = ('title', 'description', 'organiser', 'location')
    prepopulated_fields = {'slug': ('title',)}
    list_select_related = ('tenure',)
    inlines = [EventMentorAssignmentInline]
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
    )


@admin.register(EventMentorAssignment)
class EventMentorAssignmentAdmin(admin.ModelAdmin):
    list_display = ('event', 'mentor', 'role', 'custom_role', 'responsibility')
    list_filter = ('role', 'event')
    search_fields = ('event__title', 'mentor__name', 'responsibility', 'custom_role')