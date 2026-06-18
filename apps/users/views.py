from django.shortcuts import render,get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import User
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserCreateSerializer,ChangePasswordSerializer,ForgotPasswordSerializer,ResetPasswordSerializer
from apps.core.permission import IsAdmin,IsCMSUser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.throttling import AnonRateThrottle,UserRateThrottle
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.http import  urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.conf import settings


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
           
class TestEmailView(APIView):

    def get(self, request):

        send_mail(
            subject="SMTP Test",
            message="Congratulations! Your Django SMTP setup is working.",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[settings.EMAIL_HOST_USER],
            fail_silently=False,
        )

        return Response({
            "message": "Email sent successfully"
        })

class ForgotPasswordView(APIView):

    def post(self, request):

        serializer = ForgotPasswordSerializer(data=request.data)

        if serializer.is_valid():

            email = serializer.validated_data["email"]

            try:
                user = User.objects.get(email=email)

                uid = urlsafe_base64_encode(
                    force_bytes(user.pk)
                )

                token = default_token_generator.make_token(user)

                reset_link = (
                    f"http://localhost:3000/reset-password/"
                    f"{uid}/{token}/"
                )

                send_mail(
                    subject="Password Reset Request",
                    message=f"""
Hi {user.username},

Click the link below to reset your password:

{reset_link}

If you didn't request this, ignore this email.
""",
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[user.email],
                    fail_silently=False
                )

            except User.DoesNotExist:
                pass

            return Response(
                {
                    "message": "If an account exists, a reset email has been sent."
                },
                status=status.HTTP_200_OK
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
    
class ResetPasswordView(APIView):

    def post(self, request):

        serializer = ResetPasswordSerializer(
            data=request.data
        )

        if serializer.is_valid():

            uid = serializer.validated_data["uid"]
            token = serializer.validated_data["token"]
            new_password = serializer.validated_data["new_password"]    
            try:
                user_id = force_bytes(
                    urlsafe_base64_encode(uid)
                    )
                user = User.objects.get(pk=user_id)
                if not default_token_generator.check_token(user,token):
                    return Response(
                          {
                            "error": "Invalid or expired token"
                        },
                        status=status.HTTP_400_BAD_REQUEST 
                    )
                user.set_password(new_password)
                user.save()
                return Response(
                      {
                        "message": "Password reset successful"
                    },
                      status=status.HTTP_200_OK
                )
            except User.DoesNotExist :
                return Response(
                    {
                        "error": "Invalid reset link"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            



class LogoutView(APIView):
    permission_classes =[IsAuthenticated]
    def post(self,request):
        try:
          refresh_token =request.data.get("refresh")
          token = RefreshToken(refresh_token)
          token.blacklist()
          return Response(
                {"message": "Logout successful"},
                status=status.HTTP_205_RESET_CONTENT
            )

        except Exception:
         return Response(
                {"error": "Invalid token"},
                status=status.HTTP_400_BAD_REQUEST
            )



            
