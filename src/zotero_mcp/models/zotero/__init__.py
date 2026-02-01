"""Zotero item and annotation input models."""

from .annotations import CreateNoteInput, GetAnnotationsInput, GetNotesInput, SearchNotesInput
from .collections import (
    CreateCollectionInput,
    CreateCollectionResponse,
    DeleteCollectionInput,
    MoveCollectionInput,
    RenameCollectionInput,
)
from .items import (
    GetBundleInput,
    GetChildrenInput,
    GetCollectionsInput,
    GetFulltextInput,
    GetMetadataInput,
)
from .note_structure import (
    AnyBlock,
    BulletListBlock,
    Citation,
    CodeBlock,
    ContentBlock,
    HeadingBlock,
    HorizontalRuleBlock,
    ListItemWithCitation,
    NumberedListBlock,
    ParagraphBlock,
    QuoteBlock,
    StructuredAnalysisResponse,
    StructuredNote,
    TableBlock,
)

__all__ = [
    # Items
    "GetMetadataInput",
    "GetFulltextInput",
    "GetChildrenInput",
    "GetCollectionsInput",
    "GetBundleInput",
    # Collections
    "CreateCollectionInput",
    "CreateCollectionResponse",
    "DeleteCollectionInput",
    "MoveCollectionInput",
    "RenameCollectionInput",
    # Annotations
    "GetAnnotationsInput",
    "GetNotesInput",
    "SearchNotesInput",
    "CreateNoteInput",
    # Notes
    "StructuredNote",
    "StructuredAnalysisResponse",
    "AnyBlock",
    "ContentBlock",
    "HeadingBlock",
    "ParagraphBlock",
    "BulletListBlock",
    "NumberedListBlock",
    "QuoteBlock",
    "CodeBlock",
    "TableBlock",
    "HorizontalRuleBlock",
    "Citation",
    "ListItemWithCitation",
]
