from .models import User
from rest_framework import serializers


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email','password']


    def create(self,validated_data)  :
        password =  validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user