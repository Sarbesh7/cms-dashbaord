from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import PastPaper
from .serializers import PastPaperSerializer
from django.http import Http404
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser 
# from apps.core.pagination import StandardPagination
from rest_framework.permissions import IsAuthenticated

# Create your views here.
class PastPaperListView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    
  

    def get(self, request):
        papers = models.PastPaper.objects.all()
        paginated_papers = paginator.paginate_queryset(papers, request)
        serializer = serializers.PastPaperSerializer(paginated_papers, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = serializers.PastPaperSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class PastPaperDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    
    def get_object(self, pk):
        try:
            return models.PastPaper.objects.get(pk=pk)
        except models.PastPaper.DoesNotExist:
            return None
        
    def get(self, request, pk):
        paper = self.get_object(pk)
        if paper is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = serializers.PastPaperSerializer(paper)
        return Response(serializer.data)
    
    def put(self, request, pk):
        paper = self.get_object(pk)
        if paper is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = serializers.PastPaperSerializer(paper, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        paper = self.get_object(pk)
        if paper is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        paper.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)