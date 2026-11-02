import json
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from django.db import IntegrityError
from rest_framework.test import APIClient
from apps.events.models import Event, Mentor, EventMentorAssignment
from apps.events.serializers import EventSerializer
from apps.users.models import User

# Smallest valid GIF, used for multipart upload tests.
TINY_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04"
    b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


class MentorEventAssignmentTests(TestCase):
    def setUp(self):
        self.mentor_a = Mentor.objects.create(
            name="Mentor Alpha",
            expertise="Frontend Architecture",
            email="alpha@example.com"
        )
        self.mentor_b = Mentor.objects.create(
            name="Mentor Beta",
            expertise="Backend Systems",
            email="beta@example.com"
        )
        self.mentor_c = Mentor.objects.create(
            name="Mentor Gamma",
            expertise="DevOps & Cloud",
            email="gamma@example.com"
        )
        self.event_1 = Event.objects.create(
            title="Tech Summit 2026",
            description="Annual technical summit",
            date=timezone.now(),
            available_seats=100
        )
        self.event_2 = Event.objects.create(
            title="Hackathon 2026",
            description="48-hour hackathon",
            date=timezone.now(),
            available_seats=50
        )

    def test_create_mentor_independent_of_member(self):
        """Mentors exist in global catalog without requiring Member/Tenure links."""
        mentor = Mentor.objects.create(
            name="External Speaker",
            expertise="Cybersecurity",
            email="speaker@external.com"
        )
        self.assertIsNotNone(mentor.id)
        self.assertFalse(hasattr(mentor, 'member'))
        self.assertFalse(hasattr(mentor, 'slug'))
        self.assertEqual(str(mentor), "External Speaker")

    def test_assign_multiple_mentors_with_roles(self):
        """Events can have multiple mentors with specific roles and responsibilities."""
        a1 = EventMentorAssignment.objects.create(
            event=self.event_1,
            mentor=self.mentor_a,
            role=EventMentorAssignment.Role.MAIN_MENTOR,
            responsibility="Frontend Track Lead"
        )
        a2 = EventMentorAssignment.objects.create(
            event=self.event_1,
            mentor=self.mentor_b,
            role=EventMentorAssignment.Role.CO_MENTOR,
            responsibility="Backend Advisor"
        )

        self.assertEqual(self.event_1.mentors.count(), 2)
        self.assertEqual(self.event_1.mentor_assignments.count(), 2)
        self.assertEqual(a1.role, "main_mentor")
        self.assertEqual(a2.role, "co_mentor")

    def test_multiple_main_mentors_allowed_on_same_event(self):
        """Events intentionally allow multiple Main Mentors."""
        a1 = EventMentorAssignment.objects.create(
            event=self.event_1,
            mentor=self.mentor_a,
            role=EventMentorAssignment.Role.MAIN_MENTOR,
            responsibility="Web Track"
        )
        a2 = EventMentorAssignment.objects.create(
            event=self.event_1,
            mentor=self.mentor_b,
            role=EventMentorAssignment.Role.MAIN_MENTOR,
            responsibility="AI Track"
        )

        main_mentors = self.event_1.mentor_assignments.filter(role=EventMentorAssignment.Role.MAIN_MENTOR)
        self.assertEqual(main_mentors.count(), 2)

    def test_same_mentor_different_roles_across_events(self):
        """The same mentor can have different roles at different events."""
        EventMentorAssignment.objects.create(
            event=self.event_1,
            mentor=self.mentor_a,
            role=EventMentorAssignment.Role.MAIN_MENTOR
        )
        EventMentorAssignment.objects.create(
            event=self.event_2,
            mentor=self.mentor_a,
            role=EventMentorAssignment.Role.SPEAKER,
            responsibility="Keynote on Microfrontends"
        )

        self.assertEqual(self.mentor_a.event_assignments.count(), 2)
        r1 = self.mentor_a.event_assignments.get(event=self.event_1).role
        r2 = self.mentor_a.event_assignments.get(event=self.event_2).role
        self.assertEqual(r1, "main_mentor")
        self.assertEqual(r2, "speaker")

    def test_custom_role_assignment(self):
        """Custom roles are stored and formatted properly."""
        a = EventMentorAssignment.objects.create(
            event=self.event_1,
            mentor=self.mentor_c,
            role=EventMentorAssignment.Role.CUSTOM,
            custom_role="Lead Judge",
            responsibility="Final Round Evaluation"
        )
        self.assertEqual(a.role, "custom")
        self.assertEqual(a.custom_role, "Lead Judge")
        self.assertIn("Lead Judge", str(a))

    def test_duplicate_assignment_prevented(self):
        """Assigning the same mentor to the same event twice raises IntegrityError."""
        EventMentorAssignment.objects.create(
            event=self.event_1,
            mentor=self.mentor_a,
            role=EventMentorAssignment.Role.MAIN_MENTOR
        )
        with self.assertRaises(IntegrityError):
            EventMentorAssignment.objects.create(
                event=self.event_1,
                mentor=self.mentor_a,
                role=EventMentorAssignment.Role.CO_MENTOR
            )

    def test_removing_assignment_does_not_delete_mentor(self):
        """Deleting an assignment unlinks the mentor without deleting the mentor record."""
        assignment = EventMentorAssignment.objects.create(
            event=self.event_1,
            mentor=self.mentor_a,
            role=EventMentorAssignment.Role.MAIN_MENTOR
        )
        assignment.delete()
        self.assertEqual(self.event_1.mentor_assignments.count(), 0)
        self.assertTrue(Mentor.objects.filter(id=self.mentor_a.id).exists())

    def test_mentor_deletion_cascades_assignments_preserving_event(self):
        """Deleting a mentor cascades assignments but preserves the event."""
        EventMentorAssignment.objects.create(
            event=self.event_1,
            mentor=self.mentor_a,
            role=EventMentorAssignment.Role.MAIN_MENTOR
        )
        self.mentor_a.delete()
        self.assertEqual(self.event_1.mentor_assignments.count(), 0)
        self.assertTrue(Event.objects.filter(id=self.event_1.id).exists())

    def test_event_serializer_assignments_sync(self):
        """EventSerializer syncs assignments list correctly on create and update."""
        serializer_data = {
            "title": "Bootcamp 2026",
            "description": "Intensive training",
            "date": timezone.now().isoformat(),
            "available_seats": 30,
            "assignments": [
                {
                    "mentor_id": self.mentor_b.id,
                    "role": "main_mentor",
                    "responsibility": "Curriculum"
                },
                {
                    "mentor_id": self.mentor_c.id,
                    "role": "custom",
                    "custom_role": "Evaluator",
                    "responsibility": "Review"
                }
            ]
        }
        serializer = EventSerializer(data=serializer_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        event = serializer.save()

        self.assertEqual(event.mentor_assignments.count(), 2)
        assignments = {a.mentor_id: a for a in event.mentor_assignments.all()}
        self.assertEqual(assignments[self.mentor_b.id].role, "main_mentor")
        self.assertEqual(assignments[self.mentor_c.id].custom_role, "Evaluator")


class MentorAndAssignmentApiTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.mkdtemp()
        media_override = override_settings(MEDIA_ROOT=self.media_dir)
        media_override.enable()
        self.addCleanup(media_override.disable)
        self.addCleanup(shutil.rmtree, self.media_dir, ignore_errors=True)

        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="pass12345", role="admin"
        )
        self.client.force_authenticate(self.admin)
        self.mentor_a = Mentor.objects.create(name="Mentor A", expertise="Frontend")
        self.mentor_b = Mentor.objects.create(name="Mentor B", expertise="Backend")
        self.event = Event.objects.create(title="Spring Camp", description="d", date=timezone.now())
        self.other_event = Event.objects.create(title="Autumn Camp", description="d", date=timezone.now())

    def _put_assignments(self, assignments, event=None):
        event = event or self.event
        payload = {
            "title": event.title,
            "description": "d",
            "date": timezone.now().isoformat(),
            "assignments": assignments,
        }
        return self.client.put(f"/api/v1/events/{event.slug}/", payload, format="json")

    # --- Mentor directory ---

    def test_mentor_crud_by_primary_key(self):
        res = self.client.post("/api/v1/mentors/", {"name": "New", "expertise": "AI"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        for field in ("member", "member_name", "member_slug", "is_internal_member", "slug"):
            self.assertNotIn(field, res.data)
        mentor_id = res.data["id"]

        res = self.client.get(f"/api/v1/mentors/{mentor_id}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["event_assignments"], [])

        res = self.client.patch(f"/api/v1/mentors/{mentor_id}/", {"name": "Renamed"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["name"], "Renamed")

        res = self.client.delete(f"/api/v1/mentors/{mentor_id}/")
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Mentor.objects.filter(id=mentor_id).exists())

    def test_non_numeric_mentor_identifier_returns_404(self):
        self.assertEqual(self.client.get("/api/v1/mentors/mentor-a/").status_code, 404)

    def test_mentor_directory_server_pagination(self):
        for i in range(12):
            Mentor.objects.create(name=f"Bulk {i:02d}", expertise="x")
        res = self.client.get("/api/v1/mentors/", {"page": 2, "page_size": 10, "ordering": "name"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(set(res.data.keys()), {"count", "next", "previous", "results"})
        self.assertEqual(res.data["count"], 14)
        self.assertEqual(len(res.data["results"]), 4)

    def test_mentor_save_does_not_change_event_assignments(self):
        EventMentorAssignment.objects.create(
            event=self.event, mentor=self.mentor_a, role="speaker", responsibility="AI"
        )
        res = self.client.put(
            f"/api/v1/mentors/{self.mentor_a.id}/", {"name": "Mentor A2", "expertise": "Frontend"}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        assignment = EventMentorAssignment.objects.get(event=self.event, mentor=self.mentor_a)
        self.assertEqual((assignment.role, assignment.responsibility), ("speaker", "AI"))
        self.assertEqual(res.data["event_assignments"][0]["role_label"], "Speaker")

    # --- Assignments ---

    def test_multiple_main_mentors_and_roles_returned(self):
        res = self._put_assignments([
            {"mentor_id": self.mentor_a.id, "role": "main_mentor", "responsibility": "Frontend Development"},
            {"mentor_id": self.mentor_b.id, "role": "main_mentor", "responsibility": "Backend Development"},
        ])
        self.assertEqual(res.status_code, 200, res.data)
        labels = [(a["mentor_id"], a["role_label"], a["responsibility"]) for a in res.data["mentor_assignments"]]
        self.assertEqual(labels, [
            (self.mentor_a.id, "Main Mentor", "Frontend Development"),
            (self.mentor_b.id, "Main Mentor", "Backend Development"),
        ])

    def test_same_mentor_different_roles_per_event_are_independent(self):
        self._put_assignments([{"mentor_id": self.mentor_a.id, "role": "main_mentor"}])
        self._put_assignments([{"mentor_id": self.mentor_a.id, "role": "speaker"}], event=self.other_event)
        self._put_assignments([{"mentor_id": self.mentor_a.id, "role": "judge"}])
        self.assertEqual(EventMentorAssignment.objects.get(event=self.event).role, "judge")
        self.assertEqual(EventMentorAssignment.objects.get(event=self.other_event).role, "speaker")

    def test_empty_responsibility_accepted(self):
        res = self._put_assignments([{"mentor_id": self.mentor_a.id, "role": "co_mentor"}])
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["mentor_assignments"][0]["responsibility"], "")

    def test_custom_role_normalized(self):
        res = self._put_assignments([
            {"mentor_id": self.mentor_a.id, "role": "custom", "custom_role": "  Keynote   Panelist "},
        ])
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["mentor_assignments"][0]["custom_role"], "Keynote Panelist")
        self.assertEqual(res.data["mentor_assignments"][0]["role_label"], "Keynote Panelist")

    def test_custom_role_required(self):
        for value in ("", "   ", None):
            res = self._put_assignments([{"mentor_id": self.mentor_a.id, "role": "custom", "custom_role": value}])
            self.assertEqual(res.status_code, 400, value)

    def test_custom_role_conflicting_with_built_in_rejected(self):
        for value in ("main mentor", "Co Mentor", "JUDGE"):
            res = self._put_assignments([{"mentor_id": self.mentor_a.id, "role": "custom", "custom_role": value}])
            self.assertEqual(res.status_code, 400, value)

    def test_custom_role_cleared_for_built_in_roles(self):
        res = self._put_assignments([
            {"mentor_id": self.mentor_a.id, "role": "speaker", "custom_role": "Ignored"},
        ])
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(EventMentorAssignment.objects.get(event=self.event).custom_role, "")

    def test_unknown_role_rejected_and_existing_assignments_kept(self):
        self._put_assignments([{"mentor_id": self.mentor_a.id, "role": "speaker"}])
        res = self._put_assignments([{"mentor_id": self.mentor_b.id, "role": "wizard"}])
        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            list(self.event.mentor_assignments.values_list("mentor_id", "role")),
            [(self.mentor_a.id, "speaker")],
        )

    def test_unknown_or_missing_mentor_rejected(self):
        self.assertEqual(self._put_assignments([{"mentor_id": 999999, "role": "speaker"}]).status_code, 400)
        self.assertEqual(self._put_assignments([{"role": "speaker"}]).status_code, 400)

    def test_duplicate_mentor_in_payload_rejected(self):
        res = self._put_assignments([
            {"mentor_id": self.mentor_a.id, "role": "speaker"},
            {"mentor_id": self.mentor_a.id, "role": "judge"},
        ])
        self.assertEqual(res.status_code, 400)
        self.assertIn("Mentor A", str(res.data["assignments"]))

    def test_removing_assignment_keeps_mentor_and_omitting_field_keeps_assignments(self):
        self._put_assignments([
            {"mentor_id": self.mentor_a.id, "role": "speaker"},
            {"mentor_id": self.mentor_b.id, "role": "judge"},
        ])
        self._put_assignments([{"mentor_id": self.mentor_b.id, "role": "judge"}])
        self.assertEqual(list(self.event.mentor_assignments.values_list("mentor_id", flat=True)), [self.mentor_b.id])
        self.assertTrue(Mentor.objects.filter(id=self.mentor_a.id, name="Mentor A").exists())

        res = self.client.patch(f"/api/v1/events/{self.event.slug}/", {"location": "Hall"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.event.mentor_assignments.count(), 1)

    def test_multipart_event_save_with_image_and_json_assignments(self):
        payload = {
            "title": "Multipart Event",
            "description": "d",
            "date": timezone.now().isoformat(),
            "image": SimpleUploadedFile("cover.gif", TINY_GIF, content_type="image/gif"),
            "assignments": json.dumps([
                {"mentor_id": self.mentor_a.id, "role": "instructor", "responsibility": "Lab"},
            ]),
        }
        res = self.client.post("/api/v1/events/", payload, format="multipart")
        self.assertEqual(res.status_code, 201, res.data)
        event = Event.objects.get(id=res.data["id"])
        self.assertTrue(event.image.name)
        self.assertEqual(
            list(event.mentor_assignments.values_list("role", "responsibility")), [("instructor", "Lab")]
        )

    def test_malformed_assignments_json_rejected(self):
        res = self.client.post(
            "/api/v1/events/",
            {"title": "Bad", "description": "d", "date": timezone.now().isoformat(), "assignments": "[{"},
            format="multipart",
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Event.objects.filter(title="Bad").exists())

    def test_assignment_change_leaves_other_fields_untouched(self):
        self.event.location = "Main Hall"
        self.event.save()
        res = self.client.patch(
            f"/api/v1/events/{self.event.slug}/",
            {"assignments": [{"mentor_id": self.mentor_a.id, "role": "speaker"}]},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.event.refresh_from_db()
        self.mentor_a.refresh_from_db()
        self.assertEqual(self.event.location, "Main Hall")
        self.assertEqual((self.mentor_a.name, self.mentor_a.expertise), ("Mentor A", "Frontend"))

    def test_event_list_is_server_paginated(self):
        res = self.client.get("/api/v1/events/", {"page": 1, "page_size": 1})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 2)
        self.assertEqual(len(res.data["results"]), 1)

    def test_mentor_assigned_events_create_and_update(self):
        # 1. Create mentor with assigned events
        payload = {
            "name": "New Mentor",
            "expertise": "DevOps",
            "assigned_events": [
                {"event_id": self.event.id, "role": "speaker", "responsibility": "Keynote Speaker"}
            ]
        }
        res = self.client.post("/api/v1/mentors/", payload, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        mentor_id = res.data["id"]
        self.assertEqual(len(res.data["event_assignments"]), 1)
        self.assertEqual(res.data["event_assignments"][0]["event_id"], self.event.id)
        self.assertEqual(res.data["event_assignments"][0]["role"], "speaker")

        # 2. Check event details to verify it shows the new mentor
        ev_res = self.client.get(f"/api/v1/events/{self.event.slug}/")
        self.assertEqual(ev_res.status_code, 200)
        assigned_mentor_ids = [m["mentor_id"] for m in ev_res.data["mentor_assignments"]]
        self.assertIn(mentor_id, assigned_mentor_ids)

        # 3. Update mentor's assigned events via PATCH
        patch_payload = {
            "assigned_events": [
                {"event_id": self.other_event.id, "role": "judge", "responsibility": "Finals Judge"}
            ]
        }
        res_patch = self.client.patch(f"/api/v1/mentors/{mentor_id}/", patch_payload, format="json")
        self.assertEqual(res_patch.status_code, 200, res_patch.data)
        self.assertEqual(len(res_patch.data["event_assignments"]), 1)
        self.assertEqual(res_patch.data["event_assignments"][0]["event_id"], self.other_event.id)

        # 4. Verify previous event no longer includes this mentor
        ev_res2 = self.client.get(f"/api/v1/events/{self.event.slug}/")
        assigned_ids_after = [m["mentor_id"] for m in ev_res2.data["mentor_assignments"]]
        self.assertNotIn(mentor_id, assigned_ids_after)

    def test_duplicate_event_assignment_on_mentor_rejected(self):
        payload = {
            "name": "Dupe Mentor",
            "expertise": "Security",
            "assigned_events": [
                {"event_id": self.event.id, "role": "speaker"},
                {"event_id": self.event.id, "role": "judge"}
            ]
        }
        res = self.client.post("/api/v1/mentors/", payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("assigned_events", res.data)

