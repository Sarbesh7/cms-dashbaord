from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Notice
from django.http import Http404
from rest_framework import status
from .serializers import NoticeSerializer
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser # image haru ko lagi by chance dekhaenwbhane 



class NoticeListView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get(self, request):
        notices = Notice.objects.all()
        serializer = NoticeSerializer(notices, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer =NoticeSerializer(data=request.data)
        if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
class NoticeDetailView(APIView):
    def get_object(self, pk):
        try:
            return Notice.objects.get(pk=pk)
        
        
        except Notice.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        notice = self.get_object(pk)
        serializer = NoticeSerializer(notice)
        return Response(serializer.data)

    def put(self, request, pk):
        notice = self.get_object(pk)
        serializer = NoticeSerializer(notice, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        notice = self.get_object(pk)
        notice.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
                