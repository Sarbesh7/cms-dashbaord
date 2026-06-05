from . import models
from rest_framework import serializers


        
class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = '__all__'

class TenureSerializer(serializers.ModelSerializer):
    members = MemberSerializer(many=True, read_only=True)
    
    class Meta:
        model = Tenure
        fields = '__all__'