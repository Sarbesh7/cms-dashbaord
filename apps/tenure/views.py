import logging
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .models import Tenure, Member, TenureMembership, Alumni
from .serializers import (
    MemberSerializer,
    MemberProfileSerializer,
    TenureDropdownSerializer,
    DetailedTenureSerializer,
    TenureMembershipSerializer,
    AlumniSerializer,
)
from apps.core.permission import IsAdmin, IsCMSUser

logger = logging.getLogger("tenure")


class TenureListView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_classes = [IsAuthenticatedOrReadOnly]

    @method_decorator(cache_page(60 * 5), name="dispatch")
    def get(self, request):
       
        tenures = Tenure.objects.prefetch_related(
            "memberships__member", "alumni__member"
        ).all()
        serializer = DetailedTenureSerializer(tenures, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = TenureSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(
                f"Successfully created a new Tenure: {serializer.data.get('name')}"
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        logger.warning(
            f"Failed to create Tenure. Validation errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TenureDetailView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_object(self, slug):
        try:
            return Tenure.objects.prefetch_related(
                "memberships__member", "alumni__member"
            ).get(slug=slug)
        except Tenure.DoesNotExist:
            logger.error(f"Tenure with slug '{slug}' not found.")
            raise Http404

    @method_decorator(cache_page(60 * 5), name="dispatch")
    def get(self, request, slug):
        tenure = self.get_object(slug)
        serializer = DetailedTenureSerializer(tenure)
        return Response(serializer.data)

    def put(self, request, slug):
        tenure = self.get_object(slug)
        serializer = TenureSerializer(tenure, data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Successfully updated Tenure with slug '{slug}'.")
            return Response(serializer.data)

        logger.warning(
            f"Failed to update Tenure with slug '{slug}'. Validation errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, slug):
        tenure = self.get_object(slug)
        tenure_name = tenure.name
        tenure.delete()
        logger.info(f"Successfully deleted Tenure: {tenure_name} (slug: '{slug}').")
        return Response(status=status.HTTP_204_NO_CONTENT)


class MemberListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get(self, request):
        members = Member.objects.all()
        serializer = MemberSerializer(members, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = MemberSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Successfully created Member: {serializer.data.get('name')}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        logger.warning(
            f"Failed to create Member. Validation errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MemberDetailView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_object(self, slug):
        try:
            # Prefetch memberships and tenure names for complete personal profile history
            return Member.objects.prefetch_related("memberships__tenure").get(slug=slug)
        except Member.DoesNotExist:
            logger.error(f"Member with slug '{slug}' not found.")
            raise Http404

    @method_decorator(cache_page(60 * 5), name="dispatch")
    def get(self, request, slug):
        member = self.get_object(slug)
        # MemberProfileSerializer returns core profile + full historical tenure timeline
        serializer = MemberProfileSerializer(member)
        return Response(serializer.data)

    def put(self, request, slug):
        member = self.get_object(slug)
        serializer = MemberSerializer(member, data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Successfully updated Member with slug '{slug}'.")
            return Response(serializer.data)

        logger.warning(
            f"Failed to update Member with slug '{slug}'. Validation errors: {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, slug):
        member = self.get_object(slug)
        member_name = member.name
        member.delete()
        logger.info(f"Successfully deleted Member: {member_name} (slug: '{slug}').")
        return Response(status=status.HTTP_204_NO_CONTENT)


# cloning member memberships from one tenure to another


@api_view(["POST"])
@permission_classes([IsCMSUser])
def clone_members(request, slug):
    target_tenure = get_object_or_404(Tenure, slug=slug)
    source_tenure_slug = request.data.get("source_tenure_slug")

    if not source_tenure_slug:
        logger.warning(
            f"Clone members failed: Missing 'source_tenure_slug' in request data targeting tenure '{slug}'."
        )
        return Response(
            {"error": "source_tenure_slug is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    source_tenure = get_object_or_404(Tenure, slug=source_tenure_slug)
    source_memberships = TenureMembership.objects.filter(tenure=source_tenure)

    count_to_clone = source_memberships.count()
    if count_to_clone == 0:
        logger.info(
            f"Clone members execution finished: Source tenure '{source_tenure_slug}' contains no memberships to copy."
        )
        return Response(
            {"message": "No memberships found in source tenure to clone"},
            status=status.HTTP_200_OK,
        )

    new_memberships = []

    for membership in source_memberships:
        # Prevent duplicating the same member in the target tenure
        if not TenureMembership.objects.filter(
            member=membership.member, tenure=target_tenure
        ).exists():
            new_memberships.append(
                TenureMembership(
                    member=membership.member,
                    tenure=target_tenure,
                    role_type=membership.role_type,
                    designation=membership.designation,
                    order=membership.order,  # Copies hierarchy order intact
                )
            )

    try:
        TenureMembership.objects.bulk_create(new_memberships)
        logger.info(
            f"Successfully cloned {len(new_memberships)} memberships from tenure '{source_tenure_slug}' to '{slug}'."
        )
    except Exception as e:
        logger.error(
            f"Database error while executing bulk_create during cloning operation: {str(e)}"
        )
        return Response(
            {"error": "An internal error occurred during data processing."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {"message": f"{len(new_memberships)} memberships cloned successfully"},
        status=status.HTTP_200_OK,
    )


class TenureMembershipListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get(self, request):
        memberships = TenureMembership.objects.select_related("member", "tenure").all()
        serializer = TenureMembershipSerializer(memberships, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = TenureMembershipSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TenureMembershipDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_object(self, pk):
        return get_object_or_404(TenureMembership, pk=pk)

    def get(self, request, pk):
        membership = self.get_object(pk)
        serializer = TenureMembershipSerializer(membership)
        return Response(serializer.data)

    def put(self, request, pk):
        membership = self.get_object(pk)
        serializer = TenureMembershipSerializer(membership, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        membership = self.get_object(pk)
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AlumniListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get(self, request):
        alumni = (
            Alumni.objects.select_related("member").prefetch_related("tenures").all()
        )
        serializer = AlumniSerializer(alumni, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AlumniSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AlumniDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_object(self, pk):
        return get_object_or_404(Alumni, pk=pk)

    def get(self, request, pk):
        alumni = self.get_object(pk)
        serializer = AlumniSerializer(alumni)
        return Response(serializer.data)

    def put(self, request, pk):
        alumni = self.get_object(pk)
        serializer = AlumniSerializer(alumni, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        alumni = self.get_object(pk)
        alumni.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
