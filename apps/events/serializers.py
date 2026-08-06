from rest_framework import serializers
from .models import Event, Mentor


class MentorSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.name', read_only=True, default=None)
    member_slug = serializers.CharField(source='member.slug', read_only=True, default=None)
    is_internal_member = serializers.SerializerMethodField()

    class Meta:
        model = Mentor
        fields = [
            'id',
            'member',
            'member_name',
            'member_slug',
            'is_internal_member',
            'name',
            'email',
            'expertise',
            'linkedin_profile',
            'photo',
            'slug',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['slug']

    def get_is_internal_member(self, obj):
        return obj.member_id is not None


class EventSerializer(serializers.ModelSerializer):
    tenure_name = serializers.CharField(source='tenure.name', read_only=True, default=None)
    
 
    mentors_detail = MentorSerializer(source='mentors', many=True, read_only=True)

    class Meta:
        model = Event
        fields = [
            'id',
            'tenure',
            'tenure_name',
            'title',
            'slug',
            'description',
            'organiser',
            'location',
            'image',
            'date',
            'start_time',
            'end_time',
            'available_seats',
            'registration_fee_bmc',
            'registration_fee_non_bmc',
            'registration_link',
            'category',
            'tags',
            'status',
            'mentors',          
            'mentors_detail',  
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['slug']