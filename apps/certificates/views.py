import logging
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Certificate, CertificateTemplate
from .serializers import CertificateSerializer, CertificateTemplateSerializer
from django.http import Http404
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser 
from apps.core.permission import IsAdmin, IsCMSUser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly


logger = logging.getLogger('certificate')

class CertificateTemplateListView(APIView):
    permission_classes = [IsCMSUser]
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    
    def get(self, request):
        templates = CertificateTemplate.objects.all()
        serializer = CertificateTemplateSerializer(templates, many=True)
        return Response(serializer.data)
        
    def post(self, request):
        serializer = CertificateTemplateSerializer(data=request.data)
        if serializer.is_valid():
            template = serializer.save()
            logger.info(f"Certificate template '{template.id}' created successfully by user: {request.user}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        logger.warning(f"Failed certificate template creation attempt. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CertificateTemplateDetailView(APIView):
    permission_classes = [IsCMSUser]
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    
    def get_object(self, pk):
        try:
            return CertificateTemplate.objects.get(pk=pk)
        except CertificateTemplate.DoesNotExist:
            logger.error(f"Certificate template with id {pk} not found.")
            raise Http404
            
    def get(self, request, pk):
        template = self.get_object(pk)
        serializer = CertificateTemplateSerializer(template)
        return Response(serializer.data)
        
    def put(self, request, pk):
        template = self.get_object(pk)
        serializer = CertificateTemplateSerializer(template, data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Certificate template '{pk}' updated successfully by user: {request.user}")
            return Response(serializer.data)
            
        logger.warning(f"Failed update attempt for template '{pk}'. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        template = self.get_object(pk)
        template.delete()
        logger.info(f"Certificate template '{pk}' deleted by user: {request.user}")
        return Response(status=status.HTTP_204_NO_CONTENT)


class CertificateListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    
    def get(self, request):
        certificates = Certificate.objects.select_related('event').all()
        search_query = request.query_params.get('search', None)
        if search_query: 
            logger.info(f"Certificate search triggered with query: '{search_query}'")
            certificates = certificates.filter(event__title__icontains=search_query)  
        serializer = CertificateSerializer(certificates, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = CertificateSerializer(data=request.data)
        if serializer.is_valid():
            certificate = serializer.save()
            logger.info(f"Certificate '{certificate.id}' successfully issued for event by user: {request.user}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        logger.warning(f"Failed certificate generation attempt. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class CertificateDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_object(self, certificate_id):
        try:
            return Certificate.objects.select_related('event').get(certificate_id=certificate_id)
        except Certificate.DoesNotExist:
            logger.error(f"Certificate with unique ID '{certificate_id}' fetched but not found.")
            raise Http404
        
    def get(self, request, certificate_id):
        certificate = self.get_object(certificate_id)
        serializer = CertificateSerializer(certificate)
        return Response(serializer.data)
    
    def put(self, request, certificate_id):
        certificate = self.get_object(certificate_id)
        serializer = CertificateSerializer(certificate, data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Certificate '{certificate_id}' successfully updated by user: {request.user}")
            return Response(serializer.data)
            
        logger.warning(f"Failed update attempt for certificate '{certificate_id}'. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, certificate_id):
        certificate = self.get_object(certificate_id)
        certificate.delete()
        logger.info(f"Certificate '{certificate_id}' deleted by user: {request.user}")
        return Response(status=status.HTTP_204_NO_CONTENT)