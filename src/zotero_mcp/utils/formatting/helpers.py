"""
Common helper functions for Zotero MCP.
"""

import os
import re

# Precompiled regex for HTML tag removal
_HTML_TAG_PATTERN = re.compile(r"<.*?>")

# Shared DOI regex pattern used by RSS and Gmail services
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


def clean_title(title: str) -> str:
    """
    Clean article title by removing common prefixes.

    Removes prefixes like [DOI], [PDF], etc. from article titles.

    Args:
        title: The raw title string.

    Returns:
        Cleaned title string.

    Examples:
        >>> clean_title("[DOI] 10.1234/example The paper title")
        '10.1234/example The paper title'
        >>> clean_title("[PDF] Research Article")
        'Research Article'
    """
    if not title:
        return ""
    cleaned = re.sub(r"^\[.*?\]\s*", "", title)
    return cleaned.strip()


def format_creators(creators: list[dict[str, str]]) -> str:
    """
    Format creator names into a string.

    Args:
        creators: List of creator objects from Zotero.
            Each creator may have 'firstName' and 'lastName' keys,
            or a single 'name' key for organizations/single-name authors.

    Returns:
        Semicolon-separated string of creator names in "Last, First" format.
        Returns "No authors listed" if no valid creators found.

    Examples:
        >>> format_creators([{"firstName": "Albert", "lastName": "Einstein"}])
        'Einstein, Albert'
        >>> format_creators([{"name": "World Health Organization"}])
        'World Health Organization'
        >>> format_creators([])
        'No authors listed'
    """
    names = []
    for creator in creators:
        if "firstName" in creator and "lastName" in creator:
            names.append(f"{creator['lastName']}, {creator['firstName']}")
        elif "name" in creator:
            names.append(creator["name"])
    return "; ".join(names) if names else "No authors listed"


def clean_html(raw_html: str) -> str:
    """
    Remove HTML tags from a string.

    Args:
        raw_html: String containing HTML content.

    Returns:
        Cleaned string without HTML tags.

    Examples:
        >>> clean_html("<p>Hello <b>world</b></p>")
        'Hello world'
        >>> clean_html("No HTML here")
        'No HTML here'
    """
    return re.sub(_HTML_TAG_PATTERN, "", raw_html)


def is_local_mode() -> bool:
    """
    Check if Zotero MCP is running in local mode.

    Local mode is enabled when environment variable `ZOTERO_LOCAL` is set to a
    truthy value ("true", "yes", or "1", case-insensitive).

    Returns:
        True if local mode is enabled, False otherwise.
    """
    value = os.getenv("ZOTERO_LOCAL", "")
    return value.lower() in {"true", "yes", "1"}


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length, preserving word boundaries.

    Args:
        text: Text to truncate.
        max_length: Maximum length of the result (including suffix).
        suffix: Suffix to append if text is truncated.

    Returns:
        Truncated text with suffix if it exceeded max_length.
    """
    if len(text) <= max_length:
        return text

    # Find the last space before max_length - len(suffix)
    truncate_at = max_length - len(suffix)
    last_space = text.rfind(" ", 0, truncate_at)

    if last_space > 0:
        return text[:last_space] + suffix
    return text[:truncate_at] + suffix


def normalize_item_key(key: str) -> str:
    """
    Normalize a Zotero item key.

    Args:
        key: Item key, possibly with extra whitespace or mixed case.

    Returns:
        Normalized uppercase item key.

    Raises:
        ValueError: If key is empty or invalid.
    """
    key = key.strip().upper()
    if not key:
        raise ValueError("Item key cannot be empty")
    if not key.isalnum():
        raise ValueError(f"Invalid item key: {key}")
    return key


def parse_tags(tags: list[dict[str, str]]) -> list[str]:
    """
    Parse Zotero tag objects into a list of tag names.

    Args:
        tags: List of tag objects from Zotero API.

    Returns:
        List of tag name strings.
    """
    return [tag.get("tag", "") for tag in tags if tag.get("tag")]


async def check_has_pdf(data_service, item_key: str) -> bool:
    """
    Check if an item has at least one PDF attachment.

    Args:
        data_service: DataAccessService instance
        item_key: Zotero item key

    Returns:
        True if item has PDF attachment, False otherwise
    """
    try:
        children = await data_service.get_item_children(item_key)
        for child in children:
            child_data = child.get("data", {})
            if child_data.get("itemType") == "attachment":
                content_type = child_data.get("contentType", "")
                if content_type == "application/pdf":
                    return True
        return False
    except Exception:
        return False


async def check_has_notes(data_service, item_key: str) -> bool:
    """
    Check if an item has at least one note.

    Args:
        data_service: DataAccessService instance
        item_key: Zotero item key

    Returns:
        True if item has notes, False otherwise
    """
    try:
        children = await data_service.get_item_children(item_key)
        for child in children:
            child_data = child.get("data", {})
            if child_data.get("itemType") == "note":
                return True
        return False
    except Exception:
        return False


async def check_has_tag(data_service, item_key: str, tag: str) -> bool:
    """
    Check if an item has a specific tag.

    Args:
        data_service: DataAccessService instance
        item_key: Zotero item key
        tag: Tag name to check for

    Returns:
        True if item has the tag, False otherwise
    """
    try:
        item = await data_service.get_item(item_key)
        if item:
            item_data = item.get("data", {})
            item_tags = [t.get("tag", "") for t in item_data.get("tags", [])]
            return tag in item_tags
        return False
    except Exception:
        return False
