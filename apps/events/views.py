from django.shortcuts import render,get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Event
from .serializers import EventSerializer
from .pagination import EventPagination
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page


# Create your views here.
    
class EvenListtView(APIView):
    @method_decorator(cache_page(60 * 5), name='dispatch')
    def get(self,request):
        events = Event.objects.all()

        search = request.query_params.get("search")
        status_filter = request.query_params.get("status")

        if search:
            events = events.filter(title__icontains=search)
        if status_filter:
            events = events.filter(status=status_filter)

        paginator = EventPagination()
        result_page = paginator.paginate_queryset(events,request)    

        serializer = EventSerializer(result_page,many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self,request):
        serializer = EventSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data,status=status.HTTP_201_CREATED)
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)
    

class EventDetailsView(APIView) :
    @method_decorator(cache_page(60 * 5), name='dispatch')
    def get(self,request,slug) :
        event = get_object_or_404(Event,slug__iexact=slug)
        serializer = EventSerializer(event)
        return Response(serializer.data,status=status.HTTP_200_OK)
    

    def put(self,request,slug):
        event = get_object_or_404(Event,slug__iexact=slug)
        serializer = EventSerializer(event,data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data,status=status.HTTP_200_OK)
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self,request,slug):
        event= get_object_or_404(Event,slug__iexact=slug)
        event.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    
        

    