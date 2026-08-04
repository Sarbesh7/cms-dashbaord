from . import models
from rest_framework import serializers


        
class MemberSerializer(serializers.ModelSerializer):
    tenure = serializers.SlugRelatedField(
        slug_field='slug', 
        queryset=models.Tenure.objects.all())
    
    class Meta:
        model = models.Member
        fields = '__all__'
        read_only_fields = ['slug']

class TenureSerializer(serializers.ModelSerializer):
    members = MemberSerializer(many=True, read_only=True)
    
    class Meta:
        model = models.Tenure
        fields = '__all__'
        read_only_fields = ['slug'] 


class TenureMembershipSerializer(serializers.ModelSerializer):
    member = MemberSerializer(read_only=True)
    member_id = serializers.PrimaryKeyRelatedField(
        queryset=models.Member.objects.all(), 
        source='member', 
        write_only=True
    )
    tenure = serializers.SlugRelatedField(
        slug_field='slug', 
        queryset=models.Tenure.objects.all()
    )

    class Meta:
        model = models.TenureMembership
        fields = ['__all__']


class AlumniSerializer(serializers.ModelSerializer):
    
    member = MemberSerializer(read_only=True)
    member_id = serializers.PrimaryKeyRelatedField(
        queryset=models.Member.objects.all(), 
        source='member', 
        write_only=True
    )
    tenures = TenureSerializer(many=True, read_only=True)
    tenure_id = serializers.PrimaryKeyRelatedField(
        queryset=models.Tenure.objects.all(), 
        source='tenures', 
        many=True, 
        write_only=True
    )

    class Meta:
        model = models.Alumni
        fields = ['__all__']


class DetailedTenureSerializer(serializers.ModelSerializer):
  
    memberships = TenureMembershipSerializer(many=True, read_only=True)
    alumni = AlumniSerializer(many=True, read_only=True)

    class Meta:
        model = models.Tenure
        fields = ['__all__']