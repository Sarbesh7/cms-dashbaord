from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import User
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserCreateSerializer



class LoginView(APIView):
    def post(self,request):
        email=request.data.get('email')
        password = request.data.get('password')

        user = User.objects.filter(email=email).first()

        if user and user.check_password(password) :
            refresh =RefreshToken.for_user(user)

            return Response(
                {
                    "refresh":str(refresh),
                    "access": str(refresh.access_token)
            },
                status=status.HTTP_200_OK
                 

            )
        return Response(
            {"message":"Invalid credentials"},
            status = status.HTTP_401_UNAUTHORIZED
        )
    

class UserView(APIView):
  
    def post(self,request):
        if not request.user.is_autheticated:
           return Response({'error':"not authorized "},status=status.HTTP_401_UNAUTHORIZED)
        if not request.user.is_superuser :
           return Response({"error": "Not allowed"},status=status.HTTP_403_FORBIDDEN)
        serializer =  UserCreateSerializer(data=request.data) 
        if serializer.is_valid():
               serializer.save()
               return Response(serializer.data,status=status.HTTP_200_OK)
        return Response(serializer.errors)

               

            
