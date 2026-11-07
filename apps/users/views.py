import logging

from django.conf import settings
from django.db import models, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
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
    CanManageAccounts,
    ORDINARY_CMS_ROLES,
    ROLE_DEFINITIONS,
    effective_role,
    role_label,
    user_permissions,
)
from .authentication import trusted_origins
from .models import User
from .serializers import (
    AccountCreateSerializer,
    AccountSerializer,
    AccountUpdateSerializer,
    ChangePasswordSerializer,
)
from .tokens import (
    AUTH_HASH_CLAIM,
    REFRESH_COOKIE,
    SESSION_START_CLAIM,
    clear_session_cookies,
    compute_auth_hash,
    cookie_kwargs,
    issue_tokens,
    revoke_user_refresh_tokens,
    set_session_cookies,
    token_matches_user,
)

logger = logging.getLogger('security')

GENERIC_LOGIN_ERROR = "Invalid credentials"


# --------------------------------------------------------------------------- helpers
class LoginThrottle(AnonRateThrottle):
    scope = 'login'


class LoginAccountThrottle(SimpleRateThrottle):
    """Per-target-account limit so one account cannot be brute-forced from many IPs."""
    scope = 'login_account'

    def get_cache_key(self, request, view):
        email = str(request.data.get("email") or "").strip().lower()
        return self.cache_format % {"scope": self.scope, "ident": email} if email else None


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
        "first_name": user.first_name,
        "last_name": user.last_name,
        "name": user.get_full_name() or user.username,
        "role": role,
        "user_role": role,
        "role_label": role_label(role),
        "permissions": user_permissions(user),
    }


def _account_snapshot(user):
    return {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
    }


def check_account_access(request_user, target_user, action_name="manage"):
    """
    Enforces the Admin Access permission matrix:
    - Superadmin:
        - Cannot manage self through Admin Access.
        - Cannot manage another Superadmin through Admin Access.
        - Can manage regular Admins and ordinary CMS users.
    - Regular Admin:
        - Cannot manage self through Admin Access.
        - Cannot view, edit, change password for, or delete other Admins.
        - Cannot view or manage Superadmins.
        - Can manage ordinary CMS users only.
    - Ordinary CMS user:
        - Denied (handled by CanManageAccounts permission class).
    """
    req_role = effective_role(request_user)
    target_role = effective_role(target_user)
    is_target_super = target_role == "superadmin" or target_user.is_superuser

    if req_role == "superadmin":
        if request_user.id == target_user.id:
            return False, "Superadmins cannot manage their own account through Admin Access."
        if is_target_super:
            return False, "Superadmins cannot manage other Superadmins through Admin Access."
        return True, ""

    if req_role == "admin":
        if request_user.id == target_user.id:
            return False, "Admins cannot manage their own account through Admin Access."
        if is_target_super:
            return False, "Admins cannot view or manage Superadmin accounts."
        if target_role == "admin":
            return False, "Admins cannot view or manage other Admin accounts."
        if target_role not in ORDINARY_CMS_ROLES:
            return False, "Admins can only manage ordinary CMS user accounts."
        return True, ""

    return False, "You do not have permission to manage accounts."


# --------------------------------------------------------------------------- authentication
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle, LoginAccountThrottle]

    def post(self, request):
        blocked = reject_untrusted_origin(request)
        if blocked:
            return blocked

        email = (request.data.get("email") or "").strip().lower()
        password = request.data.get("password") or ""
        if not email or not password:
            return Response({"error": "email and password are required"}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email).first()
        if user is None or not user.check_password(password):
            logger.warning(f"Login failed for email: {email}")
            return Response({"error": GENERIC_LOGIN_ERROR}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            logger.warning(f"Login rejected for deactivated account: {email}")
            return Response({"error": GENERIC_LOGIN_ERROR}, status=status.HTTP_401_UNAUTHORIZED)

        response = Response(serialize_session_user(user), status=status.HTTP_200_OK)
        refresh, access = issue_tokens(user)
        set_session_cookies(response, refresh, access)
        logger.info(f"Login successful for user id {user.pk} ({user.email})")
        log_activity(request, user=user, action="login", module="auth", target_id=user.id,
                     target_repr=user.email, description=f"{user.email} logged in")
        return response


class RefreshTokenView(APIView):
    """
    Rotates the refresh token (issuing a new one and blacklisting the old one).
    Enforces sliding expiration up to JWT_SESSION_MAX_LIFETIME from initial login.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def _reject(self, message, reason):
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
            refresh = RefreshToken(raw_token)
        except TokenError:
            return self._reject("Invalid or expired refresh token", "invalid, expired or blacklisted token")

        user = User.objects.filter(
            **{api_settings.USER_ID_FIELD: refresh.get(api_settings.USER_ID_CLAIM)}
        ).first()
        if user is None or not user.is_active:
            self._blacklist(refresh)
            return self._reject("Session is no longer valid", "unknown or inactive user")

        if not token_matches_user(refresh, user):
            self._blacklist(refresh)
            return self._reject("Session is no longer valid. Please log in again.",
                                f"credential changed for user {user.pk}")

        now = timezone.now()
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

        response = Response({"message": "password changed successfully"})
        refresh, access = issue_tokens(user)
        set_session_cookies(response, refresh, access)
        logger.info(f"Password changed for user id {user.pk}")
        log_activity(request, user=user, action="password_change", module="auth", target_id=user.id,
                     target_repr=user.email, description="Changed own password; other sessions signed out")
        return response


# --------------------------------------------------------------------------- account management
class AccountListCreateView(APIView):
    permission_classes = [IsAuthenticated, CanManageAccounts]
    throttle_classes = [AccountManagementThrottle]

    def get(self, request):
        req_role = effective_role(request.user)
        if req_role == "superadmin":
            # Superadmin can view regular Admins and CMS users, never Superadmins or self
            users = User.objects.exclude(id=request.user.id).exclude(
                models.Q(is_superuser=True) | models.Q(role='superadmin')
            ).order_by('-date_joined')
        elif req_role == "admin":
            # Regular Admin can view only ordinary CMS users
            users = User.objects.filter(role__in=ORDINARY_CMS_ROLES).exclude(
                id=request.user.id
            ).order_by('-date_joined')
        else:
            users = User.objects.none()

        return Response(AccountSerializer(users, many=True).data, status=status.HTTP_200_OK)

    def post(self, request):
        req_role = effective_role(request.user)
        target_role = request.data.get('role', 'cms_user')

        if target_role == 'superadmin':
            return Response(
                {"role": ["Cannot create a Superadmin account through Admin Access."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if req_role == 'admin' and target_role not in ORDINARY_CMS_ROLES:
            return Response(
                {"role": ["Admins can only create ordinary CMS user accounts."]},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AccountCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        logger.info(f"{req_role} id {request.user.pk} created account id {user.pk} with role '{user.role}'")
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
    permission_classes = [IsAuthenticated, CanManageAccounts]
    throttle_classes = [AccountManagementThrottle]

    def get_object(self, user_id):
        return get_object_or_404(User, id=user_id)

    def get(self, request, user_id):
        target = self.get_object(user_id)
        allowed, reason = check_account_access(request.user, target, action_name="view")
        if not allowed:
            return Response({"detail": reason}, status=status.HTTP_403_FORBIDDEN)
        return Response(AccountSerializer(target).data, status=status.HTTP_200_OK)

    def patch(self, request, user_id):
        target = self.get_object(user_id)
        allowed, reason = check_account_access(request.user, target, action_name="edit")
        if not allowed:
            return Response({"detail": reason}, status=status.HTTP_403_FORBIDDEN)

        req_role = effective_role(request.user)
        new_role = request.data.get('role')
        if new_role == 'superadmin':
            return Response(
                {"role": ["Cannot promote an account to Superadmin."]},
                status=status.HTTP_403_FORBIDDEN,
            )
        if req_role == 'admin' and new_role and new_role not in ORDINARY_CMS_ROLES:
            return Response(
                {"role": ["Admins can only assign ordinary CMS user roles."]},
                status=status.HTTP_403_FORBIDDEN,
            )

        before = _account_snapshot(target)
        old_password_hash = target.password
        serializer = AccountUpdateSerializer(target, data=request.data, partial=True, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            user = serializer.save()
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
                         description=f"Set a new password for {user.email}; their sessions were signed out")
        logger.info(f"{req_role} id {request.user.pk} updated account id {user.pk}")
        return Response(AccountSerializer(user).data, status=status.HTTP_200_OK)

    def put(self, request, user_id):
        return self.patch(request, user_id)

    def delete(self, request, user_id):
        target = self.get_object(user_id)
        allowed, reason = check_account_access(request.user, target, action_name="delete")
        if not allowed:
            return Response({"detail": reason}, status=status.HTTP_403_FORBIDDEN)

        if is_superadmin(target) and target.is_active and get_active_superadmin_count() <= 1:
            return Response({"detail": "Cannot delete the last active superadmin."}, status=status.HTTP_400_BAD_REQUEST)

        req_role = effective_role(request.user)
        target_email, target_id, snapshot = target.email, target.id, _account_snapshot(target)
        target.delete()
        logger.info(f"{req_role} id {request.user.pk} deleted account id {target_id}")
        log_activity(request, action="delete", module="accounts", target_id=target_id, target_repr=target_email,
                     description=f"Deleted account {target_email}",
                     changes={k: {"before": v, "after": None} for k, v in snapshot.items()})
        return Response(status=status.HTTP_204_NO_CONTENT)


# Legacy aliases share the account-management logic.
UserView = AccountListCreateView
UserDetailView = AccountDetailView
