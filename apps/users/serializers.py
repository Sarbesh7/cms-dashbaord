from .models import User
from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    



class UserCreateSerializer(serializers.ModelSerializer) :
    password = serializers.CharField(write_only=True)  
    id = serializers.IntegerField(read_only=True)
   
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role', 'profile_picture']


    def create(self,validated_data):
        password = validated_data.pop('password')  
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
    

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    

    def validate_password(self, value):
     if len(value) < 8:
        raise serializers.ValidationError(
            "Password must be at least 8 characters long."
        )
     return value
    

class UserUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role', 'profile_picture']

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

    def validate_password(self, value):
        if value and len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        return value

    def validate_email(self, value):
        # Allow updating to the same email, but not an existing one
        request = self.context.get('request')
        if request and request.method in ['PUT', 'PATCH']:
            # self.instance is the current user being updated
            if User.objects.exclude(pk=self.instance.pk).filter(email=value).exists():
                raise serializers.ValidationError("A user with this email already exists.")
        elif User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    
class ChangePasswordSerializer(serializers.Serializer):
   old_password = serializers.CharField()
   new_password = serializers.CharField()


class ForgotPasswordSerializer(serializers.Serializer):
   email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError(
                "Password must be at least 8 characters long."
            )
        return value
