from django.contrib import admin
from . import models

# Register your models here.
@admin.register(models.PastPaper)
class PastPaperAdmin(admin.ModelAdmin):
    list_display = ('subject_code', 'semester', 'exam_year', 'model_set','drive_link')
    list_filter = ('subject_code', 'semester', 'exam_year', 'model_set')
    search_fields = ('subject_code', 'exam_year', 'semester')