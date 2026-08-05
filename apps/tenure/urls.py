from django.urls import path
from .views import (
    TenureListView, 
    TenureDetailView, 
    MemberListView, 
    MemberDetailView, 
    clone_members,
    TenureMembershipListView,
    TenureMembershipDetailView,
    AlumniListView,
    AlumniDetailView
)

urlpatterns = [
    # Tenure Endpoints
    path('api/v1/tenures/', TenureListView.as_view(), name='tenure-list'),
    path('api/v1/tenures/<slug:slug>/', TenureDetailView.as_view(), name='tenure-detail'),
    
    # Member Endpoints
    path('api/v1/members/', MemberListView.as_view(), name='member-list'),
    path('api/v1/members/<slug:slug>/', MemberDetailView.as_view(), name='member-detail'),
    
    # Utility / Action Endpoints
    path('api/v1/clone-members/<slug:slug>/', clone_members, name='clone-members'),

    # Tenure Membership Management
    path('api/v1/memberships/', TenureMembershipListView.as_view(), name='membership-list'),
    path('api/v1/memberships/<int:pk>/', TenureMembershipDetailView.as_view(), name='membership-detail'),

    # Alumni Management
    path('api/v1/alumni/', AlumniListView.as_view(), name='alumni-list'),
    path('api/v1/alumni/<int:pk>/', AlumniDetailView.as_view(), name='alumni-detail'),
]