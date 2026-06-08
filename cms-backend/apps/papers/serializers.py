from . import models
from rest_framework import serializers

class PastPaperSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = models.PastPaper
        fields = '__all__'
        