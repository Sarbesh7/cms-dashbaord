from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 40
    page_size_query_params= "page_size"
    max_page_size = 100
    