"""Enum definitions for tool names and constants."""

from enum import StrEnum


class ToolName(StrEnum):
    """Canonical tool names for Zotero MCP."""

    # Search & Discovery
    SEARCH = "zotero_search"
    SEARCH_BY_TAG = "zotero_search_by_tag"
    ADVANCED_SEARCH = "zotero_advanced_search"
    SEMANTIC_SEARCH = "zotero_semantic_search"
    GET_RECENT = "zotero_get_recent"

    # Content Access
    GET_METADATA = "zotero_get_metadata"
    GET_FULLTEXT = "zotero_get_fulltext"
    GET_CHILDREN = "zotero_get_children"
    GET_COLLECTIONS = "zotero_get_collections"
    GET_BUNDLE = "zotero_get_bundle"
    # Collections & Tags
    CREATE_COLLECTION = "zotero_create_collection"
    DELETE_COLLECTION = "zotero_delete_collection"
    MOVE_COLLECTION = "zotero_move_collection"
    RENAME_COLLECTION = "zotero_rename_collection"

    # Database
    UPDATE_DATABASE = "zotero_update_database"
    DATABASE_STATUS = "zotero_database_status"

    # Batch
    BATCH_GET_METADATA = "zotero_batch_get_metadata"

    # Annotations & Notes
    GET_ANNOTATIONS = "zotero_get_annotations"
    GET_NOTES = "zotero_get_notes"
    SEARCH_NOTES = "zotero_search_notes"
    CREATE_NOTE = "zotero_create_note"

    # Workflow
    PREPARE_ANALYSIS = "zotero_prepare_analysis"
    BATCH_ANALYZE_PDFS = "zotero_batch_analyze_pdfs"
    RESUME_WORKFLOW = "zotero_resume_workflow"
    LIST_WORKFLOWS = "zotero_list_workflows"
    FIND_COLLECTION = "zotero_find_collection"
