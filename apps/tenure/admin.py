from django.contrib import admin
from .models import Tenure, Member, TenureMembership, Alumni


class TenureMembershipInline(admin.TabularInline):
    model = TenureMembership
    extra = 1


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
   
    list_display = ('name', 'email', 'phone_number', 'slug')
    search_fields = ('name', 'email', 'phone_number')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [TenureMembershipInline]


@admin.register(TenureMembership)
class TenureMembershipAdmin(admin.ModelAdmin):
    list_display = ('member', 'tenure', 'role_type', 'designation', 'order')
    list_filter = ('tenure', 'role_type')
    search_fields = ('member__name', 'designation')
    ordering = ('tenure', 'order')


@admin.register(Tenure)
class TenureAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [TenureMembershipInline]


@admin.register(Alumni)
class AlumniAdmin(admin.ModelAdmin):
    list_display = ('member', 'graduation_year')
    search_fields = ('member__name',)