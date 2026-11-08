from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import ActivityLog
from apps.core.dashboard import activity_log_summary
from apps.notifications.models import Notification, NotificationRecipient, NotificationSource
from apps.notifications.serializers import NotificationSentSerializer
from apps.events.models import Event, Mentor, EventMentorAssignment
from apps.events.serializers import EventListSerializer, EventSerializer
from apps.events.views import _event_list_queryset
from apps.tenure.models import Tenure, Member, TenureMembership

User = get_user_model()


class PerformanceOptimizationsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="perf_tester",
            email="perf@example.com",
            password="Password123!",
            role="superadmin",
            first_name="Perf",
            last_name="Tester",
        )
        self.recipient_user = User.objects.create_user(
            username="recipient_user",
            email="recipient@example.com",
            password="Password123!",
            role="cms_user",
        )

    def test_activity_log_summary_consolidated_queries(self):
        for i in range(5):
            ActivityLog.objects.create(
                action="login" if i % 2 == 0 else "create",
                module="events" if i % 2 == 0 else "notices",
                actor_id_snapshot=self.user.pk,
                actor_sys_id_snapshot=f"SYS-{self.user.pk}",
                actor_name_snapshot="Perf Tester",
                actor_username_snapshot="perf_tester",
                user_email_snapshot="perf@example.com",
                user_role_snapshot="superadmin",
            )

        # 2 queries: 1 for most_active, 1 for consolidated aggregate
        with self.assertNumQueries(2):
            summary = activity_log_summary()

        self.assertEqual(summary["total_activities"], 5)
        self.assertIn("logins_this_week", summary)
        self.assertIn("mutations_today", summary)
        self.assertIn("most_active_module", summary)

    def test_notification_sent_serializer_uses_prefetch_cache(self):
        notifications = []
        for i in range(3):
            n = Notification.objects.create(
                sender=self.user,
                title=f"Notification {i}",
                message=f"Message {i}",
                source_module=NotificationSource.DIRECT,
            )
            NotificationRecipient.objects.create(notification=n, recipient=self.recipient_user)
            notifications.append(n)

        qs = Notification.objects.filter(sender=self.user).prefetch_related('recipients__recipient')
        loaded_notifications = list(qs)

        # Serializing with prefetch cache takes ZERO extra queries for recipient_count
        with self.assertNumQueries(0):
            serializer = NotificationSentSerializer(loaded_notifications, many=True)
            data = serializer.data

        self.assertEqual(len(data), 3)
        for item in data:
            self.assertEqual(item["recipient_count"], 1)

    def test_event_list_serialization_lightweight_mentors(self):
        mentor = Mentor.objects.create(name="Jane Mentor", email="mentor@example.com", expertise="AI")
        event = Event.objects.create(
            title="AI Bootcamp",
            date=timezone.now(),
            description="Hands-on workshop",
            status="published",
        )
        EventMentorAssignment.objects.create(
            event=event,
            mentor=mentor,
            role="main_mentor",
            custom_role="",
            responsibility="Keynote",
        )

        # Load with list queryset
        loaded_events = list(_event_list_queryset().filter(id=event.id))

        with self.assertNumQueries(0):
            serializer = EventListSerializer(loaded_events, many=True)
            data = serializer.data

        self.assertEqual(len(data), 1)
        event_data = data[0]
        self.assertIn("mentor_assignments", event_data)
        self.assertEqual(len(event_data["mentor_assignments"]), 1)
        assignment = event_data["mentor_assignments"][0]
        self.assertEqual(assignment["mentor_name"], "Jane Mentor")
        self.assertEqual(assignment["role"], "main_mentor")
        self.assertEqual(assignment["role_label"], "Main Mentor")
        # Ensure heavy nested mentors_detail is not included in list serialization
        self.assertNotIn("mentors_detail", event_data)

