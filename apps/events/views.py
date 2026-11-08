import logging

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.activity_logging import diff_snapshots, log_activity, model_snapshot
from apps.core.cache import versioned_cache_page
from apps.core.ordering import apply_ordering
from apps.core.pagination import StandardPagination
from apps.core.permissions import HasModulePermission
from apps.core.visibility import PUBLIC_EVENT_STATUSES, can_view_private
from .models import Event, Mentor
from .serializers import EventListSerializer, EventSerializer, MentorSerializer

logger = logging.getLogger("event")

EVENT_ORDERING = {
    "id": "id", "title": "title", "category": "category", "status": "status",
    "startDate": "date", "date": "date", "dates": "date", "createdAt": "created_at", "created_at": "created_at",
}
MENTOR_ORDERING = {
    "id": "id", "fullName": "name", "name": "name", "role": "expertise", "expertise": "expertise",
    "createdAt": "created_at", "created_at": "created_at",
}


def _event_queryset():
    return Event.objects.select_related('tenure').prefetch_related(
        'mentor_assignments__mentor', 'mentors__event_assignments__event'
    )


def _event_list_queryset():
    """Lightweight queryset for event listings: eager-loads tenure and event mentors without recursive event trees."""
    return Event.objects.select_related('tenure').prefetch_related('mentor_assignments__mentor')


class _ModuleView(APIView):
    """GET is public (published data only); writes need the module permission."""
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_module = None

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated(), HasModulePermission(self.permission_module)]

    def is_private(self, request):
        return can_view_private(request, self.permission_module)

    def serializer_context(self, request):
        return {'request': request, 'public': not self.is_private(request)}


class EventListView(_ModuleView):
    permission_module = "events"

    @versioned_cache_page(60 * 5)
    def get(self, request):
        events = _event_list_queryset()
        if not self.is_private(request):
            events = events.filter(status__in=PUBLIC_EVENT_STATUSES)

        search = request.query_params.get("search") or request.query_params.get("name") or request.query_params.get("title")
        status_filter = request.query_params.get("status")
        category_filter = request.query_params.get("category")
        id_filter = request.query_params.get("id")
        date_filter = request.query_params.get("date")

        try:
            if id_filter:
                events = events.filter(id=int(id_filter))
            if date_filter:
                events = events.filter(date__date=date_filter)
        except (ValueError, Exception):
            return Response({"detail": "Invalid filter value."}, status=status.HTTP_400_BAD_REQUEST)
        if search:
            events = events.filter(title__icontains=search)
        if status_filter:
            events = events.filter(status=status_filter)
        if category_filter:
            events = events.filter(category=category_filter)

        events = apply_ordering(events, request.query_params.get("ordering"), EVENT_ORDERING, "-created_at")
        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(events, request)
        serializer = EventListSerializer(result_page, many=True, context=self.serializer_context(request))
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = EventSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            event = serializer.save()
            logger.info(f"Event created: '{event.title}' (ID: {event.id}) by user id {request.user.pk}")
            log_activity(request, action="create", module="events", target_id=event.id, target_repr=event.title,
                         description=f"Created event '{event.title}'")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.warning(f"Failed event creation attempt. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EventDetailsView(_ModuleView):
    permission_module = "events"

    def get_object(self, slug, request=None):
        qs = _event_queryset()
        if request is not None and not self.is_private(request):
            qs = qs.filter(status__in=PUBLIC_EVENT_STATUSES)
        if str(slug).isdigit():
            return get_object_or_404(qs, id=int(slug))
        return get_object_or_404(qs, slug__iexact=slug)

    @versioned_cache_page(60 * 5)
    def get(self, request, slug):
        event = self.get_object(slug, request)
        return Response(EventSerializer(event, context=self.serializer_context(request)).data)

    def _update(self, request, slug, partial):
        event = self.get_object(slug)
        before = model_snapshot(event)
        serializer = EventSerializer(event, data=request.data, partial=partial, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            event.refresh_from_db()
            logger.info(f"Event '{event.title}' updated by user id {request.user.pk}")
            log_activity(request, action="update", module="events", target_id=event.id, target_repr=event.title,
                         description=f"Updated event '{event.title}'",
                         changes=diff_snapshots(before, model_snapshot(event)))
            return Response(serializer.data, status=status.HTTP_200_OK)
        logger.warning(f"Failed update for event '{slug}'. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, slug):
        return self._update(request, slug, partial=False)

    def patch(self, request, slug):
        return self._update(request, slug, partial=True)

    def delete(self, request, slug):
        event = self.get_object(slug)
        event_title, event_id = event.title, event.id
        event.delete()
        logger.info(f"Event '{event_title}' deleted by user id {request.user.pk}")
        log_activity(request, action="delete", module="events", target_id=event_id, target_repr=event_title,
                     description=f"Deleted event '{event_title}'")
        return Response(status=status.HTTP_204_NO_CONTENT)


class MentorListView(_ModuleView):
    permission_module = "mentors"

    @versioned_cache_page(60 * 5)
    def get(self, request):
        mentors = Mentor.objects.prefetch_related('event_assignments__event').all()

        search = request.query_params.get("search") or request.query_params.get("name")
        id_filter = request.query_params.get("id")
        if id_filter:
            if not str(id_filter).isdigit():
                return Response({"detail": "Invalid filter value."}, status=status.HTTP_400_BAD_REQUEST)
            mentors = mentors.filter(id=int(id_filter))
        if search:
            mentors = mentors.filter(name__icontains=search)

        mentors = apply_ordering(mentors, request.query_params.get("ordering"), MENTOR_ORDERING, "-created_at")
        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(mentors, request)
        serializer = MentorSerializer(result_page, many=True, context=self.serializer_context(request))
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = MentorSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            mentor = serializer.save()
            logger.info(f"Mentor created: ID {mentor.id} by user id {request.user.pk}")
            log_activity(request, action="create", module="mentors", target_id=mentor.id, target_repr=str(mentor),
                         description=f"Created mentor '{mentor}'")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.warning(f"Failed mentor creation attempt. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MentorDetailsView(_ModuleView):
    permission_module = "mentors"

    def get_object(self, identifier):
        return get_object_or_404(Mentor.objects.prefetch_related('event_assignments__event'), id=identifier)

    @versioned_cache_page(60 * 5)
    def get(self, request, identifier):
        mentor = self.get_object(identifier)
        return Response(MentorSerializer(mentor, context=self.serializer_context(request)).data)

    def _update(self, request, identifier, partial):
        mentor = self.get_object(identifier)
        before = model_snapshot(mentor)
        serializer = MentorSerializer(mentor, data=request.data, partial=partial, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            mentor.refresh_from_db()
            log_activity(request, action="update", module="mentors", target_id=mentor.id, target_repr=str(mentor),
                         description=f"Updated mentor '{mentor}'",
                         changes=diff_snapshots(before, model_snapshot(mentor)))
            return Response(serializer.data, status=status.HTTP_200_OK)
        logger.warning(f"Failed update for mentor '{identifier}'. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, identifier):
        return self._update(request, identifier, partial=False)

    def patch(self, request, identifier):
        return self._update(request, identifier, partial=True)

    def delete(self, request, identifier):
        mentor = self.get_object(identifier)
        name, mentor_id = str(mentor), mentor.id
        mentor.delete()
        log_activity(request, action="delete", module="mentors", target_id=mentor_id, target_repr=name,
                     description=f"Deleted mentor '{name}'")
        return Response(status=status.HTTP_204_NO_CONTENT)
