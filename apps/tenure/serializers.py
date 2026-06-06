from . import models
from rest_framework import serializers


        
class MemberSerializer(serializers.ModelSerializer):
    tenure = serializers.SlugRelatedField(
        slug_field='slug', 
        queryset=models.Tenure.objects.all())
    
    class Meta:
        model = models.Member
        fields = '__all__'

class TenureSerializer(serializers.ModelSerializer):
    members = MemberSerializer(many=True, read_only=True)
    
    class Meta:
        model = models.Tenure
        fields = '__all__'