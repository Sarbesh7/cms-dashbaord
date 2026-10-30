from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import PastPaper
from .serializers import PastPaperSerializer
from django.http import Http404
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from apps.core.pagination import StandardPagination
from apps.core.permission import IsAdmin, IsCMSUser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.db.models import Q
import logging

logger = logging.getLogger('pastpaper')

class PastPaperListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    
    def get(self, request):
        papers = PastPaper.objects.all()

        search = request.query_params.get('search')
        semester_filter = request.query_params.get('semester')
        model_set_filter = request.query_params.get('model_set')
        is_old_course_filter = request.query_params.get('is_old_course')
        exam_year_filter = request.query_params.get('exam_year')

        if search:
            search_str = search.strip()
            matching_codes = [
                code for code, title in getattr(PastPaper, 'SUBJECT_CHOICES', ())
                if search_str.lower() in code.lower() or search_str.lower() in title.lower()
            ]
            papers = papers.filter(
                Q(subject_name__icontains=search_str) | Q(subject_name__in=matching_codes)
            )
        if semester_filter:
            papers = papers.filter(semester=semester_filter)
        if model_set_filter is not None and model_set_filter != '':
            papers = papers.filter(model_set=(model_set_filter.lower() in ('true', '1', 'yes')))
        if is_old_course_filter is not None and is_old_course_filter != '':
            papers = papers.filter(is_old_course=(is_old_course_filter.lower() in ('true', '1', 'yes')))
        if exam_year_filter:
            papers = papers.filter(exam_year=exam_year_filter)

        ordering = request.query_params.get('ordering')
        if ordering:
            is_desc = ordering.startswith('-')
            field = ordering.lstrip('-')
            mapping = {
                'subject_name': 'subject_name',
                'semester': 'semester',
                'exam_year': 'exam_year',
                'model_set': 'model_set',
                'is_old_course': 'is_old_course',
            }
            db_field = mapping.get(field, field)
            if is_desc:
                db_field = f'-{db_field}'
            try:
                papers = papers.order_by(db_field)
            except Exception:
                papers = papers.order_by('-exam_year', '-semester', 'subject_name')
        else:
            papers = papers.order_by('-exam_year', '-semester', 'subject_name')

        paginator = StandardPagination()
        paginated_papers = paginator.paginate_queryset(papers, request)
        serializer = PastPaperSerializer(paginated_papers, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = PastPaperSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        logger.warning(
            f"Failed POST creation for Past Paper. Errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class PastPaperDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    
    def get_object(self, slug):
        try:
            return PastPaper.objects.get(slug=slug)
        except PastPaper.DoesNotExist:
            return None
        
    def get(self, request, slug):
        paper = self.get_object(slug)
        if paper is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = PastPaperSerializer(paper)
        return Response(serializer.data)
    
    def put(self, request, slug):
        paper = self.get_object(slug)
        if paper is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = PastPaperSerializer(paper, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        logger.warning(
            f"Failed PUT update for Past Paper Slug '{slug}'. Errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, slug):
        
        if not IsAdmin().has_permission(request, self) and not (request.user.is_authenticated and request.user.is_staff):
            return Response(
            {"detail": "You do not have permission to perform this action."},
            status=status.HTTP_403_FORBIDDEN
        )
            
        paper = self.get_object(slug)
        if paper is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        paper_subject = paper.subject_name
        paper.delete()
        
        logger.info(
            f"Past paper '{paper_subject}' (Slug: {slug}) was deleted by User: {request.user}"
        )
        return Response(status=status.HTTP_204_NO_CONTENT)