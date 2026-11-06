import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import models, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.activity_logging import diff_snapshots, log_activity
from apps.core.permissions import (
    ROLE_DEFINITIONS, IsSuperadminOnly, effective_role, role_label, user_permissions,
)
from .authentication import trusted_origins
from .models import User
from .serializers import (
    AccountCreateSerializer, AccountSerializer, AccountUpdateSerializer,
    ChangePasswordSerializer, ForgotPasswordSerializer, ResetPasswordSerializer,
)
from .tokens import (
    AUTH_HASH_CLAIM, REFRESH_COOKIE, SESSION_START_CLAIM, clear_session_cookies, compute_auth_hash,
    cookie_kwargs, issue_tokens, revoke_user_refresh_tokens, set_session_cookies, token_matches_user,
)

logger = logging.getLogger('security')

GENERIC_LOGIN_ERROR = "Invalid credentials"
GENERIC_RESET_MESSAGE = "If an account with this email exists, a password reset link has been sent."


# --------------------------------------------------------------------------- helpers
class LoginThrottle(AnonRateThrottle):
    scope = 'login'


class LoginAccountThrottle(SimpleRateThrottle):
    """Per-target-account limit so one account cannot be brute-forced from many IPs."""
    scope = 'login_account'

    def get_cache_key(self, request, view):
        email = str(request.data.get("email") or "").strip().lower()
        return self.cache_format % {"scope": self.scope, "ident": email} if email else None


class PasswordResetThrottle(AnonRateThrottle):
    scope = 'password_reset'


class PasswordResetAccountThrottle(LoginAccountThrottle):
    scope = 'password_reset_account'


class AccountManagementThrottle(UserRateThrottle):
    scope = 'account_management'


def reject_untrusted_origin(request):
    """For unauthenticated browser endpoints: refuse an explicit, untrusted Origin."""
    origin = (request.META.get("HTTP_ORIGIN") or "").rstrip("/")
    if not origin:
        return None
    if origin == f"{request.scheme}://{request.get_host()}" or origin in trusted_origins():
        return None
    return Response({"detail": "Origin is not trusted."}, status=status.HTTP_403_FORBIDDEN)


def is_superadmin(user):
    return effective_role(user) == "superadmin"


def get_active_superadmin_count():
    return User.objects.filter(is_active=True).filter(
        models.Q(role='superadmin') | models.Q(is_superuser=True)
    ).count()


def serialize_session_user(user):
    role = effective_role(user)
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "name": user.get_full_name() or user.username,
        "role": role,
        "user_role": role,
        "role_label": role_label(role),
        "permissions": user_permissions(user),
    }


def _account_snapshot(user):
    return {"username": user.username, "email": user.email, "role": user.role, "is_active": user.is_active}


# --------------------------------------------------------------------------- authentication
class LoginView(APIView):
    # Ignore any stale access cookie (e.g. of a deleted user) so it cannot block a new login.
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle, LoginAccountThrottle]

    def post(self, request):
        blocked = reject_untrusted_origin(request)
        if blocked:
            return blocked

        email = str(request.data.get("email") or "").strip()
        password = request.data.get("password") or ""

        user = User.objects.filter(email__iexact=email).first() if email else None
        # Same response for unknown email, wrong password and deactivated accounts.
        if not user or not user.check_password(password) or not user.is_active:
            logger.warning("Failed login attempt")
            return Response({"message": GENERIC_LOGIN_ERROR}, status=status.HTTP_401_UNAUTHORIZED)

        refresh, access = issue_tokens(user)
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        response = Response(
            {"message": "Login successful", "user": serialize_session_user(user)},
            status=status.HTTP_200_OK,
        )
        set_session_cookies(response, refresh, access)
        logger.info(f"Successful login: user id {user.pk}")
        log_activity(request, user=user, action="login", module="auth", target_id=user.id,
                     target_repr=user.email, description=f"{user.email} logged in")
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
        return clear_session_cookies(response)

    def _blacklist(self, refresh):
        try:
            refresh.blacklist()
        except (TokenError, AttributeError):
            pass

    def post(self, request):
        blocked = reject_untrusted_origin(request)
        if blocked:
            return blocked

        raw_token = request.COOKIES.get(REFRESH_COOKIE)
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

        # Token must be bound to the user's current password (invalidated by changes/resets).
        if not token_matches_user(refresh, user):
            self._blacklist(refresh)
            return self._reject("Session is no longer valid. Please log in again.",
                                f"credential changed for user {user.pk}")

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
            refresh[AUTH_HASH_CLAIM] = compute_auth_hash(user)
            refresh["exp"] = min(int(refresh["exp"]), session_end)
            # Track the rotated token so a later password change can revoke it in bulk.
            try:
                refresh.outstand()
            except Exception:
                pass

        new_access = refresh.access_token
        new_access["exp"] = min(int(new_access["exp"]), session_end)

        response = Response({"message": "Access token refreshed"}, status=status.HTTP_200_OK)
        now_ts = int(now.timestamp())
        response.set_cookie(
            key="access_token",
            value=str(new_access),
            **cookie_kwargs(max(int(new_access["exp"]) - now_ts, 0)),
        )
        if api_settings.ROTATE_REFRESH_TOKENS:
            response.set_cookie(
                key=REFRESH_COOKIE,
                value=str(refresh),
                **cookie_kwargs(max(int(refresh["exp"]) - now_ts, 0)),
            )
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE)
        response = Response({"message": "Logout successful"}, status=status.HTTP_205_RESET_CONTENT)
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except TokenError:
                pass
        clear_session_cookies(response)
        logger.info(f"Logout: user id {request.user.pk}")
        log_activity(request, user=request.user, action="logout", module="auth", target_id=request.user.id,
                     target_repr=request.user.email, description=f"{request.user.email} logged out")
        return response


class UserMeView(APIView):
    """Read-only profile of the authenticated user, with role label and effective permissions."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = serialize_session_user(request.user)
        data.update({"is_active": request.user.is_active, "date_joined": request.user.date_joined})
        response = Response(data, status=status.HTTP_200_OK)
        response["Cache-Control"] = "private, no-store"
        return response


class RoleListView(APIView):
    """Predefined roles (code-controlled) for labels and role-assignment pickers."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([
            {"value": key, "label": spec["label"], "description": spec["description"]}
            for key, spec in ROLE_DEFINITIONS.items()
        ])


# --------------------------------------------------------------------------- passwords
def _invalidate_sessions(user):
    """Credentials issued before a password change stop working (see apps/users/tokens.py)."""
    revoke_user_refresh_tokens(user)


class ChangePasswordView(APIView):
    """Self-service password change for every authenticated role."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data, context={"user": user})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(serializer.validated_data["old_password"]):
            logger.warning(f"Password change failed for user id {user.pk}: incorrect old password")
            return Response({"error": "old password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        _invalidate_sessions(user)

        # Every other device is now signed out; this device gets fresh credentials.
        response = Response({"message": "password changed successfully"})
        refresh, access = issue_tokens(user)
        set_session_cookies(response, refresh, access)
        logger.info(f"Password changed for user id {user.pk}")
        log_activity(request, user=user, action="password_change", module="auth", target_id=user.id,
                     target_repr=user.email, description="Changed own password; other sessions signed out")
        return response


def _reset_disallowed(user):
    # Superadmin credentials are managed through the deployment environment only.
    return effective_role(user) == "superadmin" or user.is_superuser


class PasswordResetRequestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle, PasswordResetAccountThrottle]

    def post(self, request):
        blocked = reject_untrusted_origin(request)
        if blocked:
            return blocked
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        frontend_url = getattr(settings, "FRONTEND_URL", "")

        if user is None:
            logger.info("Password reset requested for an unknown or inactive email")
        elif _reset_disallowed(user):
            logger.warning(f"Password reset requested for superadmin user id {user.pk}; ignored by policy")
        elif not frontend_url or not getattr(settings, "EMAIL_CONFIGURED", False):
            logger.error("Password reset email not sent: FRONTEND_URL or email delivery is not configured")
        else:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = f"{frontend_url}/reset-password?uid={uid}&token={token}"
            minutes = max(int(getattr(settings, "PASSWORD_RESET_TIMEOUT", 3600)) // 60, 1)
            message = (
                f"Hello {user.username},\n\n"
                f"We received a request to reset your password for CSITABMC CMS.\n"
                f"Please click the link below to set a new password:\n\n"
                f"{reset_url}\n\n"
                f"This link can be used once and expires in {minutes} minutes.\n"
                f"If you did not request this password reset, please ignore this email.\n"
            )
            try:
                send_mail("Password Reset Request - CSIT Association of BMC", message,
                          settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
                logger.info(f"Password reset email dispatched for user id {user.pk}")
                log_activity(request, user=user, action="password_reset_request", module="auth",
                             target_id=user.id, target_repr=user.email,
                             description="Password reset link emailed")
            except Exception as exc:  # never expose SMTP details to the client
                logger.error(f"Failed to send password reset email for user id {user.pk}: {exc.__class__.__name__}")

        return Response({"message": GENERIC_RESET_MESSAGE}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle]

    def post(self, request):
        blocked = reject_untrusted_origin(request)
        if blocked:
            return blocked
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        invalid = Response({"error": "Invalid or expired reset link."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user_id = force_str(urlsafe_base64_decode(serializer.validated_data["uid"]))
            user = User.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            logger.warning("Invalid password reset confirmation attempt")
            return invalid

        # Tokens are time-limited (PASSWORD_RESET_TIMEOUT) and single-use: they hash the
        # current password, so they stop validating once the password is changed.
        if _reset_disallowed(user) or not default_token_generator.check_token(user, serializer.validated_data["token"]):
            logger.warning(f"Password reset token rejected for user id {user.pk}")
            return invalid

        new_password = serializer.validated_data["new_password"]
        from .serializers import run_password_validators
        run_password_validators(new_password, user=user)

        user.set_password(new_password)
        user.save(update_fields=["password"])
        _invalidate_sessions(user)
        logger.info(f"Password reset completed for user id {user.pk}")
        log_activity(request, user=user, action="password_reset", module="auth", target_id=user.id,
                     target_repr=user.email, description="Password reset via emailed link; all sessions signed out")
        return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)


ResetPasswordView = PasswordResetConfirmView


# --------------------------------------------------------------------------- account management
class AccountListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsSuperadminOnly]
    throttle_classes = [AccountManagementThrottle]

    def get(self, request):
        users = User.objects.all().order_by('-date_joined')
        return Response(AccountSerializer(users, many=True).data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = AccountCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        logger.info(f"Superadmin id {request.user.pk} created account id {user.pk} with role '{user.role}'")
        log_activity(request, action="create", module="accounts", target_id=user.id, target_repr=user.email,
                     description=f"Created account {user.email} with role {role_label(user.role)}",
                     changes={k: {"before": None, "after": v} for k, v in _account_snapshot(user).items()})
        return Response(AccountSerializer(user).data, status=status.HTTP_201_CREATED)


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("false", "0", "no", "off"):
            return False
        if lowered in ("true", "1", "yes", "on"):
            return True
    return None


class AccountDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSuperadminOnly]
    throttle_classes = [AccountManagementThrottle]

    def get_object(self, user_id):
        return get_object_or_404(User, id=user_id)

    def get(self, request, user_id):
        return Response(AccountSerializer(self.get_object(user_id)).data, status=status.HTTP_200_OK)

    def patch(self, request, user_id):
        user = self.get_object(user_id)
        is_super = is_superadmin(user)
        deactivating = _parse_bool(request.data.get('is_active')) is False
        new_role = request.data.get('role')

        if request.user.id == user.id and deactivating:
            return Response({"detail": "You cannot deactivate your own account."}, status=status.HTTP_400_BAD_REQUEST)
        if is_super and user.is_active and deactivating and get_active_superadmin_count() <= 1:
            return Response({"detail": "Cannot deactivate the last active superadmin."}, status=status.HTTP_400_BAD_REQUEST)
        if (is_super and user.is_active and new_role and new_role != 'superadmin'
                and get_active_superadmin_count() <= 1):
            return Response({"detail": "Cannot demote the last active superadmin."}, status=status.HTTP_400_BAD_REQUEST)

        before = _account_snapshot(user)
        old_password_hash = user.password
        serializer = AccountUpdateSerializer(user, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            user = serializer.save()
            if is_super and user.is_superuser and user.role != 'superadmin':
                # Keep the Django superuser flag consistent with an explicit demotion.
                user.is_superuser = False
                user.is_staff = False
                user.save(update_fields=["is_superuser", "is_staff"])
            password_changed = user.password != old_password_hash
            if password_changed:
                _invalidate_sessions(user)

        changes = diff_snapshots(before, _account_snapshot(user))
        if changes:
            action = "update"
            if set(changes) == {"is_active"}:
                action = "status_change"
            elif set(changes) == {"role"}:
                action = "role_change"
            log_activity(request, action=action, module="accounts", target_id=user.id, target_repr=user.email,
                         description=f"Updated account {user.email}", changes=changes)
        if password_changed:
            log_activity(request, action="password_change", module="accounts", target_id=user.id,
                         target_repr=user.email,
                         description=f"Superadmin set a new password for {user.email}; their sessions were signed out")
        logger.info(f"Superadmin id {request.user.pk} updated account id {user.pk}")
        return Response(AccountSerializer(user).data, status=status.HTTP_200_OK)

    def put(self, request, user_id):
        return self.patch(request, user_id)

    def delete(self, request, user_id):
        user = self.get_object(user_id)
        if request.user.id == user.id:
            return Response({"detail": "You cannot delete your own account."}, status=status.HTTP_400_BAD_REQUEST)
        if is_superadmin(user) and user.is_active and get_active_superadmin_count() <= 1:
            return Response({"detail": "Cannot delete the last active superadmin."}, status=status.HTTP_400_BAD_REQUEST)

        target_email, target_id, snapshot = user.email, user.id, _account_snapshot(user)
        user.delete()
        logger.info(f"Superadmin id {request.user.pk} deleted account id {target_id}")
        log_activity(request, action="delete", module="accounts", target_id=target_id, target_repr=target_email,
                     description=f"Deleted account {target_email}",
                     changes={k: {"before": v, "after": None} for k, v in snapshot.items()})
        return Response(status=status.HTTP_204_NO_CONTENT)


# Legacy routes (/api/v1/users/ and /api/v1/users/<id>/) share the account-management logic.
UserView = AccountListCreateView
UserDetailView = AccountDetailView
