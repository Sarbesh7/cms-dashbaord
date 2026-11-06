from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.core.models import ActivityLog
from apps.core.activity_logging import log_activity


class ActivityLogTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.superadmin = User.objects.create_user(
            username="superadmin", email="super@example.com", password="password123", role="superadmin", is_superuser=True
        )
        self.admin = User.objects.create_user(
            username="adminuser", email="admin@example.com", password="password123", role="admin"
        )
        self.cms_user = User.objects.create_user(
            username="cmsuser", email="cms@example.com", password="password123", role="cms_user"
        )
        self.blog_user = User.objects.create_user(
            username="bloguser", email="blog@example.com", password="password123", role="blog"
        )

    def test_log_activity_creates_record_and_snapshots_user(self):
        log = log_activity(
            user=self.admin,
            action="create",
            module="events",
            target_id="101",
            target_repr="Tech Workshop 2026",
            details={"capacity": 50}
        )
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.user_email_snapshot, "admin@example.com")
        self.assertEqual(log.user_role_snapshot, "admin")
        self.assertEqual(log.action, "create")
        self.assertEqual(log.module, "events")
        self.assertEqual(log.target_id, "101")
        self.assertEqual(log.target_repr, "Tech Workshop 2026")
        self.assertEqual(log.details, {"capacity": 50})

    def test_user_deletion_preserves_log_with_set_null(self):
        temp_user = User.objects.create_user(
            username="temp", email="temp@example.com", password="password123", role="operations"
        )
        log = log_activity(
            user=temp_user,
            action="publish",
            module="events",
            target_id="1",
            target_repr="Sample Event"
        )
        temp_user.delete()
        log.refresh_from_db()
        self.assertIsNone(log.user)
        self.assertEqual(log.user_email_snapshot, "temp@example.com")
        self.assertEqual(log.user_role_snapshot, "operations")

    def test_superadmin_and_admin_can_view_activity_logs(self):
        log_activity(user=self.admin, action="login", module="auth", target_repr="Logged in")

        # Superadmin allowed
        self.client.force_authenticate(user=self.superadmin)
        res = self.client.get('/api/v1/activity-logs/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('results', res.data)
        self.assertGreaterEqual(len(res.data['results']), 1)

        # Admin allowed
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/activity-logs/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_non_admin_roles_forbidden_from_activity_logs(self):
        # cms_user forbidden
        self.client.force_authenticate(user=self.cms_user)
        res = self.client.get('/api/v1/activity-logs/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # blog user forbidden
        self.client.force_authenticate(user=self.blog_user)
        res = self.client.get('/api/v1/activity-logs/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # unauthenticated forbidden
        self.client.logout()
        res = self.client.get('/api/v1/activity-logs/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_activity_logs_are_immutable(self):
        log = log_activity(user=self.admin, action="create", module="notices", target_repr="Annual General Meeting")
        self.client.force_authenticate(user=self.superadmin)

        # POST not allowed
        post_res = self.client.post('/api/v1/activity-logs/', {'action': 'hack'})
        self.assertEqual(post_res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # DELETE not allowed
        del_res = self.client.delete(f'/api/v1/activity-logs/{log.id}/')
        self.assertEqual(del_res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PUT not allowed
        put_res = self.client.put(f'/api/v1/activity-logs/{log.id}/', {'action': 'modified'})
        self.assertEqual(put_res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_activity_log_summary_view(self):
        log_activity(user=self.admin, action="login", module="auth", target_repr="Admin login")
        log_activity(user=self.admin, action="create", module="events", target_repr="Hackathon")
        log_activity(user=self.admin, action="update", module="events", target_repr="Hackathon v2")

        self.client.force_authenticate(user=self.superadmin)
        res = self.client.get('/api/v1/activity-logs/summary/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("total_activities", res.data)
        self.assertIn("logins_this_week", res.data)
        self.assertIn("mutations_today", res.data)
        self.assertIn("most_active_module", res.data)
        self.assertEqual(res.data["most_active_module"], "events")
