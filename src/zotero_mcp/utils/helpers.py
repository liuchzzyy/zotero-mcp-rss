"""
Common helper functions for Zotero MCP.
"""

import os
import re

# Precompiled regex for HTML tag removal
_HTML_TAG_PATTERN = re.compile(r"<.*?>")


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
