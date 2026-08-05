from rest_framework import serializers
from . import models


class MemberSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Member
        fields = [
            "id",
            "name",
            "email",
            "phone_number",
            "image",
            "fb_link",
            "linkedin_link",
            "github_link",
            "slug",
        ]
        read_only_fields = ["slug"]


class TenureDropdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Tenure
        fields = ["id", "name", "slug", "start_date", "end_date"]


class TenureMembershipSerializer(serializers.ModelSerializer):

    member = MemberSerializer(read_only=True)
    member_id = serializers.PrimaryKeyRelatedField(
        queryset=models.Member.objects.all(), source="member", write_only=True
    )
    tenure = serializers.SlugRelatedField(
        slug_field="slug", queryset=models.Tenure.objects.all()
    )

    class Meta:
        model = models.TenureMembership
        fields = [
            "id",
            "member",
            "member_id",
            "tenure",
            "role_type",
            "designation",
            "order",
        ]


class MemberHistoryMembershipSerializer(serializers.ModelSerializer):

    tenure_name = serializers.CharField(source="tenure.name", read_only=True)
    tenure_slug = serializers.CharField(source="tenure.slug", read_only=True)

    class Meta:
        model = models.TenureMembership
        fields = [
            "id",
            "tenure_name",
            "tenure_slug",
            "role_type",
            "designation",
            "order",
        ]


class MemberProfileSerializer(serializers.ModelSerializer):

    history = MemberHistoryMembershipSerializer(
        source="memberships", many=True, read_only=True
    )

    class Meta:
        model = models.Member
        fields = [
            "id",
            "name",
            "email",
            "phone_number",
            "image",
            "fb_link",
            "linkedin_link",
            "github_link",
            "slug",
            "history",
        ]
        read_only_fields = ["slug"]


class AlumniSerializer(serializers.ModelSerializer):
    member = MemberSerializer(read_only=True)
    member_id = serializers.PrimaryKeyRelatedField(
        queryset=models.Member.objects.all(), source="member", write_only=True
    )
    tenures = TenureDropdownSerializer(many=True, read_only=True)
    tenure_ids = serializers.PrimaryKeyRelatedField(
        queryset=models.Tenure.objects.all(),
        source="tenures",
        many=True,
        write_only=True,
    )

    class Meta:
        model = models.Alumni
        fields = [
            "id",
            "member",
            "member_id",
            "tenures",
            "tenure_ids",
            "graduation_year",
            "bio",
        ]


class DetailedTenureSerializer(serializers.ModelSerializer):

    memberships = TenureMembershipSerializer(many=True, read_only=True)

    class Meta:
        model = models.Tenure
        fields = ["id", "name", "start_date", "end_date", "slug", "memberships"]
