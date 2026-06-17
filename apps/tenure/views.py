from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.decorators import api_view ,permission_classes
from rest_framework.response import Response
from .models import Tenure, Member
from .serializers import MemberSerializer, TenureSerializer
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django.utils.text import slugify
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework.permissions import IsAuthenticated , IsAuthenticatedOrReadOnly
from apps.core.permission import IsAdmin, IsCMSUser
import logging

logger = logging.getLogger('tenure')


class TenureListView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_classes = [IsAuthenticatedOrReadOnly] 
    
    @method_decorator(cache_page(60 * 5), name='dispatch')
    def get(self, request):
        tenures = Tenure.objects.prefetch_related('members').all()
        serializer = TenureSerializer(tenures, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = TenureSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Successfully created a new Tenure: {serializer.data.get('name')}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        logger.warning(f"Failed to create Tenure. Validation errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TenureDetailView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_classes = [IsAuthenticatedOrReadOnly]

    @method_decorator(cache_page(60 * 5), name='dispatch')
    def get_object(self, slug):
        try:
            return Tenure.objects.get(slug=slug)
        except Tenure.DoesNotExist:
            logger.error(f"Tenure with slug '{slug}' not found.")
            raise Http404

    @method_decorator(cache_page(60 * 5), name='dispatch')
    def get(self, request, slug):
        tenure = self.get_object(slug)
        serializer = TenureSerializer(tenure)
        return Response(serializer.data)

    def put(self, request, slug):
        tenure = self.get_object(slug)
        serializer = TenureSerializer(tenure, data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Successfully updated Tenure with slug '{slug}'.")
            return Response(serializer.data)
        
        logger.warning(f"Failed to update Tenure with slug '{slug}'. Validation errors: {serializer.errors}")
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
        members = Member.objects.select_related('tenure').all()
        serializer = MemberSerializer(members, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = MemberSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Successfully created Member: {serializer.data.get('name')} in Tenure ID: {serializer.data.get('tenure')}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        logger.warning(f"Failed to create Member. Validation errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MemberDetailView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_classes = [IsAuthenticatedOrReadOnly]

    @method_decorator(cache_page(60 * 5), name='dispatch')
    def get_object(self, slug):
        try:
            return Member.objects.select_related('tenure').get(slug=slug)
        except Member.DoesNotExist:
            logger.error(f"Member with slug '{slug}' not found.")
            raise Http404
        
    @method_decorator(cache_page(60 * 5), name='dispatch')
    def get(self, request, slug):
        member = self.get_object(slug)
        serializer = MemberSerializer(member)
        return Response(serializer.data)

    def put(self, request, slug):
        member = self.get_object(slug)
        serializer = MemberSerializer(member, data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Successfully updated Member with slug '{slug}'.")
            return Response(serializer.data)
        
        logger.warning(f"Failed to update Member with slug '{slug}'. Validation errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, slug):
        member = self.get_object(slug)
        member_name = member.name
        member.delete()
        logger.info(f"Successfully deleted Member: {member_name} (slug: '{slug}').")
        return Response(status=status.HTTP_204_NO_CONTENT)


# cloning members from one tenure to another

@method_decorator(cache_page(60 * 5), name='dispatch')
@api_view(["POST"])
@permission_classes([IsCMSUser])
def clone_members(request, slug):
    target_tenure = get_object_or_404(Tenure, slug=slug)
    source_tenure_slug = request.data.get("source_tenure_slug")

    if not source_tenure_slug:
        logger.warning(f"Clone members failed: Missing 'source_tenure_slug' in request data targeting tenure '{slug}'.")
        return Response({"error": "source_tenure_slug is required"}, status=400)

    source_tenure = get_object_or_404(Tenure, slug=source_tenure_slug)
    members = Member.objects.filter(tenure=source_tenure)
    
    count_to_clone = members.count()
    if count_to_clone == 0:
        logger.info(f"Clone members execution finished: Source tenure '{source_tenure_slug}' contains no members to copy.")
        return Response({"message": "No members found in source tenure to clone"}, status=status.HTTP_200_OK)

    new_members = []

    for member in members:
        base_slug = slugify(f"{member.name}-{target_tenure.name}")
        slug_str = base_slug
        counter = 1
        
        while Member.objects.filter(slug=slug_str).exists():
            slug_str = f"{base_slug}-{counter}"
            counter += 1

        new_members.append(
            Member(
                tenure=target_tenure,
                name=member.name,
                role=member.role,
                email=member.email,
                phone_number=member.phone_number,
                fb_link=member.fb_link,
                linkedin_link=member.linkedin_link,
                github_link=member.github_link,
                image=member.image,
                slug=slug_str,
            )
        )
        
    try:
        Member.objects.bulk_create(new_members)
        logger.info(f"Successfully cloned {count_to_clone} members from tenure '{source_tenure_slug}' to '{slug}'.")
    except Exception as e:
        logger.error(f"Database error while executing bulk_create during cloning operation: {str(e)}")
        return Response({"error": "An internal error occurred during data processing."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(
        {"message": "Members cloned successfully"}, status=status.HTTP_200_OK
    )