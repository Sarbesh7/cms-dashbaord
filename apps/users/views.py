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


logger = logging.getLogger('security')


class LoginView(APIView):
    throttle_classes = [AnonRateThrottle]
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        user = User.objects.filter(email=email).first()

        if user and user.check_password(password):
            refresh = RefreshToken.for_user(user)
            logger.info(f"Successful login for user: {email}")
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token)
                },
                status=status.HTTP_200_OK
            )
        
        logger.warning(f"Failed login attempt for email: {email}")
        return Response(
            {"message": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED
        )
    

class UserView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    throttle_classes = [UserRateThrottle]
    
    def post(self, request):
        serializer = UserCreateSerializer(data=request.data) 
        if serializer.is_valid():
            user = serializer.save()
            logger.info(f"Admin '{request.user.email}' successfully created a new user: '{user.email}'")
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        logger.warning(f"User creation failed by Admin '{request.user.email}'. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_403_FORBIDDEN)


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


class TestEmailView(APIView):
    # Removing permission guard if it's meant to be public, but adding auth logging if user context is available
    def get(self, request):
        caller = request.user.email if request.user.is_authenticated else "Anonymous"
        try:
            send_mail(
                subject="SMTP Test",
                message="Congratulations! Your Django SMTP setup is working.",
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[settings.EMAIL_HOST_USER],
                fail_silently=False,
                )
            logger.info(f"SMTP Test email successfully sent by operator: '{caller}'")
            return Response({
                "message": "Email sent successfully"
            })
        except Exception as e:
            logger.error(f"SMTP Test email delivery failed for operator '{caller}'. Error Details: {str(e)}")
            return Response(
                {"error": "Email system configuration issue encountered."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ForgotPasswordView(APIView):
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            try:
                user = User.objects.get(email=email)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                
                reset_link = f"http://localhost:3000/reset-password/{uid}/{token}/"

                send_mail(
                    subject="Password Reset Request",
                    message=f"\nHi {user.username},\n\nClick the link below to reset your password:\n\n{reset_link}\n\nIf you didn't request this, ignore this email.\n",
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[user.email],
                    fail_silently=False
                )
                logger.info(f"Password reset link dispatched successfully to target: '{email}'")

            except User.DoesNotExist:
                # Log targeted profiling attempt while keeping the response completely opaque to prevent account enumeration
                logger.warning(f"Password reset requested for non-registered email: '{email}'")
                pass
            except Exception as mail_err:
                logger.error(f"Failed to transmit reset email to target '{email}'. Technical error: {str(mail_err)}")

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
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            uid = serializer.validated_data["uid"]
            token = serializer.validated_data["token"]
            new_password = serializer.validated_data["new_password"]    
            
            try:
                # Security Correction Note: Changed back to urlsafe_base64_decode to properly parse inbound base64 string tokens
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
        user_identity = request.user.email if request.user else "Unknown Identity"
        try:
            refresh_token = request.data.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            logger.info(f"User session successfully closed and token blacklisted for: '{user_identity}'")
            return Response(
                {"message": "Logout successful"},
                status=status.HTTP_205_RESET_CONTENT
            )
        except Exception as e:
            logger.warning(f"Logout execution failure for user '{user_identity}'. Error/Token invalidation Context: {str(e)}")
            return Response(
                {"error": "Invalid token"},
                status=status.HTTP_400_BAD_REQUEST
            )