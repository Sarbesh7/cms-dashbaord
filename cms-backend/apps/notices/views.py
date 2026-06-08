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

        search = request.query_params.get('search')
        status_filter= request.query_params.get('status')
        if search:
          notices = notices.filter(title__icontains=search)
        if status_filter:
            notices = notices.filter(status=status_filter) 

        serializer = NoticeSerializer(notices, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer =NoticeSerializer(data=request.data)
        if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
class NoticeDetailView(APIView):
    def get_object(self, slug):
        try:
            return Notice.objects.get(slug=slug)
        
        
        except Notice.DoesNotExist:
            raise Http404

    def get(self, request, slug):
        notice = self.get_object(slug)
        serializer = NoticeSerializer(notice)
        return Response(serializer.data)

    def put(self, request, slug):
        notice = self.get_object(slug)
        serializer = NoticeSerializer(notice, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request,slug):
        notice = self.get_object(slug)
        notice.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
                