from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from apps.users.models import User
from apps.tenure.models import Tenure
from apps.events.models import Event
from apps.certificates.models import Certificate


class DataPreservationAndCertificateTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.superadmin = User.objects.create_superuser(
            username="superadmin", email="superadmin@csitabmc.org", password="Password123!", role="superadmin"
        )
        self.operations = User.objects.create_user(
            username="operations", email="ops@csitabmc.org", password="Password123!", role="operations"
        )
        self.blog_user = User.objects.create_user(
            username="bloguser", email="blog@csitabmc.org", password="Password123!", role="blog"
        )

        self.tenure = Tenure.objects.create(
            name="2025-2026 Executive Committee",
            slug="2025-2026-executive-committee",
            start_date=timezone.now().date(),
            end_date=timezone.now().date(),
        )

        self.event = Event.objects.create(
            tenure=self.tenure,
            title="Django Advanced Workshop",
            slug="django-advanced-workshop",
            description="Deep dive into Django and DRF",
            date=timezone.now(),
        )

    def test_tenure_deletion_preserves_event(self):
        """Deleting a Tenure must set Event.tenure to NULL without deleting the Event."""
        event_id = self.event.id
        self.tenure.delete()

        # Reload event
        self.event.refresh_from_db()
        self.assertEqual(self.event.id, event_id)
        self.assertIsNone(self.event.tenure)
        self.assertEqual(self.event.title, "Django Advanced Workshop")

    def test_event_deletion_preserves_certificate_and_snapshots_title(self):
        """Deleting an Event must set Certificate.event to NULL and preserve event_title snapshot."""
        cert = Certificate.objects.create(
            full_name="Aayush Sharma",
            event=self.event,
            is_project_completed=True,
        )
        self.assertEqual(cert.event_title, "Django Advanced Workshop")

        cert_id = cert.id
        # Delete event
        self.event.delete()

        cert.refresh_from_db()
        self.assertEqual(cert.id, cert_id)
        self.assertIsNone(cert.event)
        self.assertEqual(cert.event_title, "Django Advanced Workshop")
        self.assertIn("Django Advanced Workshop", str(cert))

    def test_certificate_api_authorization(self):
        """Operations role can issue certificate; Blog role is blocked."""
        payload = {
            "full_name": "Test Participant",
            "event": self.event.id,
            "is_project_completed": True,
        }

        # Blog user blocked from issuing certificate
        self.client.force_authenticate(user=self.blog_user)
        res = self.client.post("/api/v1/certificates/", payload)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Operations user allowed to issue certificate
        self.client.force_authenticate(user=self.operations)
        res = self.client.post("/api/v1/certificates/", payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Certificate.objects.filter(full_name="Test Participant").exists())
