from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Certificate, CertificateTemplate
from .serializers import CertificateSerializer, CertificateTemplateSerializer
from django.http import Http404
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser 
from apps.core.permission import IsAdmin,IsCMSUser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly

class CertificateTemplateListView(APIView):
    permission_classes = [IsCMSUser]
    parser_classes=(JSONParser, MultiPartParser, FormParser)
    def get(self, request):
        templates = CertificateTemplate.objects.all()
        serializer = CertificateTemplateSerializer(templates, many=True)
        return Response(serializer.data)
    def post(self, request):
        serializer = CertificateTemplateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CertificateTemplateDetailView(APIView):
    permission_classes =[IsCMSUser]
    parser_classes=(JSONParser, MultiPartParser, FormParser)
    def get_object(self, pk):
        try:
            return CertificateTemplate.objects.get(pk=pk)
        except CertificateTemplate.DoesNotExist:
            raise Http404
    def get(self, request, pk):
        template = self.get_object(pk)
        serializer = CertificateTemplateSerializer(template)
        return Response(serializer.data)
    def put(self, request, pk):
        template=self.get_object(pk)
        serializer = CertificateTemplateSerializer(template, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        template =self.get_object(pk)
        template.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



class CertificateListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    def get(self, request):
        certificates = Certificate.objects.select_related('event').all()
        serializer = CertificateSerializer(certificates, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = CertificateSerializer(data=request.data)
        if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class CertificateDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    def get_object(self,certificate_id):
        try:
            return Certificate.objects.select_related('event').get(certificate_id=certificate_id)
        except Certificate.DoesNotExist:
            raise Http404
        
    def get(self, request, certificate_id):
        certificate = self.get_object(certificate_id)
        serializer = CertificateSerializer(certificate)
        return Response(serializer.data)
    
    def put (self,request,certificate_id):
        certificate = self.get_object(certificate_id)
        serializer =CertificateSerializer(certificate,data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, certificate_id):
        certificate = self.get_object(certificate_id)
        certificate.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)