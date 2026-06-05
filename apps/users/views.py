from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import User
from rest_framework_simplejwt.tokens import RefreshToken



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