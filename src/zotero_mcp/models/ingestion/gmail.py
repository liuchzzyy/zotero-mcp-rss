"""
Gmail models for Zotero MCP.

Defines data structures for email processing and item extraction.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class EmailItem(BaseModel):
    """
    Represents an item extracted from an email HTML table.

    Similar to RSSItem but sourced from email content.
    """

    title: str = Field(..., description="Article/paper title")
    link: str = Field(default="", description="URL to the article")
    authors: str | None = Field(default=None, description="Author(s) of the article")
    journal: str | None = Field(default=None, description="Journal/publication name")
    pub_date: datetime | None = Field(default=None, description="Publication date")
    doi: str | None = Field(default=None, description="DOI if available")
    abstract: str | None = Field(default=None, description="Article abstract")

    # Source tracking
    source_email_id: str = Field(default="", description="Gmail message ID")
    source_subject: str = Field(default="", description="Email subject line")

    def __hash__(self) -> int:
        """Allow using EmailItem in sets for deduplication."""
        return hash((self.title, self.link, self.doi))

    def __eq__(self, other: object) -> bool:
        """Check equality based on title, link, and DOI."""
        if not isinstance(other, EmailItem):
            return False
        return (self.title, self.link, self.doi) == (other.title, other.link, other.doi)


class EmailMessage(BaseModel):
    """
    Represents a Gmail message with parsed content.
    """

    id: str = Field(..., description="Gmail message ID")
    thread_id: str = Field(default="", description="Gmail thread ID")
    subject: str = Field(default="", description="Email subject")
    sender: str = Field(default="", description="Sender email address")
    date: datetime | None = Field(default=None, description="Email date")
    html_body: str = Field(default="", description="HTML body content")
    text_body: str = Field(default="", description="Plain text body content")

    # Extracted items
    items: list[EmailItem] = Field(
        default_factory=list, description="Items extracted from email"
    )


class GmailProcessResult(BaseModel):
    """
    Result of processing Gmail messages.
    """

    emails_found: int = Field(default=0, description="Number of emails found")
    emails_processed: int = Field(
        default=0, description="Number of emails successfully processed"
    )
    items_extracted: int = Field(
        default=0, description="Total items extracted from emails"
    )
    items_filtered: int = Field(default=0, description="Items passing AI filter")
    items_imported: int = Field(
        default=0, description="Items successfully imported to Zotero"
    )
    items_duplicate: int = Field(default=0, description="Items skipped as duplicates")
    emails_deleted: int = Field(
        default=0, description="Emails deleted/trashed after processing"
    )
    errors: list[str] = Field(default_factory=list, description="Error messages")
    keywords_used: list[str] = Field(
        default_factory=list, description="Keywords used for filtering"
    )
