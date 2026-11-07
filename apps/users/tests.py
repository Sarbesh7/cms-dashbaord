from datetime import datetime, timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

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
            role="superadmin",
        )

        # Admin 1
        self.admin1 = User.objects.create_user(
            username="admin1",
            email="admin1@csitabmc.org",
            password="Password123!",
            role="admin",
        )

        # Admin 2
        self.admin2 = User.objects.create_user(
            username="admin2",
            email="admin2@csitabmc.org",
            password="Password123!",
            role="admin",
        )

        # CMS User
        self.cms_user = User.objects.create_user(
            username="cmsuser",
            email="cmsuser@csitabmc.org",
            password="Password123!",
            role="cms_user",
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
            "role": "admin",
        }
        response = self.client.post("/api/v1/users/", payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="newadmin@csitabmc.org").exists())

    def test_superadmin_cannot_create_superadmin(self):
        self.client.force_authenticate(user=self.superadmin)
        payload = {
            "username": "another_super",
            "email": "anothersuper@csitabmc.org",
            "password": "Password123!",
            "role": "superadmin",
        }
        response = self.client.post("/api/v1/users/", payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="anothersuper@csitabmc.org").exists())

    def test_superadmin_can_edit_admin(self):
        self.client.force_authenticate(user=self.superadmin)
        payload = {"username": "admin1-updated", "first_name": "Admin", "last_name": "One"}
        response = self.client.patch(f"/api/v1/users/{self.admin1.id}/", payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.admin1.refresh_from_db()
        self.assertEqual(self.admin1.username, "admin1-updated")
        self.assertEqual(self.admin1.first_name, "Admin")

    def test_superadmin_can_delete_admin(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.delete(f"/api/v1/users/{self.admin1.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.admin1.id).exists())

    def test_superadmin_cannot_edit_self_via_admin_access(self):
        self.client.force_authenticate(user=self.superadmin)
        payload = {"username": "superadmin-renamed"}
        response = self.client.patch(f"/api/v1/users/{self.superadmin.id}/", payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.superadmin.refresh_from_db()
        self.assertEqual(self.superadmin.username, "superadmin")

    def test_superadmin_cannot_delete_self(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.delete(f"/api/v1/users/{self.superadmin.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(id=self.superadmin.id).exists())

    def test_superadmin_cannot_manage_another_superadmin(self):
        super2 = User.objects.create_superuser(
            username="super2", email="super2@csitabmc.org", password="Password123!", role="superadmin"
        )
        self.client.force_authenticate(user=self.superadmin)
        # Cannot view
        self.assertEqual(self.client.get(f"/api/v1/users/{super2.id}/").status_code, status.HTTP_403_FORBIDDEN)
        # Cannot edit
        self.assertEqual(self.client.patch(f"/api/v1/users/{super2.id}/", {"username": "hacked"}).status_code, status.HTTP_403_FORBIDDEN)
        # Cannot delete
        self.assertEqual(self.client.delete(f"/api/v1/users/{super2.id}/").status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_create_admin_or_superadmin(self):
        self.client.force_authenticate(user=self.admin1)
        # Cannot create admin
        res1 = self.client.post("/api/v1/users/", {
            "username": "badadmin", "email": "badadmin@csitabmc.org", "password": "Password123!", "role": "admin"
        })
        self.assertEqual(res1.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot create superadmin
        res2 = self.client.post("/api/v1/users/", {
            "username": "badsuper", "email": "badsuper@csitabmc.org", "password": "Password123!", "role": "superadmin"
        })
        self.assertIn(res2.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])

    def test_admin_can_create_cms_user(self):
        self.client.force_authenticate(user=self.admin1)
        payload = {
            "username": "newcmsuser",
            "email": "newcmsuser@csitabmc.org",
            "password": "Password123!",
            "role": "cms_user",
        }
        response = self.client.post("/api/v1/users/", payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="newcmsuser@csitabmc.org").exists())

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

    def test_admin_can_edit_and_delete_cms_user(self):
        self.client.force_authenticate(user=self.admin1)
        # Edit CMS user succeeds
        patch_res = self.client.patch(f"/api/v1/users/{self.cms_user.id}/", {"username": "cms-updated"})
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.cms_user.refresh_from_db()
        self.assertEqual(self.cms_user.username, "cms-updated")

        # Delete CMS user succeeds
        del_res = self.client.delete(f"/api/v1/users/{self.cms_user.id}/")
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.cms_user.id).exists())

    def test_admin_cannot_manage_self_via_admin_access(self):
        self.client.force_authenticate(user=self.admin1)
        # Edit self blocked
        patch_res = self.client.patch(f"/api/v1/users/{self.admin1.id}/", {"username": "admin-renamed"})
        self.assertEqual(patch_res.status_code, status.HTTP_403_FORBIDDEN)

        # Delete self blocked
        del_res = self.client.delete(f"/api/v1/users/{self.admin1.id}/")
        self.assertEqual(del_res.status_code, status.HTTP_403_FORBIDDEN)

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

    def test_account_list_filters_by_permission_hierarchy(self):
        # Superadmin sees regular Admins and CMS user, but not self or other superadmins
        self.client.force_authenticate(user=self.superadmin)
        res_super = self.client.get("/api/v1/users/")
        self.assertEqual(res_super.status_code, status.HTTP_200_OK)
        super_ids = [u["id"] for u in res_super.data]
        self.assertNotIn(self.superadmin.id, super_ids)
        self.assertIn(self.admin1.id, super_ids)
        self.assertIn(self.admin2.id, super_ids)
        self.assertIn(self.cms_user.id, super_ids)

        # Admin sees ONLY ordinary CMS users, never other Admins or Superadmins
        self.client.force_authenticate(user=self.admin1)
        res_admin = self.client.get("/api/v1/users/")
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)
        admin_ids = [u["id"] for u in res_admin.data]
        self.assertNotIn(self.superadmin.id, admin_ids)
        self.assertNotIn(self.admin1.id, admin_ids)
        self.assertNotIn(self.admin2.id, admin_ids)
        self.assertIn(self.cms_user.id, admin_ids)


class JWTAuthSessionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="authuser",
            email="authuser@csitabmc.org",
            password="StrongPassword123!",
            role="admin",
        )

    def test_login_success_sets_http_only_cookies(self):
        response = self.client.post("/api/v1/login/", {
            "email": "authuser@csitabmc.org",
            "password": "StrongPassword123!",
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)
        self.assertTrue(response.cookies["access_token"]["httponly"])
        self.assertTrue(response.cookies["refresh_token"]["httponly"])
        self.assertEqual(response.cookies["refresh_token"]["samesite"], "Lax")

    def test_login_invalid_credentials_returns_generic_error(self):
        response = self.client.post("/api/v1/login/", {
            "email": "authuser@csitabmc.org",
            "password": "WrongPassword123!",
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"], "Invalid credentials")
        self.assertNotIn("access_token", response.cookies)

    def test_login_case_insensitive_email(self):
        response = self.client.post("/api/v1/login/", {
            "email": "AUTHUSER@csitabmc.org",
            "password": "StrongPassword123!",
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_blacklists_refresh_token_and_clears_cookies(self):
        login_res = self.client.post("/api/v1/login/", {
            "email": "authuser@csitabmc.org",
            "password": "StrongPassword123!",
        })
        refresh_raw = login_res.cookies["refresh_token"].value
        self.client.cookies["access_token"] = login_res.cookies["access_token"].value
        self.client.cookies["refresh_token"] = refresh_raw

        logout_res = self.client.post("/api/v1/users/logout/", HTTP_ORIGIN="http://testserver")
        self.assertEqual(logout_res.status_code, status.HTTP_205_RESET_CONTENT)

        # Refresh with blacklisted token must fail
        self.client.cookies["refresh_token"] = refresh_raw
        refresh_res = self.client.post("/api/v1/users/refresh-token/")
        self.assertEqual(refresh_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_rotation_and_blacklisting(self):
        login_res = self.client.post("/api/v1/login/", {
            "email": "authuser@csitabmc.org",
            "password": "StrongPassword123!",
        })
        first_refresh = login_res.cookies["refresh_token"].value
        self.client.cookies["refresh_token"] = first_refresh

        refresh_res = self.client.post("/api/v1/users/refresh-token/")
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        second_refresh = refresh_res.cookies["refresh_token"].value
        self.assertNotEqual(first_refresh, second_refresh)

        # Reusing the old rotated refresh token must fail
        self.client.cookies["refresh_token"] = first_refresh
        stale_res = self.client.post("/api/v1/users/refresh-token/")
        self.assertEqual(stale_res.status_code, status.HTTP_401_UNAUTHORIZED)


class AccountManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.superadmin = User.objects.create_superuser(
            username="superadmin", email="super@csitabmc.org", password="Password123!", role="superadmin"
        )
        self.admin = User.objects.create_user(
            username="adminuser", email="admin@csitabmc.org", password="Password123!", role="admin"
        )
        self.cms_user = User.objects.create_user(
            username="cmsuser", email="cmsuser@csitabmc.org", password="Password123!", role="cms_user"
        )

    def test_accounts_list_permissions(self):
        # Unauthenticated blocked
        res = self.client.get("/api/v1/users/accounts/")
        self.assertIn(res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # CMS user blocked
        self.client.force_authenticate(user=self.cms_user)
        self.assertEqual(self.client.get("/api/v1/users/accounts/").status_code, status.HTTP_403_FORBIDDEN)

        # Admin gets 200, only contains CMS user
        self.client.force_authenticate(user=self.admin)
        res_admin = self.client.get("/api/v1/users/accounts/")
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)
        admin_ids = [u["id"] for u in res_admin.data]
        self.assertIn(self.cms_user.id, admin_ids)
        self.assertNotIn(self.superadmin.id, admin_ids)
        self.assertNotIn(self.admin.id, admin_ids)

        # Superadmin gets 200, contains admin and CMS user, not self
        self.client.force_authenticate(user=self.superadmin)
        res_super = self.client.get("/api/v1/users/accounts/")
        self.assertEqual(res_super.status_code, status.HTTP_200_OK)
        super_ids = [u["id"] for u in res_super.data]
        self.assertIn(self.admin.id, super_ids)
        self.assertIn(self.cms_user.id, super_ids)
        self.assertNotIn(self.superadmin.id, super_ids)

    def test_superadmin_can_create_and_manage_admin(self):
        self.client.force_authenticate(user=self.superadmin)
        payload = {
            "username": "ops_user",
            "email": "ops@csitabmc.org",
            "password": "StrongPassword123!",
            "role": "operations",
        }
        res = self.client.post("/api/v1/users/accounts/", payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["role"], "operations")

        # Edit admin
        edit_res = self.client.patch(f"/api/v1/users/accounts/{self.admin.id}/", {"is_active": False})
        self.assertEqual(edit_res.status_code, status.HTTP_200_OK)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_active)

        # Delete admin
        del_res = self.client.delete(f"/api/v1/users/accounts/{self.admin.id}/")
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.admin.id).exists())

    def test_admin_cannot_manage_other_admins_or_superadmin(self):
        other_admin = User.objects.create_user(
            username="otheradmin", email="other@csitabmc.org", password="Password123!", role="admin"
        )
        self.client.force_authenticate(user=self.admin)

        # Cannot view other admin
        self.assertEqual(self.client.get(f"/api/v1/users/accounts/{other_admin.id}/").status_code, status.HTTP_403_FORBIDDEN)
        # Cannot edit other admin
        self.assertEqual(self.client.patch(f"/api/v1/users/accounts/{other_admin.id}/", {"username": "hacked"}).status_code, status.HTTP_403_FORBIDDEN)
        # Cannot delete other admin
        self.assertEqual(self.client.delete(f"/api/v1/users/accounts/{other_admin.id}/").status_code, status.HTTP_403_FORBIDDEN)

        # Cannot view superadmin
        self.assertEqual(self.client.get(f"/api/v1/users/accounts/{self.superadmin.id}/").status_code, status.HTTP_403_FORBIDDEN)
        # Cannot edit superadmin
        self.assertEqual(self.client.patch(f"/api/v1/users/accounts/{self.superadmin.id}/", {"username": "hacked"}).status_code, status.HTTP_403_FORBIDDEN)
        # Cannot delete superadmin
        self.assertEqual(self.client.delete(f"/api/v1/users/accounts/{self.superadmin.id}/").status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_manage_self_via_admin_access(self):
        # Superadmin self-manage blocked
        self.client.force_authenticate(user=self.superadmin)
        res1 = self.client.delete(f"/api/v1/users/accounts/{self.superadmin.id}/")
        self.assertEqual(res1.status_code, status.HTTP_403_FORBIDDEN)
        res2 = self.client.patch(f"/api/v1/users/accounts/{self.superadmin.id}/", {"is_active": False})
        self.assertEqual(res2.status_code, status.HTTP_403_FORBIDDEN)

        # Admin self-manage blocked
        self.client.force_authenticate(user=self.admin)
        res3 = self.client.delete(f"/api/v1/users/accounts/{self.admin.id}/")
        self.assertEqual(res3.status_code, status.HTTP_403_FORBIDDEN)
        res4 = self.client.patch(f"/api/v1/users/accounts/{self.admin.id}/", {"is_active": False})
        self.assertEqual(res4.status_code, status.HTTP_403_FORBIDDEN)


class PasswordComplexityPolicyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.superadmin = User.objects.create_superuser(
            username="superadmin", email="super@csitabmc.org", password="Password123!", role="superadmin"
        )
        self.admin = User.objects.create_user(
            username="adminuser", email="admin@csitabmc.org", password="Password123!", role="admin"
        )
        self.cms_user = User.objects.create_user(
            username="cmsuser", email="cmsuser@csitabmc.org", password="Password123!", role="cms_user"
        )

    def test_missing_uppercase_rejected(self):
        self.client.force_authenticate(user=self.superadmin)
        payload = {
            "username": "testuser1",
            "email": "test1@csitabmc.org",
            "password": "password123!",  # no uppercase
            "role": "admin",
        }
        res = self.client.post("/api/v1/users/accounts/", payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", res.data)
        self.assertTrue(any("uppercase" in str(msg).lower() for msg in res.data["password"]))

    def test_missing_number_rejected(self):
        self.client.force_authenticate(user=self.superadmin)
        payload = {
            "username": "testuser2",
            "email": "test2@csitabmc.org",
            "password": "PasswordSpecial!",  # no digit
            "role": "admin",
        }
        res = self.client.post("/api/v1/users/accounts/", payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", res.data)
        self.assertTrue(any("number" in str(msg).lower() for msg in res.data["password"]))

    def test_missing_special_character_rejected(self):
        self.client.force_authenticate(user=self.superadmin)
        payload = {
            "username": "testuser3",
            "email": "test3@csitabmc.org",
            "password": "Password123",  # no special char
            "role": "admin",
        }
        res = self.client.post("/api/v1/users/accounts/", payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", res.data)
        self.assertTrue(any("special character" in str(msg).lower() for msg in res.data["password"]))

    def test_short_password_rejected(self):
        self.client.force_authenticate(user=self.superadmin)
        payload = {
            "username": "testuser4",
            "email": "test4@csitabmc.org",
            "password": "P1!",  # too short
            "role": "admin",
        }
        res = self.client.post("/api/v1/users/accounts/", payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", res.data)
        self.assertTrue(any("8 characters" in str(msg) for msg in res.data["password"]))

    def test_multiple_missing_requirements_reported_together(self):
        self.client.force_authenticate(user=self.superadmin)
        payload = {
            "username": "testuser5",
            "email": "test5@csitabmc.org",
            "password": "short",  # short, no uppercase, no number, no special char
            "role": "admin",
        }
        res = self.client.post("/api/v1/users/accounts/", payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = res.data["password"]
        self.assertTrue(any("8 characters" in str(msg) for msg in errors))
        self.assertTrue(any("uppercase" in str(msg).lower() for msg in errors))
        self.assertTrue(any("number" in str(msg).lower() for msg in errors))
        self.assertTrue(any("special character" in str(msg).lower() for msg in errors))

    def test_valid_password_succeeds(self):
        self.client.force_authenticate(user=self.superadmin)
        payload = {
            "username": "testuser6",
            "email": "test6@csitabmc.org",
            "password": "ValidPassword123!",
            "role": "admin",
        }
        res = self.client.post("/api/v1/users/accounts/", payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_superadmin_changing_admin_password_enforces_policy(self):
        self.client.force_authenticate(user=self.superadmin)
        # Invalid: missing number
        res_bad = self.client.patch(f"/api/v1/users/accounts/{self.admin.id}/", {"password": "InvalidPassword!"})
        self.assertEqual(res_bad.status_code, status.HTTP_400_BAD_REQUEST)

        # Valid
        res_good = self.client.patch(f"/api/v1/users/accounts/{self.admin.id}/", {"password": "NewValidPassword123!"})
        self.assertEqual(res_good.status_code, status.HTTP_200_OK)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("NewValidPassword123!"))

    def test_self_service_password_change_enforces_policy(self):
        self.client.force_authenticate(user=self.admin)
        # Invalid new password
        payload_bad = {
            "old_password": "Password123!",
            "new_password": "short",
        }
        res_bad = self.client.post("/api/v1/users/change-password/", payload_bad)
        self.assertEqual(res_bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", res_bad.data)

        # Valid new password
        payload_good = {
            "old_password": "Password123!",
            "new_password": "BrandNewPassword123!",
        }
        res_good = self.client.post("/api/v1/users/change-password/", payload_good)
        self.assertEqual(res_good.status_code, status.HTTP_200_OK)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("BrandNewPassword123!"))


class ForgotPasswordRemovalTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_forgot_password_endpoints_return_404(self):
        # Request reset endpoint removed
        res1 = self.client.post("/api/v1/users/password-reset/", {"email": "user@csitabmc.org"})
        self.assertEqual(res1.status_code, status.HTTP_404_NOT_FOUND)

        # Reset confirm endpoint removed
        res2 = self.client.post("/api/v1/users/password-reset-confirm/", {"uid": "xxx", "token": "yyy", "new_password": "P1!"})
        self.assertEqual(res2.status_code, status.HTTP_404_NOT_FOUND)

        # Legacy reset-password endpoint removed
        res3 = self.client.post("/api/v1/users/reset-password/", {})
        self.assertEqual(res3.status_code, status.HTTP_404_NOT_FOUND)
