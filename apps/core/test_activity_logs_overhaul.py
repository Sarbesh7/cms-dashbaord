from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from apps.core.models import ActivityLog
from apps.core.activity_logging import log_activity, diff_snapshots
from apps.core.serializers import ActivityLogSerializer
from apps.core.user_agent import parse_user_agent

User = get_user_model()


class ActivityLogOverhaulTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_user_with_full_name_snapshot(self):
        user = User.objects.create_user(
            username="john_doe",
            email="john@example.com",
            password="Password123!",
            first_name="John",
            last_name="Doe",
            role="admin",
        )
        request = self.factory.get("/")
        request.user = user
        request.META["HTTP_USER_AGENT"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"

        log = log_activity(
            request,
            user=user,
            action="create",
            module="events",
            target_id="12",
            target_repr="Tech Meetup",
            description="Created new meetup",
        )

        self.assertIsNotNone(log)
        self.assertEqual(log.actor_id_snapshot, user.pk)
        self.assertEqual(log.actor_name_snapshot, "John Doe")
        self.assertEqual(log.actor_username_snapshot, "john_doe")
        self.assertEqual(log.user_email_snapshot, "john@example.com")
        self.assertEqual(log.user_role_snapshot, "admin")
        self.assertEqual(log.target_id, "12")
        self.assertEqual(log.target_repr, "Tech Meetup")

        # Serializer check
        serializer = ActivityLogSerializer(log)
        data = serializer.data
        self.assertEqual(data["actor_name"], "John Doe")
        self.assertEqual(data["actor_username"], "john_doe")
        self.assertEqual(data["actor_email"], "john@example.com")
        self.assertEqual(data["is_resource_applicable"], True)
        self.assertEqual(data["browser_name"], "Chrome")
        self.assertEqual(data["os_name"], "Windows")
        self.assertEqual(data["device_type"], "Desktop")

    def test_user_without_names_falls_back_to_name_unavailable(self):
        user = User.objects.create_user(
            username="nameless_user",
            email="nameless@example.com",
            password="Password123!",
            role="cms_user",
        )
        request = self.factory.get("/")
        request.user = user

        log = log_activity(
            request,
            user=user,
            action="update",
            module="notices",
            target_id="5",
            target_repr="Notice Title",
        )

        self.assertEqual(log.actor_name_snapshot, "Name unavailable")
        self.assertEqual(log.actor_username_snapshot, "nameless_user")
        # Ensure email or username is NOT substituted for name
        self.assertNotEqual(log.actor_name_snapshot, user.username)
        self.assertNotEqual(log.actor_name_snapshot, user.email)

        serializer = ActivityLogSerializer(log)
        self.assertEqual(serializer.data["actor_name"], "Name unavailable")
        self.assertEqual(serializer.data["actor_username"], "nameless_user")

    def test_auth_actions_decouple_resource_and_mark_not_applicable(self):
        user = User.objects.create_user(
            username="auth_tester",
            email="auth@example.com",
            password="Password123!",
            first_name="Auth",
            last_name="Tester",
            role="superadmin",
        )
        request = self.factory.post("/api/v1/login/")
        request.user = user

        # Login activity
        log = log_activity(
            request,
            user=user,
            action="login",
            module="auth",
            target_id="",
            target_repr="",
            description="User logged in successfully",
        )

        self.assertEqual(log.target_id, "")
        self.assertEqual(log.target_repr, "")
        self.assertNotEqual(log.target_repr, user.email)

        serializer = ActivityLogSerializer(log)
        self.assertEqual(serializer.data["is_resource_applicable"], False)

    def test_failed_login_logging(self):
        request = self.factory.post("/api/v1/login/")
        log = log_activity(
            request,
            user=None,
            action="failed_login",
            module="auth",
            target_id="",
            target_repr="",
            description="Failed login attempt for unknown@example.com",
            details={"attempted_email": "unknown@example.com"},
        )

        self.assertEqual(log.actor_name_snapshot, "Anonymous")
        self.assertEqual(log.actor_username_snapshot, "anonymous")
        self.assertEqual(log.details.get("attempted_email"), "unknown@example.com")
        self.assertEqual(ActivityLogSerializer(log).data["is_resource_applicable"], False)

    def test_system_background_activity(self):
        log = log_activity(
            request=None,
            user=None,
            action="publish",
            module="notices",
            target_id="101",
            target_repr="Scheduled Notice",
            description="System auto-published scheduled notice",
        )

        self.assertEqual(log.actor_name_snapshot, "System")
        self.assertEqual(log.actor_username_snapshot, "system")
        self.assertEqual(log.user_role_snapshot, "system")
        self.assertEqual(ActivityLogSerializer(log).data["actor_name"], "System")

    def test_zero_dependency_ua_parser(self):
        mobile_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
        res = parse_user_agent(mobile_ua)
        self.assertEqual(res["browser_name"], "Safari")
        self.assertEqual(res["os_name"], "iOS 17.1")
        self.assertEqual(res["device_type"], "Mobile")

        desktop_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        res2 = parse_user_agent(desktop_ua)
        self.assertEqual(res2["browser_name"], "Edge")
        self.assertEqual(res2["os_name"], "Windows")
        self.assertEqual(res2["device_type"], "Desktop")

    def test_changes_diff_snapshots(self):
        before = {"title": "Old Title", "is_published": False, "secret_token": "hidden"}
        after = {"title": "New Title", "is_published": True, "secret_token": "changed"}
        diff = diff_snapshots(before, after)
        self.assertIn("title", diff)
        self.assertEqual(diff["title"], {"before": "Old Title", "after": "New Title"})
        self.assertEqual(diff["is_published"], {"before": False, "after": True})

