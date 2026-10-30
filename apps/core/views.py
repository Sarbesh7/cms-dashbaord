from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.db.models import Q
from apps.notices.models import Notice
from apps.events.models import Event, Mentor
from apps.certificates.models import Certificate


class DashboardStatsView(APIView):
    """
    Returns aggregated system statistics for dashboard cards.
    Replaces client-side list filtering and accurately reflects true database counts.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        published_notices = Notice.objects.filter(status__iexact="published").count()
        open_events = Event.objects.filter(
            Q(status__iexact="published") | Q(status__iexact="open")
        ).count()
        total_mentors = Mentor.objects.count()
        completed_certificates = Certificate.objects.filter(is_project_completed=True).count()

        return Response({
            "published_notices": published_notices,
            "open_events": open_events,
            "total_mentors": total_mentors,
            "completed_certificates": completed_certificates,
            "publishedNoticesCount": published_notices,
            "openEventsCount": open_events,
            "totalMentorsCount": total_mentors,
            "certificatesIssuedCount": completed_certificates,
        })
