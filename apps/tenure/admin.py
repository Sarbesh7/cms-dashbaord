from django.contrib import admin
from .models import Tenure, Member, TenureMembership, Alumni


@admin.register(Tenure)
class TenureAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'slug')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    # Removed 'tenure' from list_display and list_filter
    list_display = ('name', 'role', 'email', 'phone_number', 'slug')
    search_fields = ('name', 'email', 'role')
    readonly_fields = ('slug',)


@admin.register(TenureMembership)
class TenureMembershipAdmin(admin.ModelAdmin):
    list_display = ('member', 'tenure', 'role_type', 'designation')
    list_filter = ('role_type', 'tenure')
    search_fields = ('member__name', 'designation', 'tenure__name')


@admin.register(Alumni)
class AlumniAdmin(admin.ModelAdmin):
    list_display = ('member', 'graduation_year')
    list_filter = ('graduation_year', 'tenures')
    search_fields = ('member__name', 'bio')
    filter_horizontal = ('tenures',)