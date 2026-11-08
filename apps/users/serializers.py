from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.core.permissions import ORDINARY_CMS_ROLES, ROLE_DEFINITIONS, effective_role, role_label
from .models import User

# Superadmin cannot be assigned through account-management endpoints.
ROLE_CHOICES = [(key, spec["label"]) for key, spec in ROLE_DEFINITIONS.items() if key != "superadmin"]


def run_password_validators(password, user=None):
    """Apply settings.AUTH_PASSWORD_VALIDATORS; raise a DRF error on failure."""
    try:
        password_validation.validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages))
    return password


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class AccountSerializer(serializers.ModelSerializer):
    role_label = serializers.SerializerMethodField()
    sys_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'sys_id', 'username', 'first_name', 'last_name', 'email',
            'role', 'role_label', 'is_active', 'date_joined', 'last_login',
        ]
        read_only_fields = fields

    def get_role_label(self, obj):
        return role_label("superadmin" if obj.is_superuser else obj.role)

    def get_sys_id(self, obj):
        return f"SYS-{obj.id}"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        role = effective_role(instance)
        if role == "superadmin" or getattr(instance, 'is_superuser', False):
            data["username"] = "CSITABMC_SUPER"
            data["first_name"] = "CSITABMC"
            data["last_name"] = "SUPERADMIN"
        return data


class _AccountWriteMixin:
    def validate_email(self, value):
        value = value.strip()
        others = User.objects.exclude(pk=self.instance.pk) if self.instance else User.objects.all()
        if others.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        value = value.strip()
        others = User.objects.exclude(pk=self.instance.pk) if self.instance else User.objects.all()
        if others.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def _validate_new_password(self, attrs):
        password = attrs.get('password')
        if password:
            probe = self.instance or User()
            probe.username = attrs.get('username', getattr(probe, 'username', ''))
            probe.email = attrs.get('email', getattr(probe, 'email', ''))
            try:
                password_validation.validate_password(password, user=probe)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({'password': list(exc.messages)})
        return attrs


class AccountCreateSerializer(_AccountWriteMixin, serializers.ModelSerializer):
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=ROLE_CHOICES, default='cms_user')

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email',
            'password', 'role', 'is_active', 'date_joined', 'last_login',
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']

    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.user:
            creator_role = effective_role(request.user)
            target_role = attrs.get('role', 'cms_user')
            if target_role == 'superadmin':
                raise serializers.ValidationError({'role': "Cannot create a Superadmin account through Admin Access."})
            if creator_role == 'admin' and target_role not in ORDINARY_CMS_ROLES:
                raise serializers.ValidationError({'role': "Admins can only create ordinary CMS user accounts."})
        return self._validate_new_password(attrs)

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class AccountUpdateSerializer(_AccountWriteMixin, serializers.ModelSerializer):
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=ROLE_CHOICES, required=False)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email',
            'password', 'role', 'is_active', 'date_joined', 'last_login',
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']

    def validate(self, attrs):
        if not attrs.get('password'):
            attrs.pop('password', None)
        request = self.context.get('request')
        if request and request.user:
            editor_role = effective_role(request.user)
            target_role = attrs.get('role')
            if target_role == 'superadmin':
                raise serializers.ValidationError({'role': "Cannot promote an account to Superadmin."})
            if editor_role == 'admin' and target_role and target_role not in ORDINARY_CMS_ROLES:
                raise serializers.ValidationError({'role': "Admins can only assign ordinary CMS user roles."})
        return self._validate_new_password(attrs)

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context.get('user')
        try:
            password_validation.validate_password(attrs['new_password'], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'new_password': list(exc.messages)})
        return attrs
