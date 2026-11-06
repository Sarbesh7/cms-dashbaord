from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from .models import DeviceToken

User = get_user_model()


class DeviceTokenModelAndManagerTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username="user_a", password="password123", role="cms_user")
        self.user_b = User.objects.create_user(username="user_b", password="password123", role="cms_user")

    def test_create_device_token_defaults(self):
        token = DeviceToken.objects.create(
            token="test_fcm_token_12345",
            platform=DeviceToken.Platform.ANDROID,
            user=self.user_a,
        )
        self.assertTrue(token.enabled)
        self.assertEqual(token.platform, "android")
        self.assertEqual(token.user, self.user_a)
        self.assertIsNotNone(token.created_at)
        self.assertIsNotNone(token.updated_at)
        self.assertIn("android", str(token))

    def test_manager_queryset_filters(self):
        # User A: 1 active Android, 1 disabled iOS
        token_a1 = DeviceToken.objects.create(
            token="token_a1", platform="android", enabled=True, user=self.user_a
        )
        token_a2 = DeviceToken.objects.create(
            token="token_a2", platform="ios", enabled=False, user=self.user_a
        )
        # User B: 1 active iOS
        token_b1 = DeviceToken.objects.create(
            token="token_b1", platform="ios", enabled=True, user=self.user_b
        )
        # Guest: 1 active Android
        token_g1 = DeviceToken.objects.create(
            token="token_g1", platform="android", enabled=True, user=None
        )

        # active()
        active_tokens = DeviceToken.objects.active()
        self.assertEqual(set(active_tokens), {token_a1, token_b1, token_g1})
        self.assertNotIn(token_a2, active_tokens)

        # for_user()
        user_a_tokens = DeviceToken.objects.for_user(self.user_a)
        self.assertEqual(list(user_a_tokens), [token_a1])

        # for_platform()
        android_tokens = DeviceToken.objects.for_platform("android")
        self.assertEqual(set(android_tokens), {token_a1, token_g1})

        ios_tokens = DeviceToken.objects.for_platform("iOS")  # case-insensitive
        self.assertEqual(list(ios_tokens), [token_b1])


class DeviceTokenAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(username="user_a", password="password123", role="cms_user")
        self.user_b = User.objects.create_user(username="user_b", password="password123", role="cms_user")
        self.admin = User.objects.create_user(username="admin_user", password="password123", role="admin")

    def test_register_device_token_guest(self):
        response = self.client.post(
            "/api/v1/device-tokens/",
            {"token": "fcm_token_guest_1", "platform": "android"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertTrue(response.data["data"]["enabled"])
        self.assertEqual(response.data["data"]["platform"], "android")

        record = DeviceToken.objects.get(pk=response.data["data"]["id"])
        self.assertIsNone(record.user)
        self.assertEqual(record.token, "fcm_token_guest_1")

    def test_register_device_token_authenticated(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(
            "/api/v1/device-tokens/",
            {"token": "fcm_token_user_a", "platform": "ios"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["data"]["enabled"])
        self.assertEqual(response.data["data"]["platform"], "ios")

        record = DeviceToken.objects.get(pk=response.data["data"]["id"])
        self.assertEqual(record.user, self.user_a)

    def test_idempotent_registration_does_not_duplicate(self):
        # First registration
        r1 = self.client.post(
            "/api/v1/device-tokens/",
            {"token": "same_token_123", "platform": "android"},
            format="json",
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        token_id = r1.data["data"]["id"]

        # Second registration with same token
        r2 = self.client.post(
            "/api/v1/device-tokens/",
            {"token": "same_token_123", "platform": "android"},
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data["data"]["id"], token_id)
        self.assertEqual(DeviceToken.objects.filter(token="same_token_123").count(), 1)

    def test_token_reassignment_on_login(self):
        # Registered as guest initially
        r1 = self.client.post(
            "/api/v1/device-tokens/",
            {"token": "handoff_token", "platform": "android"},
            format="json",
        )
        token_id = r1.data["data"]["id"]
        record = DeviceToken.objects.get(pk=token_id)
        self.assertIsNone(record.user)

        # Later, user_b logs in and registers the same token
        self.client.force_authenticate(user=self.user_b)
        r2 = self.client.post(
            "/api/v1/device-tokens/",
            {"token": "handoff_token", "platform": "android"},
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        record.refresh_from_db()
        self.assertEqual(record.user, self.user_b)

    def test_validation_errors(self):
        # Missing token
        r1 = self.client.post("/api/v1/device-tokens/", {"platform": "android"}, format="json")
        self.assertEqual(r1.status_code, status.HTTP_400_BAD_REQUEST)

        # Invalid platform
        r2 = self.client.post(
            "/api/v1/device-tokens/",
            {"token": "sample_tok", "platform": "windows_phone"},
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("platform", r2.data["errors"])

    def test_status_toggle_endpoint(self):
        token = DeviceToken.objects.create(
            token="toggle_tok_1", platform="android", enabled=True, user=self.user_a
        )
        self.client.force_authenticate(user=self.user_a)

        # Disable
        res = self.client.patch(
            f"/api/v1/device-tokens/{token.id}/status/",
            {"enabled": False, "token": "malicious_attempt_to_change_token"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data["data"]["enabled"])

        token.refresh_from_db()
        self.assertFalse(token.enabled)
        # Token string remains completely unchanged
        self.assertEqual(token.token, "toggle_tok_1")

        # Enable
        res2 = self.client.patch(
            f"/api/v1/device-tokens/{token.id}/status/",
            {"enabled": True},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        token.refresh_from_db()
        self.assertTrue(token.enabled)

    def test_status_toggle_invalid_boolean(self):
        token = DeviceToken.objects.create(
            token="toggle_tok_2", platform="android", enabled=True, user=self.user_a
        )
        self.client.force_authenticate(user=self.user_a)

        res = self.client.patch(
            f"/api/v1/device-tokens/{token.id}/status/",
            {"enabled": "not_a_boolean"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_cannot_modify_another_users_token(self):
        token_b = DeviceToken.objects.create(
            token="token_b_private", platform="ios", enabled=True, user=self.user_b
        )
        # user_a attempts to access user_b's token
        self.client.force_authenticate(user=self.user_a)

        # Status toggle denied
        res = self.client.patch(
            f"/api/v1/device-tokens/{token_b.id}/status/",
            {"enabled": False},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Detail view denied
        res_get = self.client.get(f"/api/v1/device-tokens/{token_b.id}/")
        self.assertEqual(res_get.status_code, status.HTTP_403_FORBIDDEN)

        # Delete denied
        res_del = self.client.delete(f"/api/v1/device-tokens/{token_b.id}/")
        self.assertEqual(res_del.status_code, status.HTTP_403_FORBIDDEN)

    def test_listing_user_isolation(self):
        DeviceToken.objects.create(token="a1", platform="android", user=self.user_a)
        DeviceToken.objects.create(token="a2", platform="ios", user=self.user_a)
        DeviceToken.objects.create(token="b1", platform="android", user=self.user_b)

        # User A only sees their own 2 tokens
        self.client.force_authenticate(user=self.user_a)
        res = self.client.get("/api/v1/device-tokens/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 2)

    def test_admin_listing_and_filtering(self):
        DeviceToken.objects.create(token="t1", platform="android", enabled=True, user=self.user_a)
        DeviceToken.objects.create(token="t2", platform="ios", enabled=False, user=self.user_b)

        self.client.force_authenticate(user=self.admin)
        # Admin sees all tokens
        res = self.client.get("/api/v1/device-tokens/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 2)

        # Filter by platform
        res_plat = self.client.get("/api/v1/device-tokens/?platform=android")
        self.assertEqual(res_plat.data["count"], 1)

        # Filter by enabled
        res_en = self.client.get("/api/v1/device-tokens/?enabled=false")
        self.assertEqual(res_en.data["count"], 1)

    def test_update_token_string_and_unregister(self):
        token = DeviceToken.objects.create(
            token="initial_tok", platform="android", enabled=True, user=self.user_a
        )
        self.client.force_authenticate(user=self.user_a)

        # Update refreshed token string
        res = self.client.patch(
            f"/api/v1/device-tokens/{token.id}/",
            {"token": "refreshed_tok_99"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        token.refresh_from_db()
        self.assertEqual(token.token, "refreshed_tok_99")

        # Unregister / DELETE
        del_res = self.client.delete(f"/api/v1/device-tokens/{token.id}/")
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DeviceToken.objects.filter(pk=token.id).exists())
        # User account remains unharmed
        self.assertTrue(User.objects.filter(pk=self.user_a.pk).exists())


class PushDeviceMobileContractAPITests(TestCase):
    """
    Validates exact mobile contract compatibility for:
    - POST /api/push-devices/register
    - POST /api/push-devices/unregister
    as specified in custom-dashboard-migration.md.
    """

    def setUp(self):
        self.client = APIClient()

    def test_register_new_expo_token_success(self):
        payload = {
            "token": "ExponentPushToken[example-device-token-1]",
            "platform": "android",
        }
        res = self.client.post("/api/push-devices/register", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            res.data,
            {
                "success": True,
                "registered": True,
                "message": "Device registered successfully",
            },
        )

        device = DeviceToken.objects.get(token="ExponentPushToken[example-device-token-1]")
        self.assertTrue(device.enabled)
        self.assertEqual(device.platform, "android")
        self.assertIsNone(device.user)

    def test_register_expo_token_prefix_variant(self):
        payload = {
            "token": "ExpoPushToken[example-device-token-2]",
            "platform": "ios",
        }
        res = self.client.post("/api/push-devices/register", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["registered"])
        self.assertTrue(DeviceToken.objects.filter(token="ExpoPushToken[example-device-token-2]", platform="ios").exists())

    def test_register_existing_disabled_token_re_enables(self):
        token_str = "ExponentPushToken[existing-disabled-token]"
        DeviceToken.objects.create(token=token_str, platform="android", enabled=False)

        payload = {
            "token": token_str,
            "platform": "android",
        }
        res = self.client.post("/api/push-devices/register", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            res.data,
            {
                "success": True,
                "registered": False,
                "message": "Device already registered",
            },
        )

        device = DeviceToken.objects.get(token=token_str)
        self.assertTrue(device.enabled)

    def test_register_already_enabled_token_idempotent(self):
        payload = {
            "token": "ExponentPushToken[repeat-test-token]",
            "platform": "android",
        }
        r1 = self.client.post("/api/push-devices/register", payload, format="json")
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertTrue(r1.data["registered"])

        r2 = self.client.post("/api/push-devices/register", payload, format="json")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertFalse(r2.data["registered"])
        self.assertEqual(DeviceToken.objects.filter(token="ExponentPushToken[repeat-test-token]").count(), 1)

    def test_register_validation_missing_token(self):
        res = self.client.post("/api/push-devices/register", {"platform": "android"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", res.data)

    def test_register_validation_invalid_token_prefix(self):
        res = self.client.post(
            "/api/push-devices/register",
            {"token": "fcm_raw_token_without_expo_prefix", "platform": "android"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid Expo push token", str(res.data))

    def test_register_validation_invalid_platform(self):
        res = self.client.post(
            "/api/push-devices/register",
            {"token": "ExponentPushToken[valid-token-str]", "platform": "windows"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Platform must be android or ios", str(res.data))

    def test_unregister_active_device_disables_without_deleting(self):
        token_str = "ExponentPushToken[active-optout-token]"
        DeviceToken.objects.create(token=token_str, platform="android", enabled=True)

        res = self.client.post("/api/push-devices/unregister", {"token": token_str}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            res.data,
            {
                "success": True,
                "message": "Device unregistered",
            },
        )

        device = DeviceToken.objects.get(token=token_str)
        self.assertFalse(device.enabled)  # Record preserved, but disabled

    def test_unregister_idempotent_unknown_or_disabled(self):
        # Unknown token
        res_unknown = self.client.post(
            "/api/push-devices/unregister",
            {"token": "ExponentPushToken[unknown-never-registered]"},
            format="json",
        )
        self.assertEqual(res_unknown.status_code, status.HTTP_200_OK)
        self.assertEqual(res_unknown.data["success"], True)

        # Already disabled token
        token_str = "ExponentPushToken[already-disabled-token]"
        DeviceToken.objects.create(token=token_str, platform="ios", enabled=False)
        res_disabled = self.client.post(
            "/api/push-devices/unregister",
            {"token": token_str},
            format="json",
        )
        self.assertEqual(res_disabled.status_code, status.HTTP_200_OK)
        self.assertEqual(res_disabled.data["success"], True)

    def test_unregister_validation_missing_token(self):
        res = self.client.post("/api/push-devices/unregister", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Push token is required", str(res.data))

    def test_trailing_slash_route_tolerance(self):
        # Register with slash
        res_reg = self.client.post(
            "/api/push-devices/register/",
            {"token": "ExponentPushToken[slash-test-token]", "platform": "android"},
            format="json",
        )
        self.assertEqual(res_reg.status_code, status.HTTP_201_CREATED)

        # Unregister with slash
        res_unreg = self.client.post(
            "/api/push-devices/unregister/",
            {"token": "ExponentPushToken[slash-test-token]"},
            format="json",
        )
        self.assertEqual(res_unreg.status_code, status.HTTP_200_OK)
        self.assertFalse(DeviceToken.objects.get(token="ExponentPushToken[slash-test-token]").enabled)


class PushNotificationServiceAndHistoryTests(TestCase):
    def setUp(self):
        from unittest.mock import patch
        self.client = APIClient()
        self.superadmin = User.objects.create_user(
            username="superadmin_user", password="password123", role="superadmin"
        )
        self.admin = User.objects.create_user(
            username="admin_user2", password="password123", role="admin"
        )
        self.token1 = DeviceToken.objects.create(
            token="ExponentPushToken[device-success-1]",
            platform="android",
            enabled=True,
        )
        self.token2 = DeviceToken.objects.create(
            token="ExponentPushToken[device-fail-2]",
            platform="ios",
            enabled=True,
        )

    @patch("apps.notifications.services.push.PushNotificationService.post_to_expo")
    def test_dispatch_notification_success_and_system_actor_log(self, mock_send):
        from apps.notifications.services.push import PushNotificationService
        from apps.notifications.models import NotificationHistory, NotificationAttempt, NotificationRecipientResult, NotificationStatus
        from apps.core.models import ActivityLog

        mock_send.return_value = (
            [
                {"status": "ok", "id": "ticket-1"},
                {"status": "ok", "id": "ticket-2"},
            ],
            None,
        )

        history = PushNotificationService.dispatch_notification(
            title="Service Test Title",
            body="Service Test Body",
            source_module="announcement",
            source_id="101",
            source_title="Test Ann",
            data={"type": "announcement", "id": 101},
        )

        self.assertIsNotNone(history)
        self.assertEqual(history.status, NotificationStatus.SENT)
        self.assertEqual(history.total_devices, 2)
        self.assertEqual(history.accepted_count, 2)
        self.assertEqual(history.failed_count, 0)

        # Check attempt
        attempt = history.attempts.first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.status, NotificationStatus.SENT)

        # Check recipient results
        results = NotificationRecipientResult.objects.filter(notification=history)
        self.assertEqual(results.count(), 2)
        for r in results:
            self.assertEqual(r.status, "accepted")

        # Verify System actor in ActivityLog
        log = ActivityLog.objects.filter(module="notifications", action="dispatch").first()
        self.assertIsNotNone(log)
        self.assertIsNone(log.user)
        self.assertEqual(log.actor_name_snapshot, "System")
        self.assertEqual(log.user_role_snapshot, "system")

    @patch("apps.notifications.services.push.PushNotificationService.post_to_expo")
    def test_device_not_registered_auto_disables_token(self, mock_send):
        from apps.notifications.services.push import PushNotificationService
        from apps.notifications.models import NotificationStatus

        # Clean devices and create a dedicated token
        DeviceToken.objects.all().delete()
        bad_token = DeviceToken.objects.create(
            token="ExponentPushToken[unregistered-device]",
            platform="android",
            enabled=True,
        )

        mock_send.return_value = (
            [
                {
                    "status": "error",
                    "message": "The recipient device is not registered with Expo.",
                    "details": {"error": "DeviceNotRegistered"},
                },
            ],
            None,
        )

        history = PushNotificationService.dispatch_notification(
            title="Device Not Registered Test",
            body="Testing auto disable",
            source_module="notice",
            source_id="202",
            source_title="Test Notice",
        )

        self.assertEqual(history.status, NotificationStatus.FAILED)
        self.assertEqual(history.accepted_count, 0)
        self.assertEqual(history.failed_count, 1)

        # bad_token should now be disabled automatically
        bad_token.refresh_from_db()
        self.assertFalse(bad_token.enabled)

    @patch("apps.notifications.services.push.PushNotificationService.post_to_expo")
    def test_notification_retry_endpoint(self, mock_send):
        from apps.notifications.services.push import PushNotificationService
        from apps.notifications.models import NotificationHistory, NotificationStatus

        # First dispatch produces 1 failed recipient
        mock_send.return_value = (
            [
                {"status": "ok", "id": "ticket-1"},
                {
                    "status": "error",
                    "message": "Temporary network timeout",
                    "details": {"error": "MessageTooBig"},
                },
            ],
            None,
        )

        history = PushNotificationService.dispatch_notification(
            title="Retry Test Title",
            body="Retry Body",
            source_module="announcement",
            source_id="303",
            source_title="Retry Ann",
        )
        self.assertEqual(history.failed_count, 1)

        # Authenticate and call retry API
        self.client.force_authenticate(user=self.admin)
        mock_send.return_value = ([{"status": "ok", "id": "ticket-retry-2"}], None)

        res = self.client.post(f"/api/v1/notifications/{history.id}/retry/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        history.refresh_from_db()
        self.assertEqual(history.retry_count, 1)
        self.assertEqual(history.status, NotificationStatus.SENT)
        self.assertEqual(history.accepted_count, 2)
        self.assertEqual(history.failed_count, 0)
        self.assertEqual(history.attempts.count(), 2)

    def test_notification_history_list_and_detail_api(self):
        from apps.notifications.models import NotificationHistory

        history = NotificationHistory.objects.create(
            source_module="announcement",
            source_id="1",
            source_title="History Api Test",
            title="Api Notification",
            body="Api Notification Body",
            status="completed",
            total_devices=1,
            accepted_count=1,
            failed_count=0,
        )

        # Unauthenticated request fails
        res_unauth = self.client.get("/api/v1/notifications/")
        self.assertEqual(res_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        # Admin can view
        self.client.force_authenticate(user=self.admin)
        res_list = self.client.get("/api/v1/notifications/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(res_list.data["count"], 1)

        res_detail = self.client.get(f"/api/v1/notifications/{history.id}/")
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(res_detail.data["title"], "Api Notification")


