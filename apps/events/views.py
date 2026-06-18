import logging
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from .models import Event, Mentor
from .serializers import EventSerializer, MentorSerializer
from apps.core.pagination import StandardPagination
from apps.core.permission import IsAdmin, IsCMSUser

logger = logging.getLogger("event")


class EventListView(APIView):

    def get_permissions(self):

        if self.request.method == "GET":
            return [AllowAny()]
        return [IsCMSUser()]

    @method_decorator(cache_page(60 * 5))
    def get(self, request):
        events = Event.objects.all()

        search = request.query_params.get("search")
        status_filter = request.query_params.get("status")

        if search:
            events = events.filter(title__icontains=search)
        if status_filter:
            events = events.filter(status=status_filter)

        events = events.order_by("-created_at")

        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(events, request)

        serializer = EventSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = EventSerializer(data=request.data)
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
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsCMSUser()]

    @method_decorator(cache_page(60 * 5))
    def get(self, request, slug):
        event = get_object_or_404(Event, slug__iexact=slug)
        serializer = EventSerializer(event)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, slug):
        event = get_object_or_404(Event, slug__iexact=slug)
        serializer = EventSerializer(event, data=request.data)
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

    def delete(self, request, slug):
        event = get_object_or_404(Event, slug__iexact=slug)
        event_title = event.title
        event.delete()
        logger.info(
            f"Event '{event_title}' (Slug: {slug}) was deleted by User: {request.user}"
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MentorListView(APIView):

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsCMSUser()]

    @method_decorator(cache_page(60 * 5))
    def get(self, request):
        mentors = Mentor.objects.all()
        serializer = MentorSerializer(mentors, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = MentorSerializer(data=request.data)
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

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsCMSUser()]

    def get_object(self, slug):
        return get_object_or_404(Mentor, slug=slug)

    @method_decorator(cache_page(60 * 5))
    def get(self, request, slug):
        mentor = self.get_object(slug)
        serializer = MentorSerializer(mentor)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, slug):
        mentor = self.get_object(slug)
        serializer = MentorSerializer(mentor, data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Mentor ID {slug} fully updated (PUT) by User: {request.user}")
            return Response(serializer.data, status=status.HTTP_200_OK)

        logger.warning(
            f"Failed PUT update for Mentor ID {slug}. Errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, slug):
        mentor = self.get_object(slug)
        serializer = MentorSerializer(mentor, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info(
                f"Mentor ID {slug} partially updated (PATCH) by User: {request.user}"
            )
            return Response(serializer.data, status=status.HTTP_200_OK)

        logger.warning(
            f"Failed PATCH update for Mentor ID {slug}. Errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, slug):
        mentor = self.get_object(slug)
        mentor_name = mentor.name
        mentor.delete()
        logger.info(
            f"Mentor '{mentor_name}' (ID: {slug}) was deleted by User: {request.user}"
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
