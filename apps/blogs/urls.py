from django.urls import path
from .views import BlogListCreateView, BlogDetailView, BlogImageUploadView

app_name = 'blogs'

urlpatterns = [
    path('api/v1/blogs/', BlogListCreateView.as_view(), name='blog-list-create'),
    path('api/v1/blogs/upload-image/', BlogImageUploadView.as_view(), name='blog-upload-image'),
    path('api/v1/blogs/<int:pk>/', BlogDetailView.as_view(), name='blog-detail'),
]
