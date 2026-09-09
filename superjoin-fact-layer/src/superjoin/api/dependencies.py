from functools import lru_cache
from typing import Optional
from fastapi import Query
from superjoin.application import KnowledgeLayerApplication


@lru_cache()
def get_app_service() -> KnowledgeLayerApplication:
    """Provides a cached, application-wide instance of KnowledgeLayerApplication."""
    return KnowledgeLayerApplication()


class PaginationParams:
    """Reusable dependency for handling pagination parameters."""
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number starting from 1"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)")
    ):
        self.page = page
        self.page_size = page_size
