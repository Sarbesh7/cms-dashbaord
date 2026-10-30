from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient
from apps.notices.models import Notice
from apps.users.models import User


class NoticeSlugTests(TestCase):
    def test_unique_notice_slug_generation(self):
        notice = Notice.objects.create(
            title="Annual General Meeting",
            description="Discussion on yearly progress.",
            status="published"
        )
        self.assertEqual(notice.slug, "annual-general-meeting")

    def test_duplicate_title_slug_numeric_suffixes(self):
        notice1 = Notice.objects.create(
            title="Workshop Announcement",
            description="First workshop announcement."
        )
        notice2 = Notice.objects.create(
            title="Workshop Announcement",
            description="Second workshop announcement."
        )
        notice3 = Notice.objects.create(
            title="Workshop Announcement",
            description="Third workshop announcement."
        )

        self.assertEqual(notice1.slug, "workshop-announcement")
        self.assertEqual(notice2.slug, "workshop-announcement-2")
        self.assertEqual(notice3.slug, "workshop-announcement-3")

    def test_title_update_regenerates_slug(self):
        notice = Notice.objects.create(
            title="Old Notice Title",
            description="Content"
        )
        self.assertEqual(notice.slug, "old-notice-title")

        notice.title = "New Notice Title"
        notice.save()
        notice.refresh_from_db()
        self.assertEqual(notice.slug, "new-notice-title")

    def test_non_title_update_preserves_slug(self):
        notice = Notice.objects.create(
            title="Important Update",
            description="Original description"
        )
        original_slug = notice.slug

        notice.description = "Updated description only"
        notice.status = "published"
        notice.save()
        notice.refresh_from_db()

        self.assertEqual(notice.slug, original_slug)

    def test_update_self_exclusion(self):
        notice1 = Notice.objects.create(title="Seminar Notice", description="First")
        notice2 = Notice.objects.create(title="Seminar Notice", description="Second")
        self.assertEqual(notice2.slug, "seminar-notice-2")

        # Saving notice2 without title change or with same title should not bump suffix
        notice2.description = "Updated second description"
        notice2.save()
        notice2.refresh_from_db()
        self.assertEqual(notice2.slug, "seminar-notice-2")

    def test_title_update_with_collision_resolves_correctly(self):
        notice1 = Notice.objects.create(title="Hackathon 2026", description="First")
        notice2 = Notice.objects.create(title="Other Event", description="Second")
        self.assertEqual(notice1.slug, "hackathon-2026")
        self.assertEqual(notice2.slug, "other-event")

        # Now update notice2 to have title "Hackathon 2026"
        notice2.title = "Hackathon 2026"
        notice2.save()
        notice2.refresh_from_db()
        self.assertEqual(notice2.slug, "hackathon-2026-2")

    def test_long_title_slug_fits_column(self):
        title = "Workshop " * 28 + "end"  # well over 255 characters before truncation
        title = title[:255]
        first = Notice.objects.create(title=title, description="d")
        second = Notice.objects.create(title=title, description="d")
        self.assertLessEqual(len(first.slug), 255)
        self.assertLessEqual(len(second.slug), 255)
        self.assertTrue(second.slug.endswith("-2"))
        self.assertNotEqual(first.slug, second.slug)

    def test_punctuation_only_differences_collide(self):
        a = Notice.objects.create(title="Spring Boot: Workshop!", description="d")
        b = Notice.objects.create(title="Spring Boot Workshop", description="d")
        self.assertEqual((a.slug, b.slug), ("spring-boot-workshop", "spring-boot-workshop-2"))

    def test_non_latin_title_falls_back_to_notice(self):
        a = Notice.objects.create(title="कार्यशाला सूचना", description="d")
        b = Notice.objects.create(title="परीक्षा तालिका", description="d")
        self.assertEqual((a.slug, b.slug), ("notice", "notice-2"))

    def test_concurrent_creation_race_retries_with_next_suffix(self):
        """Simulate another request inserting the same slug between the check and the insert."""
        Notice.objects.create(title="Race Notice", description="first")
        real_unique_slug = Notice._unique_slug
        calls = []

        def stale_first_check(instance, base_slug, start=1):
            calls.append(start)
            if len(calls) == 1:
                return base_slug, 1  # stale read: the other request's row was not visible yet
            return real_unique_slug(instance, base_slug, start)

        with mock.patch.object(Notice, "_unique_slug", stale_first_check):
            second = Notice.objects.create(title="Race Notice", description="second")
        self.assertEqual(second.slug, "race-notice-2")
        self.assertEqual(len(calls), 2)
        self.assertEqual(Notice.objects.filter(slug__startswith="race-notice").count(), 2)


class NoticeApiSlugTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="editor", email="editor@example.com", password="pass12345", role="admin"
        )
        self.client.force_authenticate(self.user)

    def test_client_supplied_slug_ignored_on_create_and_update(self):
        res = self.client.post(
            "/api/v1/notices/", {"title": "Spring Boot Workshop", "description": "d", "slug": "custom-value"},
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["slug"], "spring-boot-workshop")

        res = self.client.put(
            "/api/v1/notices/spring-boot-workshop/",
            {"title": "Spring Boot Workshop", "description": "changed", "slug": "hijack"},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["slug"], "spring-boot-workshop")

    def test_title_change_moves_slug_and_old_slug_404s(self):
        self.client.post("/api/v1/notices/", {"title": "Spring Boot Workshop", "description": "d"}, format="json")
        res = self.client.put(
            "/api/v1/notices/spring-boot-workshop/",
            {"title": "Advanced Spring Boot Workshop", "description": "d"},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["slug"], "advanced-spring-boot-workshop")
        self.assertEqual(self.client.get("/api/v1/notices/spring-boot-workshop/").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/notices/advanced-spring-boot-workshop/").status_code, 200)

    def test_notice_list_is_server_paginated(self):
        for i in range(3):
            Notice.objects.create(title=f"Paged {i}", description="d")
        res = self.client.get("/api/v1/notices/", {"page": 2, "page_size": 2})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 3)
        self.assertEqual(len(res.data["results"]), 1)
