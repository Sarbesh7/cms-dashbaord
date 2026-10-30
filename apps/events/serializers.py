import json
import re

from django.db import transaction
from rest_framework import serializers
from .models import Event, Mentor, EventMentorAssignment


def _normalize_role_text(value):
    """Lower-case and collapse separators so 'Co-Mentor', 'co mentor' and 'co_mentor' compare equal."""
    return re.sub(r"[\s_-]+", " ", value or "").strip().lower()


BUILT_IN_ROLE_KEYS = {
    _normalize_role_text(text)
    for value, label in EventMentorAssignment.Role.choices
    if value != EventMentorAssignment.Role.CUSTOM
    for text in (value, label)
}


class MentorEventAssignmentSummarySerializer(serializers.ModelSerializer):
    event_id = serializers.IntegerField(source='event.id', read_only=True)
    event_title = serializers.CharField(source='event.title', read_only=True)
    event_slug = serializers.CharField(source='event.slug', read_only=True)
    role_label = serializers.CharField(read_only=True)

    class Meta:
        model = EventMentorAssignment
        fields = [
            'id',
            'event_id',
            'event_title',
            'event_slug',
            'role',
            'role_label',
            'custom_role',
            'responsibility',
        ]


class MentorSerializer(serializers.ModelSerializer):
    event_assignments = MentorEventAssignmentSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Mentor
        fields = [
            'id',
            'name',
            'email',
            'expertise',
            'linkedin_profile',
            'photo',
            'event_assignments',
            'created_at',
            'updated_at',
        ]


class EventMentorAssignmentSerializer(serializers.ModelSerializer):
    mentor_id = serializers.IntegerField(source='mentor.id', read_only=True)
    mentor_name = serializers.CharField(source='mentor.name', read_only=True)
    mentor_expertise = serializers.CharField(source='mentor.expertise', read_only=True)
    mentor_photo = serializers.ImageField(source='mentor.photo', read_only=True)
    mentor_email = serializers.EmailField(source='mentor.email', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    role_label = serializers.CharField(read_only=True)

    class Meta:
        model = EventMentorAssignment
        fields = [
            'id',
            'mentor_id',
            'mentor_name',
            'mentor_expertise',
            'mentor_photo',
            'mentor_email',
            'role',
            'role_display',
            'role_label',
            'custom_role',
            'responsibility',
            'created_at',
            'updated_at',
        ]


class EventMentorAssignmentWriteSerializer(serializers.Serializer):
    """Validates one entry of an event's `assignments` payload."""
    mentor_id = serializers.PrimaryKeyRelatedField(queryset=Mentor.objects.all(), source='mentor')
    role = serializers.ChoiceField(
        choices=EventMentorAssignment.Role.choices,
        default=EventMentorAssignment.Role.MAIN_MENTOR,
    )
    custom_role = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    responsibility = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        custom_role = " ".join((attrs.get('custom_role') or "").split())
        if attrs['role'] == EventMentorAssignment.Role.CUSTOM:
            if not custom_role:
                raise serializers.ValidationError({'custom_role': 'Enter a role name for the custom role.'})
            if _normalize_role_text(custom_role) in BUILT_IN_ROLE_KEYS:
                raise serializers.ValidationError({
                    'custom_role': f'"{custom_role}" is a built-in role. Choose it from the role list instead.'
                })
        else:
            custom_role = ""
        attrs['custom_role'] = custom_role
        attrs['responsibility'] = (attrs.get('responsibility') or "").strip()
        return attrs


class EventSerializer(serializers.ModelSerializer):
    tenure_name = serializers.CharField(source='tenure.name', read_only=True, default=None)
    mentors = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    mentors_detail = MentorSerializer(source='mentors', many=True, read_only=True)
    mentor_assignments = EventMentorAssignmentSerializer(many=True, read_only=True)
    assignments = EventMentorAssignmentWriteSerializer(many=True, write_only=True, required=False)

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
            'mentor_assignments',
            'assignments',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['slug', 'mentor_assignments']

    def to_internal_value(self, data):
        # Multipart requests send `assignments` as a JSON string. Convert the
        # QueryDict into a plain dict so the nested serializer reads the decoded list.
        if hasattr(data, 'getlist'):
            data = {key: data.get(key) for key in data.keys()}
        else:
            data = dict(data)

        assignments_val = data.get('assignments')
        if isinstance(assignments_val, str):
            try:
                data['assignments'] = json.loads(assignments_val) if assignments_val.strip() else []
            except ValueError:
                raise serializers.ValidationError({'assignments': ['Assignments must be valid JSON.']})

        return super().to_internal_value(data)

    def validate_assignments(self, value):
        seen = set()
        for item in value:
            mentor = item['mentor']
            if mentor.pk in seen:
                raise serializers.ValidationError(
                    f'Mentor "{mentor}" (id {mentor.pk}) is assigned more than once.'
                )
            seen.add(mentor.pk)
        return value

    def create(self, validated_data):
        assignments_data = validated_data.pop('assignments', None)
        with transaction.atomic():
            event = super().create(validated_data)
            if assignments_data is not None:
                self._replace_assignments(event, assignments_data)
        return event

    def update(self, instance, validated_data):
        assignments_data = validated_data.pop('assignments', None)
        with transaction.atomic():
            event = super().update(instance, validated_data)
            if assignments_data is not None:
                self._replace_assignments(event, assignments_data)
        return event

    def _replace_assignments(self, event, assignments_data):
        # Drop any prefetched assignments so the response reflects the new set.
        getattr(event, '_prefetched_objects_cache', {}).clear()
        event.mentor_assignments.all().delete()
        EventMentorAssignment.objects.bulk_create([
            EventMentorAssignment(
                event=event,
                mentor=item['mentor'],
                role=item['role'],
                custom_role=item['custom_role'],
                responsibility=item['responsibility'],
            )
            for item in assignments_data
        ])
