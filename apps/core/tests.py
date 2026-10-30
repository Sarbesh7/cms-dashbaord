from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from apps.notices.models import Notice
from apps.events.models import Event, Mentor
from apps.certificates.models import Certificate

User = get_user_model()


class DashboardStatsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpassword123",
            role="admin",
        )
        self.client.force_authenticate(user=self.user)

    def test_dashboard_stats_endpoint(self):
        # Create published notice
        Notice.objects.create(title="Notice 1", status="published")
        Notice.objects.create(title="Draft Notice", status="draft")

        # Create open event
        open_event = Event.objects.create(title="Event 1", status="published", date=timezone.now())
        Event.objects.create(title="Event 2", status="draft", date=timezone.now())

        # Create mentor
        Mentor.objects.create(name="Mentor 1")

        # Create certificates
        Certificate.objects.create(
            full_name="Alice",
            event=open_event,
            is_project_completed=True,
        )
        Certificate.objects.create(
            full_name="Bob",
            event=open_event,
            is_project_completed=False,
        )

        response = self.client.get("/api/v1/dashboard/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check response keys and values
        self.assertEqual(response.data["published_notices"], 1)
        self.assertEqual(response.data["open_events"], 1)
        self.assertEqual(response.data["total_mentors"], 1)
        self.assertEqual(response.data["completed_certificates"], 1)

        # Check camelCase aliases for frontend compatibility
        self.assertEqual(response.data["publishedNoticesCount"], 1)
        self.assertEqual(response.data["openEventsCount"], 1)
        self.assertEqual(response.data["totalMentorsCount"], 1)
        self.assertEqual(response.data["certificatesIssuedCount"], 1)


class ContentConsistencyTests(APITestCase):
    """Cached GET responses must not survive writes; totals must not depend on page size."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(
            username="editor", email="editor@example.com", password="pass12345", role="admin"
        )
        self.client.force_authenticate(user=self.user)

    def test_notice_list_reflects_writes_immediately(self):
        Notice.objects.create(title="First", description="d", status="published")
        first = self.client.get("/api/v1/notices/")
        self.assertEqual(first.data["count"], 1)

        res = self.client.post("/api/v1/notices/", {"title": "Second", "description": "d"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(self.client.get("/api/v1/notices/").data["count"], 2)

        self.client.delete(f"/api/v1/notices/{res.data['slug']}/")
        self.assertEqual(self.client.get("/api/v1/notices/").data["count"], 1)

    def test_event_and_mentor_reads_reflect_writes_immediately(self):
        mentor = Mentor.objects.create(name="Cached Mentor", expertise="x")
        event = Event.objects.create(title="Cached Event", description="d", date=timezone.now())
        self.assertEqual(self.client.get(f"/api/v1/events/{event.slug}/").data["mentor_assignments"], [])
        self.assertEqual(self.client.get(f"/api/v1/mentors/{mentor.id}/").data["event_assignments"], [])

        res = self.client.patch(
            f"/api/v1/events/{event.slug}/",
            {"assignments": [{"mentor_id": mentor.id, "role": "judge"}]},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        detail = self.client.get(f"/api/v1/events/{event.slug}/").data
        self.assertEqual(detail["mentor_assignments"][0]["role_label"], "Judge")
        self.assertEqual(
            self.client.get(f"/api/v1/mentors/{mentor.id}/").data["event_assignments"][0]["role"], "judge"
        )

        self.client.patch(f"/api/v1/mentors/{mentor.id}/", {"name": "Renamed Mentor"}, format="json")
        detail = self.client.get(f"/api/v1/events/{event.slug}/").data
        self.assertEqual(detail["mentor_assignments"][0]["mentor_name"], "Renamed Mentor")

    def test_alumni_full_list_mode_and_default_envelope(self):
        from apps.tenure.models import Alumni, Member
        for i in range(3):
            member = Member.objects.create(name=f"Alum {i}", email=f"alum{i}@example.com")
            Alumni.objects.create(member=member, graduation_year=2020 + i)

        full = self.client.get("/api/v1/alumni/", {"all": "true"})
        self.assertEqual(full.status_code, 200)
        self.assertIsInstance(full.data, list)
        self.assertEqual(len(full.data), 3)

        paged = self.client.get("/api/v1/alumni/", {"page": 1, "page_size": 2})
        self.assertEqual(paged.data["count"], 3)
        self.assertEqual(len(paged.data["results"]), 2)

        member = Member.objects.create(name="Alum new", email="alumnew@example.com")
        self.client.post("/api/v1/alumni/", {"member_id": member.id, "graduation_year": 2025}, format="json")
        self.assertEqual(len(self.client.get("/api/v1/alumni/", {"all": "true"}).data), 4)

    def test_dashboard_totals_independent_of_page_size(self):
        Notice.objects.bulk_create([
            Notice(title=f"Published {i}", slug=f"published-{i}", description="d", status="published")
            for i in range(45)
        ])
        Notice.objects.create(title="Draft", description="d", status="draft")
        page = self.client.get("/api/v1/notices/", {"page_size": 10})
        self.assertEqual(len(page.data["results"]), 10)
        stats = self.client.get("/api/v1/dashboard/stats/")
        self.assertEqual(stats.data["published_notices"], 45)
