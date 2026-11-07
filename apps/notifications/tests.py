from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from apps.notifications.models import Notification, NotificationRecipient, NotificationSource
from apps.notifications.services.in_app import InAppNotificationService

User = get_user_model()


class InAppNotificationModelAndServiceTests(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            username="superadmin", email="superadmin@test.com", password="password123", role="superadmin"
        )
        self.admin = User.objects.create_user(
            username="admin", email="admin@test.com", password="password123", role="admin"
        )
        self.cms_user = User.objects.create_user(
            username="cmsuser", email="cms@test.com", password="password123", role="cms_user"
        )
        self.operations = User.objects.create_user(
            username="operations", email="ops@test.com", password="password123", role="operations"
        )

    def test_send_notification_creates_records_and_excludes_sender(self):
        recipients = [self.superadmin, self.admin, self.cms_user]
        notif = InAppNotificationService.send_notification(
            title="Meeting Scheduled",
            message="Meeting will be held tomorrow at 3 PM.",
            recipients=recipients,
            sender=self.admin,
            source_module=NotificationSource.DIRECT,
            exclude_sender=True,
        )

        self.assertIsNotNone(notif)
        self.assertEqual(notif.sender, self.admin)
        self.assertEqual(notif.title, "Meeting Scheduled")

        # Sender should be excluded from receiving their own notification
        recipient_users = list(NotificationRecipient.objects.filter(notification=notif).values_list('recipient_id', flat=True))
        self.assertIn(self.superadmin.id, recipient_users)
        self.assertIn(self.cms_user.id, recipient_users)
        self.assertNotIn(self.admin.id, recipient_users)

    def test_ineligible_roles_filtered_out_by_service(self):
        recipients = [self.cms_user, self.operations]
        notif = InAppNotificationService.send_notification(
            title="Notice",
            message="Testing filtering of ineligible roles.",
            recipients=recipients,
            sender=self.admin,
        )

        self.assertIsNotNone(notif)
        recipient_users = list(NotificationRecipient.objects.filter(notification=notif).values_list('recipient_id', flat=True))
        self.assertIn(self.cms_user.id, recipient_users)
        self.assertNotIn(self.operations.id, recipient_users)

    def test_system_notification_duplicate_prevention(self):
        notif1 = InAppNotificationService.send_system_notification(
            title="Notice Published",
            message="A new notice has been published.",
            source_module="notice",
            source_id="notice-123",
            exclude_user=self.admin,
        )
        self.assertIsNotNone(notif1)

        # Sending again with the exact same source_module, source_id, and title should be a no-op duplicate
        notif2 = InAppNotificationService.send_system_notification(
            title="Notice Published",
            message="A new notice has been published.",
            source_module="notice",
            source_id="notice-123",
            exclude_user=self.admin,
        )
        self.assertEqual(notif1.id, notif2.id)
        self.assertEqual(Notification.objects.filter(source_id="notice-123").count(), 1)


class InAppNotificationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.superadmin = User.objects.create_user(
            username="superadmin", email="superadmin@test.com", password="password123", role="superadmin"
        )
        self.admin = User.objects.create_user(
            username="admin", email="admin@test.com", password="password123", role="admin"
        )
        self.cms_user = User.objects.create_user(
            username="cmsuser", email="cms@test.com", password="password123", role="cms_user"
        )
        self.restricted_user = User.objects.create_user(
            username="restricted", email="restricted@test.com", password="password123", role="operations"
        )

    def test_unauthenticated_request_rejected(self):
        res = self.client.get("/api/v1/notifications/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_restricted_role_rejected_403(self):
        self.client.force_authenticate(user=self.restricted_user)
        res = self.client.get("/api/v1/notifications/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.client.get("/api/v1/notifications/unread-count/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.client.post("/api/v1/notifications/compose/", {"title": "X", "message": "Y"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_eligible_roles_can_access_inbox(self):
        for user in (self.superadmin, self.admin, self.cms_user):
            self.client.force_authenticate(user=user)
            res = self.client.get("/api/v1/notifications/")
            self.assertEqual(res.status_code, status.HTTP_200_OK, f"{user.role} failed to access inbox")

    def test_inbox_pagination_and_filtering(self):
        # Create 3 notifications for cms_user (2 unread, 1 read)
        notif1 = InAppNotificationService.send_notification(
            title="First Announcement",
            message="Alpha announcement",
            recipients=[self.cms_user],
            sender=self.admin,
            source_module=NotificationSource.ANNOUNCEMENT
        )
        notif2 = InAppNotificationService.send_notification(
            title="Second Notice",
            message="Beta notice",
            recipients=[self.cms_user],
            sender=self.admin,
            source_module=NotificationSource.NOTICE
        )
        notif3 = InAppNotificationService.send_notification(
            title="Third Direct",
            message="Gamma direct message",
            recipients=[self.cms_user],
            sender=self.superadmin,
            source_module=NotificationSource.DIRECT
        )

        recip1 = NotificationRecipient.objects.get(notification=notif1, recipient=self.cms_user)
        recip1.is_read = True
        recip1.read_at = timezone.now()
        recip1.save()

        self.client.force_authenticate(user=self.cms_user)

        # Unread count
        count_res = self.client.get("/api/v1/notifications/unread-count/")
        self.assertEqual(count_res.status_code, status.HTTP_200_OK)
        self.assertEqual(count_res.data["unread_count"], 2)

        # All received
        res = self.client.get("/api/v1/notifications/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 3)

        # Filter is_read=false
        res = self.client.get("/api/v1/notifications/?is_read=false")
        self.assertEqual(res.data["count"], 2)

        # Filter source_module=notice
        res = self.client.get("/api/v1/notifications/?source_module=notice")
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["title"], "Second Notice")

        # Search
        res = self.client.get("/api/v1/notifications/?search=Alpha")
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["title"], "First Announcement")

    def test_mark_individual_notification_read_and_unread(self):
        notif = InAppNotificationService.send_notification(
            title="Test",
            message="Testing read toggle",
            recipients=[self.cms_user],
            sender=self.admin
        )
        recip = NotificationRecipient.objects.get(notification=notif, recipient=self.cms_user)
        self.assertFalse(recip.is_read)

        self.client.force_authenticate(user=self.cms_user)

        # Mark read
        res = self.client.post(f"/api/v1/notifications/{recip.id}/read/", {"is_read": True})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["is_read"])
        recip.refresh_from_db()
        self.assertTrue(recip.is_read)
        self.assertIsNotNone(recip.read_at)

        # Toggle unread
        res = self.client.post(f"/api/v1/notifications/{recip.id}/read/", {"is_read": False})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data["is_read"])
        recip.refresh_from_db()
        self.assertFalse(recip.is_read)
        self.assertIsNone(recip.read_at)

    def test_mark_all_read(self):
        InAppNotificationService.send_notification(
            title="N1", message="M1", recipients=[self.cms_user], sender=self.admin
        )
        InAppNotificationService.send_notification(
            title="N2", message="M2", recipients=[self.cms_user], sender=self.superadmin
        )

        self.assertEqual(NotificationRecipient.objects.filter(recipient=self.cms_user, is_read=False).count(), 2)

        self.client.force_authenticate(user=self.cms_user)
        res = self.client.post("/api/v1/notifications/mark-all-read/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["marked_count"], 2)

        self.assertEqual(NotificationRecipient.objects.filter(recipient=self.cms_user, is_read=False).count(), 0)

    def test_compose_notification_with_specific_recipients(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            "/api/v1/notifications/compose/",
            {
                "title": "Staff Meeting",
                "message": "Please review the agenda.",
                "recipient_ids": [self.superadmin.id, self.cms_user.id],
            },
            format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        notif = Notification.objects.get(id=res.data["id"])
        self.assertEqual(notif.title, "Staff Meeting")
        self.assertEqual(notif.recipients.count(), 2)

    def test_compose_notification_to_all_eligible(self):
        self.client.force_authenticate(user=self.superadmin)
        res = self.client.post(
            "/api/v1/notifications/compose/",
            {
                "title": "System Maintenance",
                "message": "Scheduled for tonight.",
                "all_eligible": True,
            },
            format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        notif = Notification.objects.get(id=res.data["id"])

        # Should target admin and cms_user, but exclude superadmin (sender) and restricted operations
        recipient_user_ids = list(notif.recipients.values_list('recipient_id', flat=True))
        self.assertIn(self.admin.id, recipient_user_ids)
        self.assertIn(self.cms_user.id, recipient_user_ids)
        self.assertNotIn(self.superadmin.id, recipient_user_ids)
        self.assertNotIn(self.restricted_user.id, recipient_user_ids)

    def test_compose_rejects_ineligible_recipient(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            "/api/v1/notifications/compose/",
            {
                "title": "Secret",
                "message": "Message",
                "recipient_ids": [self.restricted_user.id],
            },
            format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("recipient_ids", res.data)

    def test_compose_rejects_empty_fields(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            "/api/v1/notifications/compose/",
            {
                "title": "   ",
                "message": "",
                "recipient_ids": [],
            },
            format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", res.data)
        self.assertIn("message", res.data)

        # Valid text but missing recipients
        res2 = self.client.post(
            "/api/v1/notifications/compose/",
            {
                "title": "Valid Title",
                "message": "Valid Message",
                "recipient_ids": [],
            },
            format="json"
        )
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("recipient_ids", res2.data)

    def test_sent_notifications_list(self):
        InAppNotificationService.send_notification(
            title="Sent by Admin",
            message="Content",
            recipients=[self.cms_user],
            sender=self.admin
        )
        InAppNotificationService.send_notification(
            title="Sent by Superadmin",
            message="Content",
            recipients=[self.cms_user],
            sender=self.superadmin
        )

        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/v1/notifications/sent/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["title"], "Sent by Admin")

    def test_eligible_recipients_endpoint(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/v1/notifications/recipients/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        returned_ids = [u["id"] for u in res.data]
        # Includes superadmin and cms_user
        self.assertIn(self.superadmin.id, returned_ids)
        self.assertIn(self.cms_user.id, returned_ids)
        # Excludes requesting user (admin) and restricted_user (operations)
        self.assertNotIn(self.admin.id, returned_ids)
        self.assertNotIn(self.restricted_user.id, returned_ids)
