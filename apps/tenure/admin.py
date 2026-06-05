from django.contrib import admin
from .models import Tenure, Member
# Register your models here.

@admin.register(Tenure)
class TenureAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'email', 'phone_number', 'tenure')
    list_filter = ('tenure',)
    search_fields = ('name', 'email', 'phone_number')

