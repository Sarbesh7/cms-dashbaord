from django.contrib import admin
from .models import Event, Mentor

# Register your models here.
@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'status')
    search_fields = ('title', 'description')
    list_filter = ('status', 'date')

   
@admin.register(Mentor)
class MentorAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'expertise' )
    search_fields = ('name', 'email', 'expertise' )