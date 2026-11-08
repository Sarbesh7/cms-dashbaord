import logging

from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.activity_logging import diff_snapshots, log_activity, model_snapshot
from apps.core.cache import bump_content_cache_version, versioned_cache_page
from apps.core.ordering import apply_ordering
from apps.core.pagination import StandardPagination
from apps.core.permissions import HasModulePermission
from apps.core.visibility import PUBLISHED, can_view_private
from .models import Alumni, Member, Tenure, TenureMembership
from .serializers import (
    AlumniSerializer, DetailedTenureSerializer, MemberProfileSerializer, MemberSerializer,
    TenureMembershipSerializer, TenureSerializer,
)

logger = logging.getLogger("tenure")

MEMBER_ORDERING = {"id": "id", "name": "name", "email": "email", "status": "status",
                   "createdAt": "created_at", "created_at": "created_at"}
ALUMNI_ORDERING = {"id": "id", "memberId": "member__id", "fullName": "member__name",
                   "graduationYear": "graduation_year", "createdAt": "created_at"}


class _ModuleView(APIView):
    """GET is public (published data only); writes need the module permission."""
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_module = None

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated(), HasModulePermission(self.permission_module)]

    def is_private(self, request):
        return can_view_private(request, self.permission_module)

    def ctx(self, request):
        return {"request": request, "public": not self.is_private(request)}


def _log_update(request, module, obj, before, label, noun):
    log_activity(request, action="update", module=module, target_id=obj.pk, target_repr=label,
                 description=f"Updated {noun} '{label}'", changes=diff_snapshots(before, model_snapshot(obj)))


# ---------------------------------------------------------------------------- tenures
class TenureListView(_ModuleView):
    permission_module = "tenures"

    @versioned_cache_page(60 * 5)
    def get(self, request):
        tenures = Tenure.objects.prefetch_related("memberships__member", "alumni__member").all()
        return Response(DetailedTenureSerializer(tenures, many=True, context=self.ctx(request)).data)

    def post(self, request):
        serializer = TenureSerializer(data=request.data)
        if serializer.is_valid():
            tenure = serializer.save()
            log_activity(request, action="create", module="tenures", target_id=tenure.id, target_repr=tenure.name,
                         description=f"Created tenure '{tenure.name}'")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.warning(f"Failed to create Tenure. Validation errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TenureDetailView(_ModuleView):
    permission_module = "tenures"

    def get_object(self, slug):
        try:
            qs = Tenure.objects.prefetch_related("memberships__member", "alumni__member")
            if str(slug).isdigit():
                return qs.get(id=int(slug))
            return qs.get(slug=slug)
        except Tenure.DoesNotExist:
            raise Http404

    @versioned_cache_page(60 * 5)
    def get(self, request, slug):
        return Response(DetailedTenureSerializer(self.get_object(slug), context=self.ctx(request)).data)

    def put(self, request, slug):
        tenure = self.get_object(slug)
        before = model_snapshot(tenure)
        serializer = TenureSerializer(tenure, data=request.data)
        if serializer.is_valid():
            tenure = serializer.save()
            _log_update(request, "tenures", tenure, before, tenure.name, "tenure")
            return Response(serializer.data)
        logger.warning(f"Failed to update Tenure '{slug}'. Validation errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, slug):
        tenure = self.get_object(slug)
        name, tenure_id = tenure.name, tenure.id
        tenure.delete()
        log_activity(request, action="delete", module="tenures", target_id=tenure_id, target_repr=name,
                     description=f"Deleted tenure '{name}'")
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------- members
class MemberListView(_ModuleView):
    permission_module = "members"

    def get(self, request):
        members = Member.objects.all()
        if not self.is_private(request):
            members = members.filter(status=PUBLISHED)

        status_param = request.query_params.get("status")
        if status_param and status_param.lower() in ["published", "draft"]:
            members = members.filter(status=status_param.lower())

        search = request.query_params.get("search")
        if search:
            q = Q(name__icontains=search) | Q(slug__icontains=search)
            if self.is_private(request):
                q |= Q(email__icontains=search)  # email search only where emails are visible
            members = members.filter(q)

        members = apply_ordering(members, request.query_params.get("ordering"), MEMBER_ORDERING, "-id")
        context = self.ctx(request)
        if request.query_params.get("all") in ["true", "1"] and self.is_private(request):
            return Response(MemberSerializer(members, many=True, context=context).data)

        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(members, request)
        return paginator.get_paginated_response(MemberSerializer(result_page, many=True, context=context).data)

    def post(self, request):
        serializer = MemberSerializer(data=request.data)
        if serializer.is_valid():
            member = serializer.save()
            log_activity(request, action="create", module="members", target_id=member.id, target_repr=member.name,
                         description=f"Created member '{member.name}'")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.warning(f"Failed to create Member. Validation errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MemberDetailView(_ModuleView):
    permission_module = "members"

    def get_object(self, slug, public=False):
        qs = Member.objects.prefetch_related("memberships__tenure")
        if public:
            qs = qs.filter(status=PUBLISHED)
        try:
            if str(slug).isdigit():
                return qs.get(id=int(slug))
            return qs.get(slug=slug)
        except Member.DoesNotExist:
            raise Http404

    @versioned_cache_page(60 * 5)
    def get(self, request, slug):
        member = self.get_object(slug, public=not self.is_private(request))
        return Response(MemberProfileSerializer(member, context=self.ctx(request)).data)

    def _update(self, request, slug):
        member = self.get_object(slug)
        before = model_snapshot(member)
        serializer = MemberSerializer(member, data=request.data, partial=True)
        if serializer.is_valid():
            member = serializer.save()
            _log_update(request, "members", member, before, member.name, "member")
            return Response(serializer.data)
        logger.warning(f"Failed to update Member '{slug}'. Validation errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, slug):
        return self._update(request, slug)

    def patch(self, request, slug):
        return self._update(request, slug)

    def delete(self, request, slug):
        # members.delete is a protected permission: superadmin only (HasModulePermission).
        member = self.get_object(slug)
        name, member_id = member.name, member.id
        membership_count = member.memberships.count()
        member.delete()  # memberships, alumni and blog credits are kept (SET_NULL + name snapshots)
        log_activity(request, action="delete", module="members", target_id=member_id, target_repr=name,
                     description=f"Deleted member '{name}'; historical records preserved",
                     details={"preserved_memberships": membership_count})
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------- memberships
@api_view(["POST"])
@permission_classes([IsAuthenticated, HasModulePermission("tenures", "update")])
def clone_members(request, slug):
    target_tenure = get_object_or_404(Tenure, slug=slug)
    source_tenure_slug = request.data.get("source_tenure_slug")
    if not source_tenure_slug:
        return Response({"error": "source_tenure_slug is required"}, status=status.HTTP_400_BAD_REQUEST)

    source_tenure = get_object_or_404(Tenure, slug=source_tenure_slug)
    source_memberships = (
        TenureMembership.objects.filter(tenure=source_tenure, member__isnull=False)
        .select_related("member")
    )
    if not source_memberships.exists():
        return Response({"message": "No memberships found in source tenure to clone"}, status=status.HTTP_200_OK)

    existing = set(TenureMembership.objects.filter(tenure=target_tenure).values_list("member_id", flat=True))
    new_memberships = [
        TenureMembership(
            member=m.member,
            member_name_snapshot=m.member.name,
            tenure=target_tenure,
            role_type=m.role_type,
            designation=m.designation,
            order=m.order,
        )
        for m in source_memberships
        if m.member_id not in existing
    ]
    try:
        TenureMembership.objects.bulk_create(new_memberships)
        # bulk_create sends no post_save signals, so invalidate cached reads explicitly.
        bump_content_cache_version()
    except Exception as e:
        logger.error(f"Database error while cloning memberships: {e.__class__.__name__}")
        return Response({"error": "An internal error occurred during data processing."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    log_activity(request, action="create", module="tenures", target_id=target_tenure.id,
                 target_repr=target_tenure.name,
                 description=f"Cloned {len(new_memberships)} memberships from '{source_tenure.name}'")
    return Response({"message": f"{len(new_memberships)} memberships cloned successfully"}, status=status.HTTP_200_OK)


class TenureMembershipListView(_ModuleView):
    permission_module = "tenures"

    def get(self, request):
        memberships = TenureMembership.objects.select_related("member", "tenure").all()
        if not self.is_private(request):
            memberships = memberships.filter(status=PUBLISHED, member__status=PUBLISHED)
        return Response(TenureMembershipSerializer(memberships, many=True, context=self.ctx(request)).data)

    def post(self, request):
        serializer = TenureMembershipSerializer(data=request.data)
        if serializer.is_valid():
            membership = serializer.save()
            log_activity(request, action="create", module="tenures", target_id=membership.id,
                         target_repr=str(membership), description="Added tenure membership")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TenureMembershipDetailView(_ModuleView):
    permission_module = "tenures"

    def get_object(self, pk, public=False):
        qs = TenureMembership.objects.select_related("member", "tenure")
        if public:
            qs = qs.filter(status=PUBLISHED, member__status=PUBLISHED)
        return get_object_or_404(qs, pk=pk)

    def get(self, request, pk):
        membership = self.get_object(pk, public=not self.is_private(request))
        return Response(TenureMembershipSerializer(membership, context=self.ctx(request)).data)

    def put(self, request, pk):
        membership = self.get_object(pk)
        before = model_snapshot(membership)
        serializer = TenureMembershipSerializer(membership, data=request.data)
        if serializer.is_valid():
            membership = serializer.save()
            _log_update(request, "tenures", membership, before, str(membership), "membership")
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        membership = self.get_object(pk)
        label = str(membership)
        membership.delete()
        log_activity(request, action="delete", module="tenures", target_id=pk, target_repr=label,
                     description="Removed tenure membership")
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------- alumni
class AlumniListView(_ModuleView):
    permission_module = "alumni"

    @versioned_cache_page(60 * 5)
    def get(self, request):
        alumni = Alumni.objects.select_related("member").prefetch_related("tenures").all()
        if not self.is_private(request):
            alumni = alumni.filter(member__status=PUBLISHED)

        search = request.query_params.get("search") or request.query_params.get("name")
        id_filter = request.query_params.get("id")
        if id_filter:
            if not str(id_filter).isdigit():
                return Response({"detail": "Invalid filter value."}, status=status.HTTP_400_BAD_REQUEST)
            alumni = alumni.filter(id=int(id_filter))
        if search:
            alumni = alumni.filter(Q(member__name__icontains=search) | Q(member_name_snapshot__icontains=search))

        alumni = apply_ordering(alumni, request.query_params.get("ordering"), ALUMNI_ORDERING, "-created_at")
        context = self.ctx(request)
        # Full-list mode for the dashboard, which paginates alumni in the browser.
        if request.query_params.get("all") in ["true", "1"] and self.is_private(request):
            return Response(AlumniSerializer(alumni, many=True, context=context).data)

        paginator = StandardPagination()
        result_page = paginator.paginate_queryset(alumni, request)
        return paginator.get_paginated_response(AlumniSerializer(result_page, many=True, context=context).data)

    def post(self, request):
        serializer = AlumniSerializer(data=request.data)
        if serializer.is_valid():
            alumni = serializer.save()
            log_activity(request, action="create", module="alumni", target_id=alumni.id,
                         target_repr=alumni.member_name, description=f"Added alumni '{alumni.member_name}'")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AlumniDetailView(_ModuleView):
    permission_module = "alumni"

    def get_object(self, pk, public=False):
        qs = Alumni.objects.select_related("member")
        if public:
            qs = qs.filter(member__status=PUBLISHED)
        return get_object_or_404(qs, pk=pk)

    def get(self, request, pk):
        alumni = self.get_object(pk, public=not self.is_private(request))
        return Response(AlumniSerializer(alumni, context=self.ctx(request)).data)

    def _update(self, request, pk):
        alumni = self.get_object(pk)
        before = model_snapshot(alumni)
        serializer = AlumniSerializer(alumni, data=request.data, partial=True)
        if serializer.is_valid():
            alumni = serializer.save()
            _log_update(request, "alumni", alumni, before, alumni.member_name, "alumni")
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        return self._update(request, pk)

    def patch(self, request, pk):
        return self._update(request, pk)

    def delete(self, request, pk):
        alumni = self.get_object(pk)
        label = alumni.member_name
        alumni.delete()
        log_activity(request, action="delete", module="alumni", target_id=pk, target_repr=label,
                     description=f"Removed alumni '{label}'")
        return Response(status=status.HTTP_204_NO_CONTENT)
