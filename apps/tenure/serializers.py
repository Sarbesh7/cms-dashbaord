from rest_framework import serializers
from . import models


class MemberSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Member
        fields = [
            "id",
            "name",
            "email",
            "image",
            "fb_link",
            "linkedin_link",
            "github_link",
            "description",
            "skills",
            "status",
            "slug",
        ]
        read_only_fields = ["slug"]


class TenureDropdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Tenure
        fields = ["id", "name", "slug","signature", "start_date", "end_date"]


class TenureSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Tenure
        fields = ["id", "name", "start_date", "end_date", "slug", "signature"]
        read_only_fields = ["slug"]


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
            "status",
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
            "status",
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
            "image",
            "fb_link",
            "linkedin_link",
            "github_link",
            "description",
            "skills",
            "status",
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
        required=False,
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
        extra_kwargs = {
            "bio": {"required": False, "allow_blank": True, "allow_null": True},
            "graduation_year": {"required": False, "allow_null": True},
        }

    def update(self, instance, validated_data):
        has_tenure_ids = "tenures" in validated_data
        tenures = validated_data.pop("tenures", None)
        instance = super().update(instance, validated_data)
        if has_tenure_ids and tenures is not None:
            instance.tenures.set(tenures)
        return instance


class DetailedTenureSerializer(serializers.ModelSerializer):

    memberships = TenureMembershipSerializer(many=True, read_only=True)

    class Meta:
        model = models.Tenure
        fields = ["id", "name", "start_date","signature", "end_date", "slug", "memberships"]
