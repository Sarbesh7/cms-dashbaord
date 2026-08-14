from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 40
    # NOTE: DRF only recognizes the SINGULAR `page_size_query_param` attribute.
    # The previous `page_size_query_params` (plural) was silently ignored by
    # DRF, so the `page_size` query param from the frontend never took effect
    # and the API always returned the default 40 items per page. Renaming to
    # the singular form allows `/notices/?page=2&page_size=5` to work.
    page_size_query_param = "page_size"
    max_page_size = 100
    