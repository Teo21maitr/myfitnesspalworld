"""Pagination par défaut de l'API (spec 04, spec 10 §5)."""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Pagination `page` / `limit`, 25 éléments par défaut."""

    page_size = 25
    page_query_param = "page"
    page_size_query_param = "limit"
    max_page_size = 100
