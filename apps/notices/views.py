from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Notice
from django.http import Http404
from rest_framework import status
from .serializers import NoticeSerializer
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser 
from apps.core.pagination import StandardPagination
from apps.core.permission import IsAdmin, IsCMSUser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
import logging

logger = logging.getLogger('notice')


class NoticeListView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_classes = [IsAuthenticatedOrReadOnly]

    @method_decorator(cache_page(60 * 5), name='dispatch')
    def get(self, request):
        notices = Notice.objects.all()

        search = request.query_params.get('search') or request.query_params.get('name') or request.query_params.get('title')
        status_filter = request.query_params.get('status')
        category_filter = request.query_params.get('category')
        id_filter = request.query_params.get('id')
        date_filter = request.query_params.get('date')

        if id_filter:
            notices = notices.filter(id=id_filter)
        if search:
            notices = notices.filter(title__icontains=search)
        if status_filter:
            notices = notices.filter(status=status_filter)
        if category_filter:
            notices = notices.filter(category=category_filter)
        if date_filter:
            notices = notices.filter(created_at__date=date_filter)

        ordering = request.query_params.get("ordering")
        if ordering:
            is_desc = ordering.startswith("-")
            field = ordering.lstrip("-")
            mapping = {
                "id": "id",
                "title": "title",
                "category": "category",
                "status": "status",
                "createdAt": "created_at",
            }
            db_field = mapping.get(field, field)
            if is_desc:
                db_field = f"-{db_field}"
            try:
                notices = notices.order_by(db_field)
            except Exception:
                notices = notices.order_by("-created_at")
        else:
            notices = notices.order_by("-created_at")   
         
        paginator = StandardPagination() 
        result_page = paginator.paginate_queryset(notices, request) 

        serializer = NoticeSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)
    
    def post(self, request):
        serializer = NoticeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(
                f"Notice '{serializer.data['title']}' (Slug: {serializer.data['slug']}) created by User: {request.user}"
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.warning(
            f"Failed post update for Notice. Errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            

class NoticeDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_object(self, slug):
        try:
            return Notice.objects.get(slug=slug)
        except Notice.DoesNotExist:
            raise Http404
        
    @method_decorator(cache_page(60 * 5), name='dispatch')
    def get(self, request, slug):
        notice = self.get_object(slug)
        serializer = NoticeSerializer(notice)
        return Response(serializer.data)

    def put(self, request, slug):
        notice = self.get_object(slug)
        serializer = NoticeSerializer(notice, data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(
                f"Notice '{notice.title}' (Slug: {slug}) fully updated (PUT) by User: {request.user}"
            )
            return Response(serializer.data)
        
        logger.warning(
            f"Failed PUT update for Notice Slug '{slug}'. Errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, slug):
        notice = self.get_object(slug)
        notice.delete()
        
        logger.info(
            f"Notice '{notice.title}' (Slug: {slug}) was deleted by User: {request.user}"
        )
        return Response(status=status.HTTP_204_NO_CONTENT)