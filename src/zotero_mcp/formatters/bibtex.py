"""
BibTeX formatter for Zotero MCP responses.
"""

import re
from typing import Any

from zotero_mcp.utils.formatting.helpers import clean_html

from .base import BaseFormatter

# BibTeX type mapping from Zotero item types
ZOTERO_TO_BIBTEX_TYPE: dict[str, str] = {
    "journalArticle": "article",
    "book": "book",
    "bookSection": "incollection",
    "conferencePaper": "inproceedings",
    "thesis": "phdthesis",
    "report": "techreport",
    "patent": "misc",
    "webpage": "misc",
    "manuscript": "unpublished",
    "presentation": "misc",
    "document": "misc",
}


def _escape_bibtex(text: str) -> str:
    """Escape special characters for BibTeX."""
    if not text:
        return ""
    # Remove HTML tags first
    text = clean_html(text)
    # Escape special LaTeX characters
    replacements = [
        ("\\", "\\textbackslash{}"),
        ("&", "\\&"),
        ("%", "\\%"),
        ("$", "\\$"),
        ("#", "\\#"),
        ("_", "\\_"),
        ("{", "\\{"),
        ("}", "\\}"),
        ("~", "\\textasciitilde{}"),
        ("^", "\\textasciicircum{}"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _generate_cite_key(item: dict[str, Any]) -> str:
    """Generate a citation key for an item."""
    data = item.get("data", item)

    # Try to use first author's last name
    creators = data.get("creators", [])
    author_part = "unknown"
    for creator in creators:
        if creator.get("creatorType") == "author" or not creator.get("creatorType"):
            if "lastName" in creator:
                author_part = creator["lastName"].lower()
                break
            elif "name" in creator:
                author_part = creator["name"].split()[-1].lower()
                break

    # Get year
    date = data.get("date", "")
    year_match = re.search(r"\d{4}", date)
    year_part = year_match.group() if year_match else "nd"

    # Get first significant word from title
    title = data.get("title", "")
    title_words = re.findall(r"\b[A-Za-z]{4,}\b", title)
    title_part = title_words[0].lower() if title_words else "untitled"

    # Clean and combine
    author_part = re.sub(r"[^a-z]", "", author_part)
    title_part = re.sub(r"[^a-z]", "", title_part)

    return f"{author_part}{year_part}{title_part}"


class BibTeXFormatter(BaseFormatter):
    """Formatter for BibTeX output."""

    def format_items(
        self,
        items: list[dict[str, Any]],
        **kwargs: Any,
    ) -> str:
        """
        Format a list of Zotero items as BibTeX.

        Args:
            items: List of Zotero item data
            **kwargs: Additional options

        Returns:
            BibTeX-formatted string
        """
        entries = []
        for item in items:
            entry = self.format_item(item)
            if entry:
                entries.append(entry)

        return "\n\n".join(entries)

    def format_item(self, item: dict[str, Any], **kwargs: Any) -> str:
        """
        Format a single Zotero item as BibTeX.

        Args:
            item: Zotero item data
            **kwargs: Additional options

        Returns:
            BibTeX entry string
        """
        data = item.get("data", item)
        item_type = data.get("itemType", "misc")

        # Get BibTeX type
        bibtex_type = ZOTERO_TO_BIBTEX_TYPE.get(item_type, "misc")

        # Generate citation key
        cite_key = _generate_cite_key(item)

        # Build fields
        fields: list[tuple[str, str]] = []

        # Title
        title = data.get("title", "")
        if title:
            fields.append(("title", f"{{{_escape_bibtex(title)}}}"))

        # Authors
        creators = data.get("creators", [])
        authors = []
        editors = []
        for creator in creators:
            creator_type = creator.get("creatorType", "author")
            if "lastName" in creator and "firstName" in creator:
                name = f"{creator['lastName']}, {creator['firstName']}"
            elif "name" in creator:
                name = creator["name"]
            else:
                continue

            if creator_type == "editor":
                editors.append(name)
            else:
                authors.append(name)

        if authors:
            fields.append(("author", f"{{{' and '.join(authors)}}}"))
        if editors:
            fields.append(("editor", f"{{{' and '.join(editors)}}}"))

        # Year
        date = data.get("date", "")
        year_match = re.search(r"\d{4}", date)
        if year_match:
            fields.append(("year", year_match.group()))

        # Journal/Book title
        if item_type == "journalArticle":
            journal = data.get("publicationTitle", "")
            if journal:
                fields.append(("journal", f"{{{_escape_bibtex(journal)}}}"))
        elif item_type in ("bookSection", "conferencePaper"):
            booktitle = data.get("publicationTitle", data.get("proceedingsTitle", ""))
            if booktitle:
                fields.append(("booktitle", f"{{{_escape_bibtex(booktitle)}}}"))

        # Publisher
        publisher = data.get("publisher", "")
        if publisher:
            fields.append(("publisher", f"{{{_escape_bibtex(publisher)}}}"))

        # Volume, Issue, Pages
        volume = data.get("volume", "")
        if volume:
            fields.append(("volume", volume))

        issue = data.get("issue", "")
        if issue:
            fields.append(("number", issue))

        pages = data.get("pages", "")
        if pages:
            fields.append(("pages", pages.replace("-", "--")))

        # DOI
        doi = data.get("DOI", "")
        if doi:
            fields.append(("doi", f"{{{doi}}}"))

        # URL
        url = data.get("url", "")
        if url and not doi:
            fields.append(("url", f"{{{url}}}"))

        # ISBN/ISSN
        isbn = data.get("ISBN", "")
        if isbn:
            fields.append(("isbn", f"{{{isbn}}}"))

        issn = data.get("ISSN", "")
        if issn:
            fields.append(("issn", f"{{{issn}}}"))

        # Abstract (optional, often too long)
        abstract = data.get("abstractNote", "")
        if abstract and kwargs.get("include_abstract", False):
            fields.append(("abstract", f"{{{_escape_bibtex(abstract)}}}"))

        # Build entry
        lines = [f"@{bibtex_type}{{{cite_key},"]
        for field_name, field_value in fields:
            lines.append(f"  {field_name} = {field_value},")
        lines.append("}")

        return "\n".join(lines)

    def format_error(self, message: str, **kwargs: Any) -> str:
        """
        Format an error message (as BibTeX comment).

        Args:
            message: Error message
            **kwargs: Additional options

        Returns:
            BibTeX comment string
        """
        return f"% Error: {message}"

    def format_search_results(
        self,
        items: list[dict[str, Any]],
        query: str,
        total: int,
        **kwargs: Any,
    ) -> str:
        """
        Format search results as BibTeX.

        Args:
            items: List of matching items
            query: Search query
            total: Total number of matches
            **kwargs: Additional options

        Returns:
            BibTeX-formatted search results
        """
        header = f"% Search results for: {query}\n% Found {total} items\n\n"
        entries = self.format_items(items, **kwargs)
        return header + entries
