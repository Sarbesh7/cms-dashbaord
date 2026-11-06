from rest_framework import serializers

from apps.core.visibility import PUBLISHED
from . import models

# Fields never returned to public (non-dashboard) callers.
PRIVATE_MEMBER_FIELDS = ("email",)
PRIVATE_TENURE_FIELDS = ("signature",)


def _is_public(serializer):
    return bool(serializer.context.get("public"))


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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if _is_public(self):
            for field in PRIVATE_MEMBER_FIELDS:
                data.pop(field, None)
        return data


class TenureDropdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Tenure
        fields = ["id", "name", "slug", "signature", "start_date", "end_date"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if _is_public(self):
            for field in PRIVATE_TENURE_FIELDS:
                data.pop(field, None)
        return data


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
    # Survives Member deletion (the FK becomes NULL; the snapshot keeps the name).
    member_name = serializers.CharField(read_only=True)
    tenure = serializers.SlugRelatedField(
        slug_field="slug", queryset=models.Tenure.objects.all()
    )

    class Meta:
        model = models.TenureMembership
        fields = [
            "id",
            "member",
            "member_id",
            "member_name",
            "tenure",
            "role_type",
            "designation",
            "order",
            "status",
        ]


def _public_membership(membership):
    return membership.status == PUBLISHED and membership.member_id and membership.member.status == PUBLISHED


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

    history = serializers.SerializerMethodField()

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

    def get_history(self, obj):
        memberships = obj.memberships.all()
        if _is_public(self):
            memberships = [m for m in memberships if m.status == PUBLISHED]
        return MemberHistoryMembershipSerializer(memberships, many=True, context=self.context).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if _is_public(self):
            for field in PRIVATE_MEMBER_FIELDS:
                data.pop(field, None)
        return data


class AlumniSerializer(serializers.ModelSerializer):
    member = MemberSerializer(read_only=True)
    member_id = serializers.PrimaryKeyRelatedField(
        queryset=models.Member.objects.all(), source="member", write_only=True
    )
    member_name = serializers.CharField(read_only=True)
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
            "member_name",
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

    memberships = serializers.SerializerMethodField()

    class Meta:
        model = models.Tenure
        fields = ["id", "name", "start_date", "signature", "end_date", "slug", "memberships"]

    def get_memberships(self, obj):
        memberships = obj.memberships.all()
        if _is_public(self):
            memberships = [m for m in memberships if _public_membership(m)]
        return TenureMembershipSerializer(memberships, many=True, context=self.context).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if _is_public(self):
            for field in PRIVATE_TENURE_FIELDS:
                data.pop(field, None)
        return data
