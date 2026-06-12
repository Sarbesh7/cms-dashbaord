from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import PastPaper
from .serializers import PastPaperSerializer
from django.http import Http404
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser 
# from apps.core.pagination import StandardPagination
from apps.core.permission import IsAdmin, IsCMSUser
from apps.core.pagination import StandardPagination
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

# Create your views here.
class PastPaperListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    
    @method_decorator(cache_page(60 * 5), name='dispatch')
    def get(self, request):
        papers = PastPaper.objects.all()
        paginator = StandardPagination()
        paginated_papers = paginator.paginate_queryset(papers, request)
        serializer = PastPaperSerializer(paginated_papers, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = PastPaperSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class PastPaperDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    
    def get_object(self, slug):
        try:
            return PastPaper.objects.get(slug=slug)
        except PastPaper.DoesNotExist:
            return None
        
    @method_decorator(cache_page(60 * 5), name='dispatch')   
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
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, slug):
        paper = self.get_object(slug)
        if paper is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        paper.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)