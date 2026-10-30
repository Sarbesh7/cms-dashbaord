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
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
from django.utils import timezone
from rest_framework_simplejwt.settings import api_settings



logger = logging.getLogger('security')


def _cookie_kwargs(max_age):
    return {
        "httponly": True,
        "secure": not settings.DEBUG,
        "samesite": "None" if not settings.DEBUG else "Lax",
        "max_age": max_age,
    }


# Claim carried through every rotation so the absolute session cap counts from login.
SESSION_START_CLAIM = "session_start"


def _clear_session_cookies(response):
    response.set_cookie("access_token", "", **_cookie_kwargs(0))
    response.set_cookie("refresh_token", "", **_cookie_kwargs(0))
    return response


class LoginView(APIView):
    # Ignore any stale access cookie (e.g. of a deleted user) so it cannot block a new login.
    authentication_classes = []
    permission_classes = [AllowAny]
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
        refresh[SESSION_START_CLAIM] = int(timezone.now().timestamp())
        access = refresh.access_token

        response = Response(
            {
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "user_role": "superadmin" if (user.is_superuser or user.role == "superadmin") else user.role,
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
    

def is_superadmin(user):
    return bool(
        user and user.is_authenticated and (user.is_superuser or getattr(user, 'role', '') == 'superadmin')
    )


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
        if not is_superadmin(request.user):
            # Admin cannot modify peer Admin or Superadmin accounts
            if user.id != request.user.id and (user.role in ['admin', 'superadmin'] or user.is_superuser):
                logger.warning(
                    f"Forbidden PUT mutation attempt by Admin '{request.user.email}' on peer/superior account '{user.email}'"
                )
                return Response(
                    {"detail": "Admins cannot modify peer Admin or Superadmin accounts."},
                    status=status.HTTP_403_FORBIDDEN
                )
            # Admin cannot assign administrative roles
            new_role = request.data.get('role')
            if new_role in ['admin', 'superadmin'] and new_role != user.role:
                return Response(
                    {"detail": "Only superadmins can assign administrative roles."},
                    status=status.HTTP_403_FORBIDDEN
                )

        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Admin '{request.user.email}' updated user '{user.email}'")
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        logger.warning(f"User update failed by Admin '{request.user.email}'. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        if not is_superadmin(request.user):
            # Admin cannot modify peer Admin or Superadmin accounts
            if user.id != request.user.id and (user.role in ['admin', 'superadmin'] or user.is_superuser):
                logger.warning(
                    f"Forbidden PATCH mutation attempt by Admin '{request.user.email}' on peer/superior account '{user.email}'"
                )
                return Response(
                    {"detail": "Admins cannot modify peer Admin or Superadmin accounts."},
                    status=status.HTTP_403_FORBIDDEN
                )
            # Admin cannot assign administrative roles
            new_role = request.data.get('role')
            if new_role in ['admin', 'superadmin'] and new_role != user.role:
                return Response(
                    {"detail": "Only superadmins can assign administrative roles."},
                    status=status.HTTP_403_FORBIDDEN
                )

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
        if not is_superadmin(request.user):
            if user.role in ['admin', 'superadmin'] or user.is_superuser:
                logger.warning(
                    f"Forbidden delete attempt by Admin '{request.user.email}' on peer/superior account '{user.email}'"
                )
                return Response(
                    {"detail": "Admins cannot delete peer Admin or Superadmin accounts."},
                    status=status.HTTP_403_FORBIDDEN
                )

        user.delete()
        logger.info(f"Admin '{request.user.email}' deleted user '{user.email}'")
        return Response(status=status.HTTP_204_NO_CONTENT)

class UserView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [UserRateThrottle]
    
    def post(self, request):
        target_role = request.data.get('role', 'cms_user')
        if target_role in ['admin', 'superadmin'] and not is_superadmin(request.user):
            logger.warning(
                f"Unauthorized admin creation attempt by non-superadmin '{request.user.email}'"
            )
            return Response(
                {"detail": "Only superadmins can create administrative accounts."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = UserCreateSerializer(data=request.data) 
        if serializer.is_valid():
            user = serializer.save()
            logger.info(f"Admin '{request.user.email}' successfully created a new user: '{user.email}'")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        logger.warning(f"User creation failed by Admin '{request.user.email}'. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    def get(self, request):
        users = User.objects.all().order_by('-date_joined')
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

        _clear_session_cookies(response)

        logger.info(f"Logout: {request.user.email}")

        return response

class RefreshTokenView(APIView):
    """Rotate the refresh token (sliding 7-day window) within the absolute session cap."""
    # Authenticated only by the refresh cookie; a stale access cookie must not
    # short-circuit the request before session cookies can be cleared.
    authentication_classes = []
    permission_classes = [AllowAny]

    def _reject(self, message, reason):
        # Never log or return token values.
        logger.info(f"Refresh rejected: {reason}")
        response = Response({"message": message}, status=status.HTTP_401_UNAUTHORIZED)
        return _clear_session_cookies(response)

    def _blacklist(self, refresh):
        try:
            refresh.blacklist()
        except (TokenError, AttributeError):
            pass

    def post(self, request):
        raw_token = request.COOKIES.get("refresh_token")
        if not raw_token:
            return self._reject("Refresh token missing", "missing token")

        try:
            # Verifies signature, expiry and the blacklist (rotated or logged-out tokens).
            refresh = RefreshToken(raw_token)
        except TokenError:
            return self._reject("Invalid or expired refresh token", "invalid, expired or blacklisted token")

        user = User.objects.filter(
            **{api_settings.USER_ID_FIELD: refresh.get(api_settings.USER_ID_CLAIM)}
        ).first()
        if user is None or not user.is_active:
            self._blacklist(refresh)
            return self._reject("Session is no longer valid", "unknown or inactive user")

        now = timezone.now()
        # Tokens issued before the cap existed carry no session_start; count from their issue time.
        session_start = int(refresh.get(SESSION_START_CLAIM, refresh.get("iat")))
        session_end = int(session_start + settings.JWT_SESSION_MAX_LIFETIME.total_seconds())
        if now.timestamp() >= session_end:
            self._blacklist(refresh)
            return self._reject("Session expired. Please log in again.", f"session cap reached for user {user.pk}")

        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                self._blacklist(refresh)
            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            refresh[SESSION_START_CLAIM] = session_start
            refresh["exp"] = min(int(refresh["exp"]), session_end)

        new_access = refresh.access_token
        new_access["exp"] = min(int(new_access["exp"]), session_end)

        response = Response({"message": "Access token refreshed"}, status=status.HTTP_200_OK)
        now_ts = int(now.timestamp())
        response.set_cookie(
            key="access_token",
            value=str(new_access),
            **_cookie_kwargs(max(int(new_access["exp"]) - now_ts, 0)),
        )
        if api_settings.ROTATE_REFRESH_TOKENS:
            response.set_cookie(
                key="refresh_token",
                value=str(refresh),
                **_cookie_kwargs(max(int(refresh["exp"]) - now_ts, 0)),
            )
        return response
