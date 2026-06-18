from django.shortcuts import render,get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import User
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserCreateSerializer,ChangePasswordSerializer,ResetPasswordSerializer
from apps.core.permission import IsAdmin,IsCMSUser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.throttling import AnonRateThrottle,UserRateThrottle


class LoginView(APIView):
    throttle_classes = [AnonRateThrottle]
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
    permission_classes = [IsAuthenticated, IsAdmin]
    throttle_classes = [UserRateThrottle]
    
    def post(self,request):
        serializer =  UserCreateSerializer(data=request.data) 
        if serializer.is_valid():
               serializer.save()
               return Response(serializer.data,status=status.HTTP_200_OK)
        return Response(serializer.errors,status=status.HTTP_403_FORBIDDEN)


class ChangePasswordView(APIView) :
     permission_classes = [IsAuthenticated, IsCMSUser]
     throttle_classes = [UserRateThrottle]
     def post(self,request):
          serializer = ChangePasswordSerializer(data=request.data)
          if serializer.is_valid():
               user = request.user
               old_password = serializer.validated_data["old_password"]
               new_password = serializer.validated_data["new_password"] 
               if not user.check_password(old_password) :
                    return Response(
                    {"error": "old password is incorrect"},
                    status=status.HTTP_400_BAD_REQUEST
                )  
               user.set_password(new_password)     
               user.save() 
               return Response(
                    {"message":"password changed successfully"}
               )  
          return Response(
      serializer.errors,
    status=status.HTTP_400_BAD_REQUEST
)
     

class LogoutView(APIView)   :
     permission_classes = [IsAuthenticated,IsCMSUser] 

     def post(self,request)  :
          try:
               refresh_token = request.data.get("refresh")
               token = RefreshToken(refresh_token)
               token.blacklist()
               return Response(
                    {"message":"Logout Sucessfully"},
                    status=status.HTTP_204_NO_CONTENT
               )
          except Exception:
               return Response(
                    {"message":"Invalid Token"},
                    status=status.HTTP_400_BAD_REQUEST
               )
          


class ResetPasswordView(APIView):
    permission_classes = [IsAdmin,IsAuthenticated]

    def post(self, request, user_id):

        serializer = ResetPasswordSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        user = get_object_or_404(
            User,
            id=user_id
        )

        user.set_password(
            serializer.validated_data["new_password"]
        )

        user.save()

        return Response(
            {
                "message": "Password reset successfully"
            },
            status=status.HTTP_200_OK
        )          


               

            
