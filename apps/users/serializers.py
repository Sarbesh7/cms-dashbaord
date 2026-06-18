from .models import User
from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    



class UserCreateSerializer(serializers.ModelSerializer) :
    password = serializers.CharField(write_only=True)   
   
    class Meta:
        model = User
        fields = ['username','email','password','role']


    def create(self,validated_data):
        password = validated_data.pop('password')  
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
    

    def validate_password(self, value):
     if len(value) < 8:
        raise serializers.ValidationError(
            "Password must be at least 8 characters long."
        )
     return value
    
class ChangePasswordSerializer(serializers.Serializer):
   old_password = serializers.CharField()
   new_password = serializers.CharField()

class ResetPasswordSerializer(serializers.Serializer):
   new_password = serializers.CharField(write_only = True, min_length = 8)
   
     