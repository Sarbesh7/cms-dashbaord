from django.contrib import admin
from . import models
# from .apps import events


# Register your models here.
@admin.register(models.Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ("certificate_id", "full_name", "event", "issued_at")
    search_fields = ("full_name","event__title")
    list_filter = ("issued_at",)

@admin.register(models.CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "template_name", "template_file")
    search_fields = ("template_name",)