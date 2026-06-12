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
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TenureDetailView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_classes = [IsAuthenticatedOrReadOnly]

    @method_decorator(cache_page(60 * 5), name='dispatch')
    def get_object(self, slug):
        try:
            return Tenure.objects.get(slug=slug)
        except Tenure.DoesNotExist:
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
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, slug):
        tenure = self.get_object(slug)
        tenure.delete()
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
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MemberDetailView(APIView):
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_classes = [IsAuthenticatedOrReadOnly]

    @method_decorator(cache_page(60 * 5), name='dispatch')
    def get_object(self, slug):
        try:
            return Member.objects.select_related('tenure').get(slug=slug)
        except Member.DoesNotExist:
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
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, slug):
        member = self.get_object(slug)
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



# cloning members from one tenure to another


@method_decorator(cache_page(60 * 5), name='dispatch')
@api_view(["POST"])
@permission_classes([IsCMSUser])
def clone_members(request, slug):

    target_tenure = get_object_or_404(Tenure, slug=slug)
    source_tenure_slug = request.data.get("source_tenure_slug")

    if not source_tenure_slug:
        return Response({"error": "source_tenure_slug is required"}, status=400)

    source_tenure = get_object_or_404(Tenure, slug=source_tenure_slug)
    members = Member.objects.filter(tenure=source_tenure)

    new_members = []

    for member in members:
        base_slug = slugify(f"{member.name}-{target_tenure.name}")
        slug = base_slug
        counter = 1
        
        while Member.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
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
                slug=slug,
            )
        )
    Member.objects.bulk_create(new_members)
    
    return Response(
        {"message": "Members cloned successfully"}, status=status.HTTP_200_OK
    )