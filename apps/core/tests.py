from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from apps.notices.models import Notice
from apps.events.models import Event, Mentor
from apps.certificates.models import Certificate

User = get_user_model()


OVERVIEW_URL = "/api/v1/dashboard/overview/"

ALL_MODULES = {
    "tenures", "members", "alumni", "events", "mentors",
    "certificates", "papers", "blogs", "notices", "activity_logs",
}
EXPECTED_MODULES = {
    "superadmin": ALL_MODULES,
    "admin": ALL_MODULES,
    "cms_user": ALL_MODULES - {"activity_logs"},
    "operations": {"events", "mentors", "certificates", "papers", "notices"},
    "papers": {"papers"},
    "notice": {"notices"},
    "blog": {"blogs"},
}


class DashboardOverviewTests(APITestCase):
    def _user(self, role):
        return User.objects.create_user(
            username=f"u_{role}", email=f"{role}@example.com", password="pass12345", role=role
        )

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(OVERVIEW_URL).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.get("/api/v1/dashboard/stats/").status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_each_role_receives_only_permitted_modules(self):
        for role, expected in EXPECTED_MODULES.items():
            with self.subTest(role=role):
                self.client.force_authenticate(user=self._user(role))
                res = self.client.get(OVERVIEW_URL)
                self.assertEqual(res.status_code, status.HTTP_200_OK)
                self.assertEqual(set(res.data["modules"].keys()), expected)
                for key, payload in res.data["modules"].items():
                    self.assertNotIn("error", payload, key)

    def test_counts_match_database(self):
        Notice.objects.create(title="Notice 1", status="published")
        Notice.objects.create(title="Draft Notice", status="draft")
        published_event = Event.objects.create(title="Event 1", status="published", date=timezone.now())
        Event.objects.create(title="Event 2", status="draft", date=timezone.now())
        Event.objects.create(title="Event 3", status="completed", date=timezone.now())
        Mentor.objects.create(name="Mentor 1", expertise="x")
        Certificate.objects.create(full_name="Alice", event=published_event, is_project_completed=True)
        Certificate.objects.create(full_name="Bob", event=published_event, is_project_completed=False)

        self.client.force_authenticate(user=self._user("superadmin"))
        modules = self.client.get(OVERVIEW_URL).data["modules"]

        self.assertEqual(modules["notices"]["stats"], {"total": 2, "published": 1, "drafts": 1})
        self.assertEqual(modules["events"]["stats"]["total"], 3)
        self.assertEqual(modules["events"]["stats"]["published"], 1)
        self.assertEqual(modules["events"]["stats"]["drafts"], 1)
        self.assertEqual(modules["events"]["stats"]["completed"], 1)
        self.assertEqual(modules["mentors"]["stats"]["total"], 1)
        self.assertEqual(modules["certificates"]["stats"], {"total": 2, "completed": 1})
        self.assertEqual(modules["certificates"]["recent"][0]["event_title"], "Event 1")

    def test_recent_records_are_capped_and_newest_first(self):
        for i in range(8):
            Notice.objects.create(title=f"N{i}", status="published")
        self.client.force_authenticate(user=self._user("notice"))
        recent = self.client.get(OVERVIEW_URL).data["modules"]["notices"]["recent"]
        self.assertEqual(len(recent), 5)
        self.assertEqual(recent[0]["title"], "N7")
        self.assertEqual(self.client.get(OVERVIEW_URL).data["modules"]["notices"]["stats"]["total"], 8)


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
        overview = self.client.get(OVERVIEW_URL)
        self.assertEqual(overview.data["modules"]["notices"]["stats"]["published"], 45)
        self.assertEqual(overview.data["modules"]["notices"]["stats"]["total"], 46)
