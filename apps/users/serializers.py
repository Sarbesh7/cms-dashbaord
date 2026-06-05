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