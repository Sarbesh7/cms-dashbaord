import logging
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Certificate, CertificateTemplate
from .serializers import CertificateSerializer, CertificateTemplateSerializer, BulkStatusSerializer
from django.http import Http404
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser 
from apps.core.permission import IsAdmin, IsCMSUser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from apps.core.pagination import StandardPagination
# import logging

# logger = logging.getLogger(certificate)


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
            from django.db.models import Q 
            logger.info(f"Certificate search triggered with query: '{search_query}'")
            certificates = certificates.filter(
                Q(event__title__icontains=search_query) | 
                Q(full_name__icontains=search_query)
            )  
            
        ordering = request.query_params.get('ordering')
        if ordering:
            is_desc = ordering.startswith('-')
            field = ordering.lstrip('-')
            # map frontend field to backend field if necessary
            mapping = {
                'id': 'certificate_id',
                'event': 'event__title',
                'fullName': 'full_name',
                'createdAt': 'issued_at'
            }
            db_field = mapping.get(field, field)
            if is_desc:
                db_field = f'-{db_field}'
            try:
                certificates = certificates.order_by(db_field)
            except Exception:
                certificates = certificates.order_by('-issued_at')
        else:
            certificates = certificates.order_by('-issued_at')

        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(certificates, request)

        serializer = CertificateSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)    
    
    def post(self, request):
        serializer = CertificateSerializer(data=request.data)
        if serializer.is_valid():
            certificate = serializer.save()
            logger.info(f"Certificate '{certificate.id}' successfully issued for event by user: {request.user}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        logger.warning(f"Failed certificate generation attempt. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        """Bulk-update is_project_completed for multiple certificates.
        
        Expects: { "ids": [1, 2, 3], "is_project_completed": true }
        """
        if not (request.user and request.user.is_authenticated and
                request.user.role in ('admin', 'cms_user')):
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BulkStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        ids = serializer.validated_data['ids']
        is_project_completed = serializer.validated_data['is_project_completed']

        queryset = Certificate.objects.filter(certificate_id__in=ids)
        found_ids = list(queryset.values_list('certificate_id', flat=True))
        # Convert UUIDs to string for JSON serialization
        found_ids_str = [str(i) for i in found_ids]
        missing_ids = [str(i) for i in ids if i not in found_ids]

        updated_count = queryset.update(is_project_completed=is_project_completed)

        logger.info(
            f"Bulk status update: user '{request.user}' set is_project_completed={is_project_completed} "
            f"on {updated_count} certificate(s). IDs: {found_ids_str}"
        )

        response_data = {
            'updated': updated_count,
            'is_project_completed': is_project_completed,
        }
        if missing_ids:
            response_data['missing_ids'] = missing_ids

        return Response(response_data, status=status.HTTP_200_OK)
    

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
        
        if not IsAdmin().has_permission(request, self) and not (request.user.is_authenticated and request.user.is_staff):
            return Response(
            {"detail": "You do not have permission to perform this action."},
            status=status.HTTP_403_FORBIDDEN
        )
            
        certificate = self.get_object(certificate_id)
        certificate.delete()
        logger.info(f"Certificate '{certificate_id}' deleted by user: {request.user}")
        return Response(status=status.HTTP_204_NO_CONTENT)