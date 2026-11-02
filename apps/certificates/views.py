import logging
import uuid

from django.db.models import Q
from django.http import Http404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.core.activity_logging import diff_snapshots, log_activity, model_snapshot
from apps.core.ordering import apply_ordering
from apps.core.pagination import StandardPagination
from apps.core.permissions import HasModulePermission
from .models import Certificate, CertificateTemplate
from .serializers import (
    BulkStatusSerializer, CertificateSerializer, CertificateTemplateSerializer, CertificateVerificationSerializer,
)

logger = logging.getLogger('certificate')

CERTIFICATE_ORDERING = {
    'id': 'certificate_id', 'event': 'event__title', 'fullName': 'full_name', 'full_name': 'full_name',
    'createdAt': 'issued_at', 'issued_at': 'issued_at',
}


class CertificateTemplateListView(APIView):
    permission_module = "certificates"
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated, HasModulePermission("certificates", "manage_templates")]

    def get(self, request):
        return Response(CertificateTemplateSerializer(CertificateTemplate.objects.all(), many=True).data)

    def post(self, request):
        serializer = CertificateTemplateSerializer(data=request.data)
        if serializer.is_valid():
            template = serializer.save()
            logger.info(f"Certificate template '{template.id}' created by user id {request.user.pk}")
            log_activity(request, action="create", module="certificates", target_id=template.id,
                         target_repr=template.template_name, description="Created certificate template",
                         details={"kind": "template"})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.warning(f"Failed certificate template creation attempt. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CertificateTemplateDetailView(APIView):
    permission_module = "certificates"
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated, HasModulePermission("certificates", "manage_templates")]

    def get_object(self, pk):
        try:
            return CertificateTemplate.objects.get(pk=pk)
        except CertificateTemplate.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        return Response(CertificateTemplateSerializer(self.get_object(pk)).data)

    def put(self, request, pk):
        template = self.get_object(pk)
        before = model_snapshot(template)
        serializer = CertificateTemplateSerializer(template, data=request.data)
        if serializer.is_valid():
            template = serializer.save()
            log_activity(request, action="update", module="certificates", target_id=template.id,
                         target_repr=template.template_name, description="Updated certificate template",
                         changes=diff_snapshots(before, model_snapshot(template)), details={"kind": "template"})
            return Response(serializer.data)
        logger.warning(f"Failed update attempt for template '{pk}'. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        template = self.get_object(pk)
        name = template.template_name
        template.delete()
        log_activity(request, action="delete", module="certificates", target_id=pk, target_repr=name,
                     description="Deleted certificate template", details={"kind": "template"})
        return Response(status=status.HTTP_204_NO_CONTENT)


class CertificateListView(APIView):
    """Dashboard certificate management. There is no public listing."""
    permission_module = "certificates"
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated, HasModulePermission("certificates")]

    def get(self, request):
        certificates = Certificate.objects.select_related('event').all()
        search_query = request.query_params.get('search', None)
        if search_query:
            certificates = certificates.filter(
                Q(event__title__icontains=search_query) | Q(event_title__icontains=search_query)
                | Q(full_name__icontains=search_query)
            )
        certificates = apply_ordering(certificates, request.query_params.get('ordering'),
                                      CERTIFICATE_ORDERING, '-issued_at')
        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(certificates, request)
        return paginator.get_paginated_response(CertificateSerializer(result_page, many=True).data)

    def post(self, request):
        serializer = CertificateSerializer(data=request.data)
        if serializer.is_valid():
            certificate = serializer.save()
            logger.info(f"Certificate '{certificate.id}' issued by user id {request.user.pk}")
            log_activity(request, action="create", module="certificates", target_id=certificate.certificate_id,
                         target_repr=certificate.full_name,
                         description=f"Issued certificate to {certificate.full_name}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.warning(f"Failed certificate generation attempt. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        """Bulk-update is_project_completed. Expects {"ids": [uuid, ...], "is_project_completed": bool}."""
        serializer = BulkStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        ids = serializer.validated_data['ids']
        is_project_completed = serializer.validated_data['is_project_completed']
        queryset = Certificate.objects.filter(certificate_id__in=ids)
        found_ids = list(queryset.values_list('certificate_id', flat=True))
        missing_ids = [str(i) for i in ids if i not in found_ids]
        updated_count = queryset.update(is_project_completed=is_project_completed)

        log_activity(request, action="update", module="certificates", target_repr=f"{updated_count} certificate(s)",
                     description=f"Bulk set project completion to {is_project_completed}",
                     details={"certificate_ids": [str(i) for i in found_ids][:100]})
        response_data = {'updated': updated_count, 'is_project_completed': is_project_completed}
        if missing_ids:
            response_data['missing_ids'] = missing_ids
        return Response(response_data, status=status.HTTP_200_OK)


class CertificateDetailView(APIView):
    permission_module = "certificates"
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated, HasModulePermission("certificates")]

    def get_object(self, certificate_id):
        try:
            return Certificate.objects.select_related('event').get(certificate_id=certificate_id)
        except Certificate.DoesNotExist:
            raise Http404

    def get(self, request, certificate_id):
        return Response(CertificateSerializer(self.get_object(certificate_id)).data)

    def put(self, request, certificate_id):
        certificate = self.get_object(certificate_id)
        before = model_snapshot(certificate)
        serializer = CertificateSerializer(certificate, data=request.data)
        if serializer.is_valid():
            certificate = serializer.save()
            log_activity(request, action="update", module="certificates", target_id=certificate.certificate_id,
                         target_repr=certificate.full_name, description=f"Updated certificate of {certificate.full_name}",
                         changes=diff_snapshots(before, model_snapshot(certificate)))
            return Response(serializer.data)
        logger.warning(f"Failed update attempt for certificate '{certificate_id}'. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, certificate_id):
        certificate = self.get_object(certificate_id)
        name = certificate.full_name
        certificate.delete()
        log_activity(request, action="delete", module="certificates", target_id=certificate_id, target_repr=name,
                     description=f"Deleted certificate of {name}")
        return Response(status=status.HTTP_204_NO_CONTENT)


class CertificateVerifyThrottle(SimpleRateThrottle):
    """Per-client-IP limit (the endpoint is unauthenticated)."""
    scope = 'certificate_verify'

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class CertificateVerifyView(APIView):
    """
    Public verification of ONE certificate by its exact UUID.
    Returns only the details needed to confirm authenticity; never lists or searches.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [CertificateVerifyThrottle]

    def get(self, request, certificate_id):
        try:
            parsed = uuid.UUID(str(certificate_id).strip())
        except (ValueError, AttributeError):
            return Response({"valid": False, "detail": "Enter a valid certificate ID."},
                            status=status.HTTP_400_BAD_REQUEST)

        certificate = Certificate.objects.select_related('event').filter(certificate_id=parsed).first()
        if certificate is None:
            return Response({"valid": False, "detail": "No certificate exists with this ID."},
                            status=status.HTTP_404_NOT_FOUND)

        log_activity(request, action="verify", module="certificates", target_id=certificate.certificate_id,
                     target_repr=certificate.full_name, description="Certificate verified on the public website")
        response = Response({"valid": True, "certificate": CertificateVerificationSerializer(certificate).data})
        response["Cache-Control"] = "no-store"
        return response
