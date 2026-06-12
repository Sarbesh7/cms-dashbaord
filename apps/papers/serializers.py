from . import models
from rest_framework import serializers

class PastPaperSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = models.PastPaper
        fields = '__all__'
    
    def get_subject_name(self, obj):
        return obj.get_subject_code_display()

    def get_semester_name(self, obj):
        return obj.get_semester_display()   