from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Tenure, Member
from .serializers import MemberSerializer, TenureSerializer
from django.http import Http404
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser 


class TenureListView(APIView):
    parser_classes=(JSONParser, MultiPartParser, FormParser)
    def get(self, request):
        tenures = Tenure.objects.all()
        serializer = TenureSerializer(tenures, many=True)
        return Response(serializer.data)
    def post(self, request):
        serializer = TenureSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class TenureDetailView(APIView):
    parser_classes=(JSONParser, MultiPartParser, FormParser)
    def get_object(self, pk):
        try:
            return Tenure.objects.get(pk=pk)
        except Tenure.DoesNotExist:
            raise Http404
    def get(self,request, pk):
        tenure = self.get_object(pk)
        serializer = TenureSerializer(tenure)
        return Response(serializer.data)
    
    def put(self, request, pk):
        tenure=self.get_object(pk)
        serializer = TenureSerializer(tenure, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    def delete(self, request, pk):
        tenure =self.get_object(pk)
        tenure.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
class MemberListView(APIView):
    parser_classes=(JSONParser, MultiPartParser, FormParser)
    def get(self, request):
        members = Member.objects.all()
        serializer = MemberSerializer(members, many=True)
        return Response(serializer.data)
    def post(self, request):
        serializer = MemberSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class MemberDetailView(APIView):
    parser_classes=(JSONParser, MultiPartParser, FormParser)
    def get_object(self, pk):
        try:
            return Member.objects.get(pk=pk)
        except Member.DoesNotExist:
            raise Http404
    def get(self,request, pk):
        member =self.get_object(pk)
        serializer =MemberSerializer(member)
        return Response(serializer.data)
    def put(self, request, pk):
        member =self.get_object(pk)
        serializer = MemberSerializer(member, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    def delete(self, request, pk):
        member =self.get_object(pk)
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    
    




#cloning members from one tenure to another
@api_view(['POST'])
def clone_members(request,slug):
    
    target_tenure = Tenure.objects.get(slug=slug)
    source_tenure_id = request.data.get('source_tenure_id')
    source_tenure = Tenure.objects.get(id=source_tenure_id)
    members=Member.objects.filter(tenure=source_tenure)
    
    new_members = [
        Member(
            tenure=target_tenure,
            name=member.name,
            role=member.role,
            email=member.email,
            phone_number=member.phone_number,
            fb_link=member.fb_link,
            linkedin_link=member.linkedin_link,
            github_link=member.github_link,
            image=member.image
        )
        for member in members
    ]
    Member.objects.bulk_create(new_members)
    return Response({'message': 'Members cloned successfully'}, status=status.HTTP_200_OK)
