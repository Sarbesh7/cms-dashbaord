import logging
from django.shortcuts import render, get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import User
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from .serializers import UserCreateSerializer, UserUpdateSerializer, ChangePasswordSerializer, ForgotPasswordSerializer, ResetPasswordSerializer
from apps.core.permission import IsAdmin, IsCMSUser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
from rest_framework_simplejwt.settings import api_settings



logger = logging.getLogger('security')


def _cookie_kwargs(max_age):
    return {
        "httponly": True,
        "secure": not settings.DEBUG,
        "samesite": "None" if not settings.DEBUG else "Lax",
        "max_age": max_age,
    }


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
                    "user_role": user.role,
                    "profile_picture": user.profile_picture.url if user.profile_picture else None
                }
            },
            status=status.HTTP_200_OK
        )
        ACCESS_TOKEN_AGE = int(api_settings.ACCESS_TOKEN_LIFETIME.total_seconds())
        REFRESH_TOKEN_AGE = int(api_settings.REFRESH_TOKEN_LIFETIME.total_seconds())

        response.set_cookie(
            key="access_token",
            value=str(access),
            **_cookie_kwargs(int(api_settings.ACCESS_TOKEN_LIFETIME.total_seconds())),
        )

        response.set_cookie(
            key="refresh_token",
            value=str(refresh),
            **_cookie_kwargs(int(api_settings.REFRESH_TOKEN_LIFETIME.total_seconds())),
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
    
    def put(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Admin '{request.user.email}' updated user '{user.email}'")
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        logger.warning(f"User update failed by Admin '{request.user.email}'. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Admin '{request.user.email}' patched user '{user.email}'")
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        logger.warning(f"User patch failed by Admin '{request.user.email}'. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, user_id):
        if str(request.user.id) == str(user_id):
            return Response({"error": "You cannot delete your own account."}, status=status.HTTP_400_BAD_REQUEST)
        
        user = get_object_or_404(User, id=user_id)
        user.delete()
        logger.info(f"Admin '{request.user.email}' deleted user '{user.email}'")
        return Response(status=status.HTTP_204_NO_CONTENT)

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
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
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

        response.set_cookie("access_token", "", **_cookie_kwargs(0))
        response.set_cookie("refresh_token", "", **_cookie_kwargs(0))

        logger.info(f"Logout: {request.user.email}")

        return response

class RefreshTokenView(APIView):
   def post(self, request):

        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response(
                {"message": "Refresh token missing"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:

            refresh = RefreshToken(refresh_token)
            
            if api_settings.ROTATE_REFRESH_TOKENS:
                if api_settings.BLACKLIST_AFTER_ROTATION:
                    try:
                        refresh.blacklist()
                    except AttributeError:
                        pass
                refresh.set_jti()
                refresh.set_exp()
                refresh.set_iat()

            new_access = refresh.access_token

            response = Response(
                {
                    "message": "Access token refreshed"
                },
                status=status.HTTP_200_OK
            )

            response.set_cookie(
                key="access_token",
                value=str(new_access),
                **_cookie_kwargs(int(api_settings.ACCESS_TOKEN_LIFETIME.total_seconds())),
            )
            
            if api_settings.ROTATE_REFRESH_TOKENS:
                response.set_cookie(
                    key="refresh_token",
                    value=str(refresh),
                    **_cookie_kwargs(int(api_settings.REFRESH_TOKEN_LIFETIME.total_seconds())),
                )

            return response

        except TokenError:

            return Response(
                {"message": "Invalid or expired refresh token"},
                status=status.HTTP_401_UNAUTHORIZED
            )