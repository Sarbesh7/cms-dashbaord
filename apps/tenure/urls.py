from django.urls import path
from .views import TenureListView, TenureDetailView, MemberListView , MemberDetailView , clone_members


urlpatterns = [
    path('api/tenures/', TenureListView.as_view()),
    path('api/tenures/<int:pk>/', TenureDetailView.as_view()),
    
    path('api/members/', MemberListView.as_view()),
    path('api/members/<int:pk>/', MemberDetailView.as_view()),
    
    path('api/clone-members/<slug:slug>/', clone_members, name='clone-members'),
]