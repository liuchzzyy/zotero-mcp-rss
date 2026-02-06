"""
Pydantic models for zotero-core.

Provides data models for Zotero items, collections, tags, and search operations.
"""

from zotero_core.models.base import (
    BaseInput,
    BaseResponse,
    PaginatedInput,
    PaginatedResponse,
    PaginationParams,
    ResponseFormat,
)
from zotero_core.models.collection import (
    Collection,
    CollectionCreate,
    CollectionUpdate,
)
from zotero_core.models.item import (
    Creator,
    Item,
    ItemCreate,
    ItemUpdate,
)
from zotero_core.models.search import (
    AdvancedSearchCondition,
    AdvancedSearchInput,
    HybridSearchInput,
    SearchByTagInput,
    SearchItemsInput,
    SearchMode,
    SearchResultItem,
    SearchResults,
    SemanticSearchInput,
)
from zotero_core.models.tag import Tag, TagCreate, TagUpdate

__all__ = [
    # Base models
    "BaseInput",
    "BaseResponse",
    "PaginatedInput",
    "PaginatedResponse",
    "PaginationParams",
    "ResponseFormat",
    # Item models
    "Item",
    "ItemCreate",
    "ItemUpdate",
    "Creator",
    # Collection models
    "Collection",
    "CollectionCreate",
    "CollectionUpdate",
    # Tag models
    "Tag",
    "TagCreate",
    "TagUpdate",
    # Search models
    "SearchMode",
    "SearchItemsInput",
    "SearchByTagInput",
    "AdvancedSearchInput",
    "AdvancedSearchCondition",
    "SemanticSearchInput",
    "HybridSearchInput",
    "SearchResultItem",
    "SearchResults",
]
