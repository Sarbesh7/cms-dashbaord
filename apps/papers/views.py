from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import PastPaper
from .serializers import PastPaperSerializer
from django.http import Http404
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from apps.core.pagination import StandardPagination
from apps.core.permissions import HasModulePermission
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.db.models import Q
import logging
from apps.core.activity_logging import diff_snapshots, log_activity, model_snapshot
from apps.core.ordering import apply_ordering

logger = logging.getLogger('pastpaper')

PAPER_ORDERING = {f: f for f in ('id', 'subject_name', 'semester', 'exam_year', 'model_set', 'is_old_course', 'created_at')}

class PastPaperListView(APIView):
    permission_module = "papers"
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated(), HasModulePermission("papers")]
    
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
        for value in (semester_filter, exam_year_filter):
            if value and not str(value).isdigit():
                return Response({"detail": "Invalid filter value."}, status=status.HTTP_400_BAD_REQUEST)
        if semester_filter:
            papers = papers.filter(semester=semester_filter)
        if model_set_filter is not None and model_set_filter != '':
            papers = papers.filter(model_set=(model_set_filter.lower() in ('true', '1', 'yes')))
        if is_old_course_filter is not None and is_old_course_filter != '':
            papers = papers.filter(is_old_course=(is_old_course_filter.lower() in ('true', '1', 'yes')))
        if exam_year_filter:
            papers = papers.filter(exam_year=exam_year_filter)

        papers = apply_ordering(papers, request.query_params.get('ordering'), PAPER_ORDERING,
                                ['-exam_year', '-semester', 'subject_name'])

        paginator = StandardPagination()
        paginated_papers = paginator.paginate_queryset(papers, request)
        serializer = PastPaperSerializer(paginated_papers, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = PastPaperSerializer(data=request.data)
        if serializer.is_valid():
            paper = serializer.save()
            log_activity(request, action="create", module="papers", target_id=paper.id, target_repr=str(paper),
                         description=f"Created past paper {paper}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        logger.warning(
            f"Failed POST creation for Past Paper. Errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class PastPaperDetailView(APIView):
    permission_module = "papers"
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated(), HasModulePermission("papers")]
    
    def get_object(self, slug):
        try:
            if str(slug).isdigit():
                return PastPaper.objects.get(pk=int(slug))
        except (ValueError, TypeError):
            pass
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
        before = model_snapshot(paper)
        serializer = PastPaperSerializer(paper, data=request.data)
        if serializer.is_valid():
            paper = serializer.save()
            log_activity(request, action="update", module="papers", target_id=paper.id, target_repr=str(paper),
                         description=f"Updated past paper {paper}",
                         changes=diff_snapshots(before, model_snapshot(paper)))
            return Response(serializer.data)
        logger.warning(
            f"Failed PUT update for Past Paper Slug '{slug}'. Errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, slug):
        paper = self.get_object(slug)
        if paper is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        paper_subject, paper_id, paper_label = paper.subject_name, paper.id, str(paper)
        paper.delete()
        log_activity(request, action="delete", module="papers", target_id=paper_id, target_repr=paper_label,
                     description=f"Deleted past paper {paper_label}")
        
        logger.info(
            f"Past paper '{paper_subject}' (Slug: {slug}) was deleted by User: {request.user}"
        )
        return Response(status=status.HTTP_204_NO_CONTENT)