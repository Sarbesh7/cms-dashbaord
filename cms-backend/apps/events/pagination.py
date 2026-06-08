from rest_framework.pagination import PageNumberPagination

class EventPagination(PageNumberPagination):
    page_size = 3