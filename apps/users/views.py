import logging
from django.shortcuts import render, get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import User
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserCreateSerializer, ChangePasswordSerializer, ForgotPasswordSerializer, ResetPasswordSerializer
from apps.core.permission import IsAdmin, IsCMSUser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError        


logger = logging.getLogger('security')


class LoginView(APIView):
    throttle_classes = [AnonRateThrottle]
    def post(self, request):

        email = request.data.get("email")
        password = request.data.get("password")

        user = User.objects.filter(email=email).first()

        if not user or not user.check_password(password):
            logger.warning(f"Failed login attempt: {email}")

            return Response(
                {"message": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        response = Response(
            {
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                }
            },
            status=status.HTTP_200_OK
        )

        response.set_cookie(
            key="access_token",
            value=str(access),
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Lax",
            max_age=ACCESS_TOKEN_AGE,
        )

        response.set_cookie(
            key="refresh_token",
            value=str(refresh),
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Lax",
            max_age=REFRESH_TOKEN_AGE,
        )

        logger.info(f"Successful login: {user.email}")

        return response
    

class UserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    throttle_classes = [UserRateThrottle]
    
    def get(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        serializer = UserCreateSerializer(user)
        logger.info(f"Admin '{request.user.email}' retrieved details for user: '{user.email}'")
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [UserRateThrottle]
    
    def post(self, request):
        serializer = UserCreateSerializer(data=request.data) 
        if serializer.is_valid():
            user = serializer.save()
            logger.info(f"Admin '{request.user.email}' successfully created a new user: '{user.email}'")
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        logger.warning(f"User creation failed by Admin '{request.user.email}'. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_403_FORBIDDEN)
        
    def get(self, request):
        users = User.objects.all()
        serializer = UserCreateSerializer(users, many=True)
        logger.info(f"Admin '{request.user.email}' retrieved the user list.")
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated, IsCMSUser]
    throttle_classes = [UserRateThrottle]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            old_password = serializer.validated_data["old_password"]
            new_password = serializer.validated_data["new_password"] 
            
            if not user.check_password(old_password):
                logger.warning(f"Password change failed for user '{user.email}': Incorrect old password.")
                return Response(
                    {"error": "old password is incorrect"},
                    status=status.HTTP_400_BAD_REQUEST
                )  
            
            user.set_password(new_password)     
            user.save() 
            logger.info(f"Successfully changed password for user: '{user.email}'")
            return Response(
                {"message": "password changed successfully"}
            )  
            
        logger.warning(f"Password change validation failed for user '{request.user.email}'. Errors: {serializer.errors}")
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


# class TestEmailView(APIView):
#     # Removing permission guard if it's meant to be public, but adding auth logging if user context is available
#     def get(self, request):
#         caller = request.user.email if request.user.is_authenticated else "Anonymous"
#         try:
#             send_mail(
#                 subject="SMTP Test",
#                 message="Congratulations! Your Django SMTP setup is working.",
#                 from_email=settings.EMAIL_HOST_USER,
#                 recipient_list=[settings.EMAIL_HOST_USER],
#                 fail_silently=False,
#                 )
#             logger.info(f"SMTP Test email successfully sent by operator: '{caller}'")
#             return Response({
#                 "message": "Email sent successfully"
#             })
#         except Exception as e:
#             logger.error(f"SMTP Test email delivery failed for operator '{caller}'. Error Details: {str(e)}")
#             return Response(
#                 {"error": "Email system configuration issue encountered."},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )


#   class ForgotPasswordView(APIView):
#     def post(self, request):
#         serializer = ForgotPasswordSerializer(data=request.data)
#         if serializer.is_valid():
#             email = serializer.validated_data["email"]
#             try:
#                 user = User.objects.get(email=email)
#                 uid = urlsafe_base64_encode(force_bytes(user.pk))
#                 token = default_token_generator.make_token(user)
                
#                 reset_link = f"http://localhost:3000/reset-password/{uid}/{token}/"

#                 send_mail(
#                     subject="Password Reset Request",
#                     message=f"\nHi {user.username},\n\nClick the link below to reset your password:\n\n{reset_link}\n\nIf you didn't request this, ignore this email.\n",
#                     from_email=settings.EMAIL_HOST_USER,
#                     recipient_list=[user.email],
#                     fail_silently=False
#                 )
#                 logger.info(f"Password reset link dispatched successfully to target: '{email}'")

#             except User.DoesNotExist:
               
#                 logger.warning(f"Password reset requested for non-registered email: '{email}'")
#                 pass
#             except Exception as mail_err:
#                 logger.error(f"Failed to transmit reset email to target '{email}'. Technical error: {str(mail_err)}")

#             return Response(
#                 {
#                     "message": "If an account exists, a reset email has been sent."
#                 },
#                 status=status.HTTP_200_OK
#             )

#         return Response(
#             serializer.errors,
#             status=status.HTTP_400_BAD_REQUEST
#         )


class ResetPasswordView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [UserRateThrottle]
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            uid = serializer.validated_data["uid"]
            token = serializer.validated_data["token"]
            new_password = serializer.validated_data["new_password"]    
            
            try:
                
                user_id = force_str(urlsafe_base64_decode(uid))
                user = User.objects.get(pk=user_id)
                
                if not default_token_generator.check_token(user, token):
                    logger.warning(f"Password reset token verification failed for user verification id: '{user_id}'. Token invalid/expired.")
                    return Response(
                        {"error": "Invalid or expired token"},
                        status=status.HTTP_400_BAD_REQUEST 
                    )
                
                user.set_password(new_password)
                user.save()
                
                logger.info(f"User password successfully updated via valid reset token pipeline for user: '{user.email}'")
                return Response(
                    {"message": "Password reset successful"},
                    status=status.HTTP_200_OK
                )
            except (TypeError, ValueError, OverflowError, User.DoesNotExist) as validation_err:
                logger.warning(f"Malformed or fake password reset link processed. Error Context: {str(validation_err)}")
                return Response(
                    {"error": "Invalid reset link"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
  
    def post(self, request):

        refresh_token = request.COOKIES.get("refresh_token")

        response = Response(
            {"message": "Logout successful"},
            status=status.HTTP_205_RESET_CONTENT
        )

        if refresh_token:

            try:
                token = RefreshToken(refresh_token)
                token.blacklist()

            except TokenError:
                pass

        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")

        logger.info(f"Logout: {request.user.email}")

        return response

#cookiesss 

class CookieJWTAuthentication(JWTAuthentication):

    def authenticate(self, request):
        raw_token = request.COOKIES.get("access_token")

        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
            return self.get_user(validated_token), validated_token

        except InvalidToken:
            return None               