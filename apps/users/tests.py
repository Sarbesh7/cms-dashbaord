from datetime import datetime, timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from apps.users.models import User
from apps.users.tokens import AUTH_HASH_CLAIM, compute_auth_hash


class AdminRoleHierarchyTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Superadmin
        self.superadmin = User.objects.create_superuser(
            username="superadmin",
            email="superadmin@csitabmc.org",
            password="Password123!",
            role="superadmin"
        )

        # Admin 1
        self.admin1 = User.objects.create_user(
            username="admin1",
            email="admin1@csitabmc.org",
            password="Password123!",
            role="admin"
        )

        # Admin 2
        self.admin2 = User.objects.create_user(
            username="admin2",
            email="admin2@csitabmc.org",
            password="Password123!",
            role="admin"
        )

        # CMS User
        self.cms_user = User.objects.create_user(
            username="cmsuser",
            email="cmsuser@csitabmc.org",
            password="Password123!",
            role="cms_user"
        )

    def test_unauthenticated_access_blocked(self):
        response = self.client.get("/api/v1/users/")
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_non_admin_access_blocked(self):
        self.client.force_authenticate(user=self.cms_user)
        response = self.client.get("/api/v1/users/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superadmin_can_create_admin(self):
        self.client.force_authenticate(user=self.superadmin)
        payload = {
            "username": "newadmin",
            "email": "newadmin@csitabmc.org",
            "password": "Password123!",
            "role": "admin"
        }
        response = self.client.post("/api/v1/users/", payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="newadmin@csitabmc.org").exists())

    def test_superadmin_can_edit_admin(self):
        self.client.force_authenticate(user=self.superadmin)
        payload = {"username": "admin1-updated"}
        response = self.client.patch(f"/api/v1/users/{self.admin1.id}/", payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.admin1.refresh_from_db()
        self.assertEqual(self.admin1.username, "admin1-updated")

    def test_superadmin_can_delete_admin(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.delete(f"/api/v1/users/{self.admin1.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.admin1.id).exists())

    def test_admin_cannot_create_admin_or_superadmin(self):
        self.client.force_authenticate(user=self.admin1)
        payload = {
            "username": "badadmin",
            "email": "badadmin@csitabmc.org",
            "password": "Password123!",
            "role": "admin"
        }
        response = self.client.post("/api/v1/users/", payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_create_any_user(self):
        self.client.force_authenticate(user=self.admin1)
        payload = {
            "username": "newcmsuser",
            "email": "newcmsuser@csitabmc.org",
            "password": "Password123!",
            "role": "cms_user"
        }
        response = self.client.post("/api/v1/users/", payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(email="newcmsuser@csitabmc.org").exists())

    def test_admin_cannot_edit_peer_admin(self):
        self.client.force_authenticate(user=self.admin1)
        payload = {"username": "admin2-hacked"}
        response = self.client.patch(f"/api/v1/users/{self.admin2.id}/", payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_edit_superadmin(self):
        self.client.force_authenticate(user=self.admin1)
        payload = {"username": "superadmin-hacked"}
        response = self.client.patch(f"/api/v1/users/{self.superadmin.id}/", payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_delete_peer_admin(self):
        self.client.force_authenticate(user=self.admin1)
        response = self.client.delete(f"/api/v1/users/{self.admin2.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(id=self.admin2.id).exists())

    def test_admin_cannot_delete_superadmin(self):
        self.client.force_authenticate(user=self.admin1)
        response = self.client.delete(f"/api/v1/users/{self.superadmin.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(id=self.superadmin.id).exists())

    def test_admin_cannot_elevate_cms_user_to_admin(self):
        self.client.force_authenticate(user=self.admin1)
        payload = {"role": "admin"}
        response = self.client.patch(f"/api/v1/users/{self.cms_user.id}/", payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_edit_or_delete_cms_user(self):
        self.client.force_authenticate(user=self.admin1)
        # Edit CMS user blocked
        patch_res = self.client.patch(f"/api/v1/users/{self.cms_user.id}/", {"username": "cms-updated"})
        self.assertEqual(patch_res.status_code, status.HTTP_403_FORBIDDEN)

        # Delete CMS user blocked
        del_res = self.client.delete(f"/api/v1/users/{self.cms_user.id}/")
        self.assertEqual(del_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(id=self.cms_user.id).exists())

    def test_cms_user_blocked_from_account_detail_and_mutations(self):
        self.client.force_authenticate(user=self.cms_user)
        self.assertEqual(self.client.get(f"/api/v1/users/{self.admin1.id}/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.patch(f"/api/v1/users/{self.cms_user.id}/", {"role": "admin"}).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(self.client.delete(f"/api/v1/users/{self.admin1.id}/").status_code, status.HTTP_403_FORBIDDEN)
        self.cms_user.refresh_from_db()
        self.assertEqual(self.cms_user.role, "cms_user")

    def test_unauthenticated_detail_returns_no_account_data(self):
        response = self.client.get(f"/api/v1/users/{self.admin1.id}/")
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
        self.assertNotIn("email", response.data)

    def test_admin_cannot_raise_own_role(self):
        self.client.force_authenticate(user=self.admin1)
        response = self.client.patch(f"/api/v1/users/{self.admin1.id}/", {"role": "superadmin"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.admin1.refresh_from_db()
        self.assertEqual(self.admin1.role, "admin")

    def test_self_edit_with_unchanged_email_succeeds(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.patch(
            f"/api/v1/users/{self.superadmin.id}/",
            {"username": "superadmin-renamed", "email": "superadmin@csitabmc.org", "role": "superadmin"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["username"], "superadmin-renamed")

    def test_edit_cannot_take_another_accounts_email(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.patch(f"/api/v1/users/{self.cms_user.id}/", {"email": "admin1@csitabmc.org"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_account_list_exposes_date_joined_but_no_password(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.get("/api/v1/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)
        for row in response.data:
            self.assertIn("date_joined", row)
            self.assertNotIn("password", row)


class JWTAuthSessionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="authuser",
            email="authuser@csitabmc.org",
            password="SecurePassword123!",
            role="admin"
        )

    def test_login_token_issuance_in_cookies(self):
        response = self.client.post("/api/v1/login/", {
            "email": "authuser@csitabmc.org",
            "password": "SecurePassword123!"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)
        self.assertTrue(response.cookies["access_token"]["httponly"])
        self.assertTrue(response.cookies["refresh_token"]["httponly"])

    def test_refresh_token_rotation_and_old_token_invalidation(self):
        login_res = self.client.post("/api/v1/login/", {
            "email": "authuser@csitabmc.org",
            "password": "SecurePassword123!"
        })
        original_refresh = login_res.cookies["refresh_token"].value

        # First refresh using cookie
        self.client.cookies["refresh_token"] = original_refresh
        refresh_res = self.client.post("/api/v1/users/refresh-token/")
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", refresh_res.cookies)
        self.assertIn("refresh_token", refresh_res.cookies)
        new_refresh = refresh_res.cookies["refresh_token"].value
        self.assertNotEqual(original_refresh, new_refresh)

        # Attempting to reuse old blacklisted refresh token must fail with 401
        self.client.cookies["refresh_token"] = original_refresh
        stale_res = self.client.post("/api/v1/users/refresh-token/")
        self.assertEqual(stale_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_token(self):
        login_res = self.client.post("/api/v1/login/", {
            "email": "authuser@csitabmc.org",
            "password": "SecurePassword123!"
        })
        refresh_token = login_res.cookies["refresh_token"].value
        access_token = login_res.cookies["access_token"].value

        # Authenticate and call logout
        self.client.cookies["access_token"] = access_token
        self.client.cookies["refresh_token"] = refresh_token
        logout_res = self.client.post("/api/v1/users/logout/", HTTP_AUTHORIZATION=f"Bearer {access_token}")
        self.assertEqual(logout_res.status_code, status.HTTP_205_RESET_CONTENT)

        # Attempting to refresh with the logged-out token must fail with 401
        self.client.cookies["refresh_token"] = refresh_token
        refresh_attempt = self.client.post("/api/v1/users/refresh-token/")
        self.assertEqual(refresh_attempt.status_code, status.HTTP_401_UNAUTHORIZED)


class JWTSessionPolicyTests(TestCase):
    """Sliding 7-day refresh, 30-day absolute cap, and cookie clearing on failure."""

    def setUp(self):
        self.client = APIClient()
        self.password = "SecurePassword123!"
        self.user = User.objects.create_user(
            username="policyuser", email="policy@csitabmc.org", password=self.password, role="admin"
        )
        self.t0 = timezone.now()

    def _at(self, moment):
        """Freeze both SimpleJWT's clock and the view's clock at `moment`."""
        return _FrozenClock(moment)

    def _login(self):
        with self._at(self.t0):
            res = self.client.post("/api/v1/login/", {"email": self.user.email, "password": self.password})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return res.cookies["refresh_token"].value

    def _refresh(self, token, moment):
        self.client.cookies["refresh_token"] = token
        with self._at(moment):
            return self.client.post("/api/v1/users/refresh-token/")

    def _assert_rejected_and_cleared(self, res):
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        for name in ("access_token", "refresh_token"):
            self.assertEqual(res.cookies[name].value, "")
            self.assertEqual(int(res.cookies[name]["max-age"]), 0)

    def test_sliding_refresh_on_day_6_and_day_12(self):
        token = self._login()
        res = self._refresh(token, self.t0 + timedelta(days=6))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(int(res.cookies["refresh_token"]["max-age"]), 7 * 24 * 3600)
        res = self._refresh(res.cookies["refresh_token"].value, self.t0 + timedelta(days=12))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_inactive_for_more_than_seven_days_expires(self):
        token = self._login()
        res = self._refresh(token, self.t0 + timedelta(days=7, minutes=1))
        self._assert_rejected_and_cleared(res)

    def test_absolute_session_cap(self):
        token = self._login()
        for day in (6, 12, 18, 24):
            res = self._refresh(token, self.t0 + timedelta(days=day))
            self.assertEqual(res.status_code, status.HTTP_200_OK, day)
            token = res.cookies["refresh_token"].value
        # The day-24 token is clamped to the cap (day 30), not day 31.
        self.assertLessEqual(int(res.cookies["refresh_token"]["max-age"]), 6 * 24 * 3600)
        payload = RefreshToken(token, verify=False).payload
        self.assertLessEqual(payload["exp"], int((self.t0 + timedelta(days=30)).timestamp()) + 1)

        res = self._refresh(token, self.t0 + timedelta(days=29, hours=23))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res = self._refresh(res.cookies["refresh_token"].value, self.t0 + timedelta(days=30, minutes=1))
        self._assert_rejected_and_cleared(res)

    def test_rotated_token_reuse_rejected_and_cleared(self):
        token = self._login()
        first = self._refresh(token, self.t0 + timedelta(hours=1))
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self._assert_rejected_and_cleared(self._refresh(token, self.t0 + timedelta(hours=2)))

    def test_malformed_token_rejected_without_leaking_it(self):
        self.client.cookies["refresh_token"] = "not-a-jwt"
        res = self.client.post("/api/v1/users/refresh-token/")
        self._assert_rejected_and_cleared(res)
        self.assertNotIn("not-a-jwt", res.content.decode())

    def test_missing_token_rejected(self):
        res = self.client.post("/api/v1/users/refresh-token/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_rejected(self):
        token = self._login()
        self.user.is_active = False
        self.user.save()
        self._assert_rejected_and_cleared(self._refresh(token, self.t0 + timedelta(minutes=5)))

    def test_deleted_user_rejected(self):
        token = self._login()
        self.user.delete()
        self._assert_rejected_and_cleared(self._refresh(token, self.t0 + timedelta(minutes=5)))

    def test_token_without_session_start_is_capped_from_its_issue_time(self):
        with self._at(self.t0):
            token = RefreshToken.for_user(self.user)
            token[AUTH_HASH_CLAIM] = compute_auth_hash(self.user)  # bound, but no session_start
            legacy = str(token)
        res = self._refresh(legacy, self.t0 + timedelta(days=1))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        rotated = RefreshToken(res.cookies["refresh_token"].value, verify=False)
        self.assertEqual(rotated["session_start"], int(self.t0.timestamp()))

    def test_token_without_password_binding_is_rejected(self):
        with self._at(self.t0):
            unbound = str(RefreshToken.for_user(self.user))  # issued outside LoginView
        self._assert_rejected_and_cleared(self._refresh(unbound, self.t0 + timedelta(minutes=5)))

    def test_stale_access_cookie_of_deleted_user_does_not_block_login(self):
        other = User.objects.create_user(
            username="gone", email="gone@csitabmc.org", password=self.password, role="cms_user"
        )
        stale_access = str(RefreshToken.for_user(other).access_token)
        other.delete()
        self.client.cookies["access_token"] = stale_access
        res = self.client.post("/api/v1/login/", {"email": self.user.email, "password": self.password})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_access_cookie_lifetime_is_one_hour(self):
        token = self._login()
        res = self._refresh(token, self.t0 + timedelta(minutes=50))
        self.assertEqual(int(res.cookies["access_token"]["max-age"]), 3600)


class _FrozenClock:
    """Freeze SimpleJWT, PyJWT and the refresh view at one moment."""

    def __init__(self, moment):
        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return moment.astimezone(tz) if tz else moment

        self.patches = [
            mock.patch("rest_framework_simplejwt.tokens.aware_utcnow", return_value=moment),
            mock.patch("jwt.api_jwt.datetime", FrozenDatetime),
            mock.patch("apps.users.views.timezone.now", return_value=moment),
        ]

    def __enter__(self):
        for p in self.patches:
            p.start()

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()


class AccountManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.superadmin = User.objects.create_superuser(
            username="superadmin",
            email="superadmin@csitabmc.org",
            password="Password123!",
            role="superadmin"
        )
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@csitabmc.org",
            password="Password123!",
            role="admin"
        )
        self.cms_user = User.objects.create_user(
            username="cmsuser",
            email="cmsuser@csitabmc.org",
            password="Password123!",
            role="cms_user"
        )

    def test_accounts_list_requires_superadmin(self):
        # Unauthenticated
        res = self.client.get("/api/v1/users/accounts/")
        self.assertIn(res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # CMS user
        self.client.force_authenticate(user=self.cms_user)
        res = self.client.get("/api/v1/users/accounts/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Admin
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/v1/users/accounts/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Superadmin
        self.client.force_authenticate(user=self.superadmin)
        res = self.client.get("/api/v1/users/accounts/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 3)
        row = res.data[0]
        for field in ['id', 'username', 'email', 'role', 'is_active', 'date_joined', 'last_login']:
            self.assertIn(field, row)

    def test_superadmin_can_create_account(self):
        self.client.force_authenticate(user=self.superadmin)
        payload = {
            "username": "ops_user",
            "email": "ops@csitabmc.org",
            "password": "Password123!",
            "role": "operations"
        }
        res = self.client.post("/api/v1/users/accounts/", payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["role"], "operations")
        self.assertTrue(User.objects.filter(email="ops@csitabmc.org").exists())

    def test_admin_blocked_from_account_endpoints(self):
        self.client.force_authenticate(user=self.admin)
        # Create
        res = self.client.post("/api/v1/users/accounts/", {
            "username": "hacked", "email": "hacked@csitabmc.org", "password": "Password123!", "role": "cms_user"
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Update
        res = self.client.patch(f"/api/v1/users/accounts/{self.cms_user.id}/", {"username": "hacked"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Delete
        res = self.client.delete(f"/api/v1/users/accounts/{self.cms_user.id}/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_delete_self(self):
        self.client.force_authenticate(user=self.superadmin)
        res = self.client.delete(f"/api/v1/users/accounts/{self.superadmin.id}/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot delete your own account", res.data.get("detail", ""))

    def test_cannot_deactivate_self(self):
        self.client.force_authenticate(user=self.superadmin)
        res = self.client.patch(f"/api/v1/users/accounts/{self.superadmin.id}/", {"is_active": False})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot deactivate your own account", res.data.get("detail", ""))

    def test_cannot_delete_last_active_superadmin(self):
        second_super = User.objects.create_superuser(
            username="super2", email="super2@csitabmc.org", password="Password123!", role="superadmin"
        )
        self.client.force_authenticate(user=second_super)
        # Delete first superadmin (now 1 remains)
        res = self.client.delete(f"/api/v1/users/accounts/{self.superadmin.id}/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        # Now second_super is the only superadmin. Attempting to delete from another session/target:
        # Create a temp third superadmin to try deleting the last one
        third_super = User.objects.create_user(
            username="super3", email="super3@csitabmc.org", password="Password123!", role="admin"
        )
        # Make third a superadmin
        third_super.role = "superadmin"
        third_super.save()

        # third deletes second_super (now third_super is last active superadmin)
        self.client.force_authenticate(user=third_super)
        self.client.delete(f"/api/v1/users/accounts/{second_super.id}/")

        # Now third_super tries to demote self or deactivate self (blocked by self rules),
        # but let's test last superadmin check with an inactive superadmin
        inactive_super = User.objects.create_user(
            username="inactive_super", email="inact@csitabmc.org", password="Password123!", role="superadmin", is_active=False
        )
        # Attempt to demote third_super:
        res = self.client.patch(f"/api/v1/users/accounts/{third_super.id}/", {"role": "admin"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot demote the last active superadmin", res.data.get("detail", ""))

    def test_superadmin_can_manage_other_accounts(self):
        self.client.force_authenticate(user=self.superadmin)
        # Deactivate admin
        res = self.client.patch(f"/api/v1/users/accounts/{self.admin.id}/", {"is_active": False})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_active)

        # Delete admin
        res = self.client.delete(f"/api/v1/users/accounts/{self.admin.id}/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.admin.id).exists())


class PasswordRecoveryAndChangeTests(TestCase):
    def setUp(self):
        from django.core import mail
        self.mail = mail
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@csitabmc.org",
            password="OriginalPassword123!",
            role="cms_user"
        )
        self.ops_user = User.objects.create_user(
            username="opsuser",
            email="opsuser@csitabmc.org",
            password="OriginalPassword123!",
            role="operations"
        )

    def test_self_service_password_change_cms_user(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "old_password": "OriginalPassword123!",
            "new_password": "BrandNewPassword123!"
        }
        res = self.client.post("/api/v1/users/change-password/", payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPassword123!"))

    def test_self_service_password_change_ops_user(self):
        self.client.force_authenticate(user=self.ops_user)
        payload = {
            "old_password": "OriginalPassword123!",
            "new_password": "BrandNewPassword123!"
        }
        res = self.client.post("/api/v1/users/change-password/", payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.ops_user.refresh_from_db()
        self.assertTrue(self.ops_user.check_password("BrandNewPassword123!"))

    def test_self_service_password_change_fails_on_incorrect_old_password(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "old_password": "WrongOldPassword123!",
            "new_password": "BrandNewPassword123!"
        }
        res = self.client.post("/api/v1/users/change-password/", payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_self_service_password_change_fails_on_short_new_password(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "old_password": "OriginalPassword123!",
            "new_password": "short"
        }
        res = self.client.post("/api/v1/users/change-password/", payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_request_sends_email(self):
        self.mail.outbox = []
        res = self.client.post("/api/v1/users/password-reset/", {"email": "testuser@csitabmc.org"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("password reset link has been sent", res.data.get("message", ""))
        self.assertEqual(len(self.mail.outbox), 1)
        self.assertIn("testuser@csitabmc.org", self.mail.outbox[0].to)
        self.assertIn("reset-password?uid=", self.mail.outbox[0].body)

    def test_password_reset_request_generic_response_for_unknown_email(self):
        self.mail.outbox = []
        res = self.client.post("/api/v1/users/password-reset/", {"email": "nonexistent@csitabmc.org"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("password reset link has been sent", res.data.get("message", ""))
        self.assertEqual(len(self.mail.outbox), 0)

    def test_password_reset_confirm_updates_password_and_invalidates_token(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        token = default_token_generator.make_token(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        # Confirm with new password
        payload = {
            "uid": uid,
            "token": token,
            "new_password": "RecoveredPassword123!"
        }
        res = self.client.post("/api/v1/users/password-reset-confirm/", payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("RecoveredPassword123!"))

        # Re-using the same token should fail
        res2 = self.client.post("/api/v1/users/password-reset-confirm/", payload)
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

