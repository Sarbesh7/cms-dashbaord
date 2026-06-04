from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import UserRegistrationSerializer
from .models import User
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken


# Create your views here.

class RegisterView(APIView):
    def post(self,request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data,status=status.HTTP_201_CREATED)
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)
    

class LoginView(APIView):
    def post(Self,request):
        email = request.data.get('email')
        password = request.data.get('password')

        User = get_user_model()
        user = User.objects.filter(email=email).first()

        if user and user.check_password(password):
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "refresh":str(refresh),
                    "access":str(refresh.access_token),
                   
                },
                 status=status.HTTP_200_OK
            )
        return Response(
            {"error":"Invalid Credentials"},
            status=status.HTTP_401_UNAUTHORIZED
        )
    

class TestView(APIView) :
    permission_classes = [IsAuthenticated]
    def get(self,request) :
        return Response(
            {"message":"you are authenticated"},
            status=status.HTTP_202_ACCEPTED
        )

