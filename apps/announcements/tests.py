from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from apps.announcements.models import Announcement
from apps.core.models import ActivityLog
from apps.notifications.models import Notification

User = get_user_model()


class AnnouncementApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username="admin_user",
            password="password123",
            role="admin",
        )
        self.cms_user = User.objects.create_user(
            username="cms_user",
            password="password123",
            role="cms_user",
        )

    def test_anonymous_can_list_announcements(self):
        Announcement.objects.create(title="Test Ann 1", description="Description 1")
        Announcement.objects.create(title="Test Ann 2", description="Description 2")

        res = self.client.get("/announcements/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 2)

    def test_anonymous_cannot_create_announcement(self):
        res = self.client.post(
            "/announcements/",
            {"title": "Unauthorized", "description": "Should fail"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_announcement_triggers_notification_and_activity_log(self):
        # Create an eligible recipient user so in-app notification finds a target
        User.objects.create_user(
            username="cms_recipient",
            email="recipient@test.com",
            password="password123",
            role="cms_user"
        )

        self.client.force_authenticate(user=self.admin_user)
        res = self.client.post(
            "/announcements/",
            {
                "title": "Welcome to CSITABMC",
                "description": "Welcome to our association platform!",
                "link": "https://csitabmc.com",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Announcement.objects.count(), 1)
        announcement = Announcement.objects.first()
        self.assertEqual(announcement.title, "Welcome to CSITABMC")

        # Verify activity log
        log = ActivityLog.objects.filter(module="announcements", action="create").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.target_id, str(announcement.id))

        # Check In-App Notification dispatch
        notif = Notification.objects.filter(source_module="announcement").first()
        self.assertIsNotNone(notif)
        self.assertIn(announcement.title, notif.title)

    def test_update_announcement(self):
        ann = Announcement.objects.create(title="Original Title", description="Original Desc")
        self.client.force_authenticate(user=self.admin_user)

        res = self.client.patch(
            f"/announcements/{ann.id}/",
            {"title": "Updated Title"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ann.refresh_from_db()
        self.assertEqual(ann.title, "Updated Title")

        # Verify update activity log
        log = ActivityLog.objects.filter(module="announcements", action="update").first()
        self.assertIsNotNone(log)
        self.assertIn("Updated Title", log.description)

    def test_delete_announcement(self):
        ann = Announcement.objects.create(title="To Delete", description="To Delete Desc")
        self.client.force_authenticate(user=self.admin_user)

        res = self.client.delete(f"/announcements/{ann.id}/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Announcement.objects.count(), 0)

        log = ActivityLog.objects.filter(module="announcements", action="delete").first()
        self.assertIsNotNone(log)
