from django.urls import path
from .views import BlogListCreateView, BlogDetailView, BlogImageUploadView, BlogImageDeleteView

app_name = 'blogs'

urlpatterns = [
    path('api/v1/blogs/', BlogListCreateView.as_view(), name='blog-list-create'),
    path('api/v1/blogs/upload-image/', BlogImageUploadView.as_view(), name='blog-upload-image'),
    path('api/v1/blogs/delete-image/', BlogImageDeleteView.as_view(), name='blog-delete-image'),
    path('api/v1/blogs/<str:pk>/', BlogDetailView.as_view(), name='blog-detail'),
]
