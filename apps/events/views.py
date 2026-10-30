import logging
from django.shortcuts import get_object_or_404
from apps.core.cache import versioned_cache_page
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser

from .models import Event, Mentor
from .serializers import EventSerializer, MentorSerializer
from apps.core.pagination import StandardPagination
from apps.core.permission import IsCMSUser, IsAdmin

logger = logging.getLogger("event")


class EventListView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsCMSUser()]

    @versioned_cache_page(60 * 5)
    def get(self, request):
        events = Event.objects.select_related('tenure').prefetch_related('mentor_assignments__mentor', 'mentors__event_assignments__event').all()

        search = request.query_params.get("search") or request.query_params.get("name") or request.query_params.get("title")
        status_filter = request.query_params.get("status")
        category_filter = request.query_params.get("category")
        id_filter = request.query_params.get("id")
        date_filter = request.query_params.get("date")

        if id_filter:
            events = events.filter(id=id_filter)
        if search:
            events = events.filter(title__icontains=search)
        if status_filter:
            events = events.filter(status=status_filter)
        if category_filter:
            events = events.filter(category=category_filter)
        if date_filter:
            events = events.filter(date__date=date_filter)

        ordering = request.query_params.get("ordering")
        if ordering:
            is_desc = ordering.startswith("-")
            field = ordering.lstrip("-")
            mapping = {
                "id": "id",
                "title": "title",
                "category": "category",
                "status": "status",
                "startDate": "date",
                "date": "date",
                "dates": "date",
                "createdAt": "created_at",
            }
            db_field = mapping.get(field, field)
            if is_desc:
                db_field = f"-{db_field}"
            try:
                events = events.order_by(db_field)
            except Exception:
                events = events.order_by("-created_at")
        else:
            events = events.order_by("-created_at")

        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(events, request)

        serializer = EventSerializer(result_page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = EventSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            event = serializer.save()
            logger.info(
                f"Event created successfully: '{event.title}' (ID: {event.id}) by User: {request.user}"
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        logger.warning(
            f"Failed event creation attempt. Errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EventDetailsView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsCMSUser()]

    def get_object(self, slug):
        return get_object_or_404(
            Event.objects.select_related('tenure').prefetch_related('mentor_assignments__mentor', 'mentors__event_assignments__event'),
            slug__iexact=slug
        )

    @versioned_cache_page(60 * 5)
    def get(self, request, slug):
        event = self.get_object(slug)
        serializer = EventSerializer(event, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, slug):
        event = self.get_object(slug)
        serializer = EventSerializer(event, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            logger.info(
                f"Event '{event.title}' fully updated (PUT) by User: {request.user}"
            )
            return Response(serializer.data, status=status.HTTP_200_OK)

        logger.warning(
            f"Failed PUT update for Event Slug '{slug}'. Errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, slug):
        event = self.get_object(slug)
        serializer = EventSerializer(event, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            logger.info(
                f"Event '{event.title}' partially updated (PATCH) by User: {request.user}"
            )
            return Response(serializer.data, status=status.HTTP_200_OK)

        logger.warning(
            f"Failed PATCH update for Event Slug '{slug}'. Errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, slug):
        
        if not IsAdmin().has_permission(request, self) and not (request.user.is_authenticated and request.user.is_staff):
            return Response(
            {"detail": "You do not have permission to perform this action."},
            status=status.HTTP_403_FORBIDDEN
        )
        
        event = self.get_object(slug)
        event_title = event.title
        event.delete()
        logger.info(
            f"Event '{event_title}' (Slug: {slug}) was deleted by User: {request.user}"
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MentorListView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsCMSUser()]

    @versioned_cache_page(60 * 5)
    def get(self, request):
        mentors = Mentor.objects.prefetch_related('event_assignments__event').all()

        search = request.query_params.get("search") or request.query_params.get("name")
        id_filter = request.query_params.get("id")

        if id_filter:
            mentors = mentors.filter(id=id_filter)
        if search:
            mentors = mentors.filter(name__icontains=search)

        ordering = request.query_params.get("ordering")
        if ordering:
            is_desc = ordering.startswith("-")
            field = ordering.lstrip("-")
            mapping = {
                "id": "id",
                "fullName": "name",
                "name": "name",
                "role": "expertise",
                "expertise": "expertise",
            }
            db_field = mapping.get(field, field)
            if is_desc:
                db_field = f"-{db_field}"
            try:
                mentors = mentors.order_by(db_field)
            except Exception:
                mentors = mentors.order_by("-created_at")
        else:
            mentors = mentors.order_by("-created_at")

        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(mentors, request)

        serializer = MentorSerializer(result_page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = MentorSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            mentor = serializer.save()
            logger.info(
                f"Mentor created successfully: {mentor.name} (ID: {mentor.id}) by User: {request.user}"
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        logger.warning(
            f"Failed mentor creation attempt. Errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MentorDetailsView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsCMSUser()]

    def get_object(self, identifier):
        qs = Mentor.objects.prefetch_related('event_assignments__event')
        return get_object_or_404(qs, id=identifier)

    @versioned_cache_page(60 * 5)
    def get(self, request, identifier):
        mentor = self.get_object(identifier)
        serializer = MentorSerializer(mentor, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, identifier):
        target = identifier
        mentor = self.get_object(target)
        serializer = MentorSerializer(mentor, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Mentor '{target}' fully updated (PUT) by User: {request.user}")
            return Response(serializer.data)

        logger.warning(
            f"Failed PUT update for Mentor '{target}'. Errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, identifier):
        target = identifier
        mentor = self.get_object(target)
        serializer = MentorSerializer(mentor, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            logger.info(
                f"Mentor '{target}' partially updated (PATCH) by User: {request.user}"
            )
            return Response(serializer.data, status=status.HTTP_200_OK)

        logger.warning(
            f"Failed PATCH update for Mentor '{target}'. Errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, identifier):
        target = identifier
        if not IsAdmin().has_permission(request, self) and not (request.user.is_authenticated and request.user.is_staff):
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        mentor = self.get_object(target)
        mentor_name = mentor.name
        mentor.delete()
        logger.info(
            f"Mentor '{mentor_name}' (ID: {target}) was deleted by User: {request.user}"
        )
        return Response(status=status.HTTP_204_NO_CONTENT)