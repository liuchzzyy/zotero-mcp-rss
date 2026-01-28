"""
Gmail Client for Zotero MCP.

Provides OAuth2 authentication and email operations for Gmail API.
Supports searching, reading, and deleting emails.
"""

import asyncio
import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Gmail API scopes - we need modify to trash/delete emails
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Default paths for credentials
DEFAULT_CREDENTIALS_PATH = (
    Path.home() / ".config" / "zotero-mcp" / "gmail_credentials.json"
)
DEFAULT_TOKEN_PATH = Path.home() / ".config" / "zotero-mcp" / "gmail_token.json"


class GmailClient:
    """
    Gmail API client with OAuth2 authentication.

    Handles authentication, email search, content reading, and deletion.

    For GitHub Actions / headless environments:
    - Set GMAIL_TOKEN_JSON env var with the token.json content
    - The client will use this instead of requiring interactive auth
    """

    def __init__(
        self,
        credentials_path: str | Path | None = None,
        token_path: str | Path | None = None,
    ):
        """
        Initialize Gmail client.

        Args:
            credentials_path: Path to OAuth2 credentials JSON (from Google Cloud Console)
            token_path: Path to store/load OAuth2 token
        """
        self.credentials_path = Path(
            credentials_path
            or os.getenv("GMAIL_CREDENTIALS_PATH")
            or DEFAULT_CREDENTIALS_PATH
        )
        self.token_path = Path(
            token_path or os.getenv("GMAIL_TOKEN_PATH") or DEFAULT_TOKEN_PATH
        )
        self._service: Any = None
        self._credentials: Credentials | None = None

    def _get_credentials(self) -> Credentials:
        """
        Get or refresh OAuth2 credentials.

        Priority:
        1. GMAIL_TOKEN_JSON env var (for CI/CD, contains full token JSON)
        2. Token file at token_path
        3. Interactive OAuth flow (requires browser)
        """
        creds = None

        # Priority 1: Load from environment variable (for GitHub Actions)
        token_json_env = os.getenv("GMAIL_TOKEN_JSON")
        if token_json_env:
            try:
                token_data = json.loads(token_json_env)
                creds = Credentials.from_authorized_user_info(token_data, SCOPES)
                logger.info("Loaded Gmail credentials from GMAIL_TOKEN_JSON env var")
            except Exception as e:
                logger.warning(f"Failed to load token from env var: {e}")

        # Priority 2: Load from token file
        if not creds and self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(self.token_path), SCOPES
                )
                logger.info(f"Loaded Gmail credentials from {self.token_path}")
            except Exception as e:
                logger.warning(f"Failed to load token from file: {e}")

        # Refresh if expired
        if creds and not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Refreshed Gmail credentials")

                    # Save refreshed token back to file (if not using env var)
                    if not token_json_env:
                        self._save_token(creds)
                except Exception as e:
                    logger.warning(f"Failed to refresh token: {e}")
                    creds = None

        # Priority 3: Interactive OAuth flow
        if not creds or not creds.valid:
            if not self.credentials_path.exists():
                raise FileNotFoundError(
                    f"Gmail credentials not found at {self.credentials_path}. "
                    "Download OAuth2 credentials from Google Cloud Console. "
                    "Or set GMAIL_TOKEN_JSON env var with pre-authorized token."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
            self._save_token(creds)

        return creds

    def _save_token(self, creds: Credentials) -> None:
        """Save token to file for future use."""
        try:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, "w") as token_file:
                token_file.write(creds.to_json())
            logger.info(f"Saved Gmail token to {self.token_path}")
        except Exception as e:
            logger.warning(f"Failed to save token: {e}")

    @property
    def service(self) -> Any:
        """Get Gmail API service (lazy initialization)."""
        if self._service is None:
            self._credentials = self._get_credentials()
            self._service = build("gmail", "v1", credentials=self._credentials)
            logger.info("Gmail API service initialized")
        return self._service

    async def search_messages(
        self,
        sender: str | None = None,
        subject: str | None = None,
        query: str | None = None,
        max_results: int = 100,
    ) -> list[dict[str, str]]:
        """
        Search for emails matching criteria.

        Args:
            sender: Filter by sender email address
            subject: Filter by subject (partial match)
            query: Raw Gmail search query (overrides sender/subject)
            max_results: Maximum number of results to return

        Returns:
            List of dicts with 'id' and 'threadId' for each matching message
        """
        # Build query
        if query:
            q = query
        else:
            parts = []
            if sender:
                parts.append(f"from:{sender}")
            if subject:
                parts.append(f"subject:({subject})")
            q = " ".join(parts)

        if not q:
            logger.warning("No search criteria provided")
            return []

        logger.info(f"Searching Gmail with query: {q}")

        try:
            # Run in thread to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.service.users()
                .messages()
                .list(
                    userId="me",
                    q=q,
                    maxResults=max_results,
                )
                .execute(),
            )

            messages = result.get("messages", [])
            logger.info(f"Found {len(messages)} matching emails")
            return messages

        except HttpError as e:
            logger.error(f"Gmail API error: {e}")
            raise

    async def get_message(self, message_id: str) -> dict[str, Any]:
        """
        Get full message content by ID.

        Args:
            message_id: Gmail message ID

        Returns:
            Full message data including payload, headers, etc.
        """
        try:
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self.service.users()
                .messages()
                .get(
                    userId="me",
                    id=message_id,
                    format="full",
                )
                .execute(),
            )
            return message

        except HttpError as e:
            logger.error(f"Failed to get message {message_id}: {e}")
            raise

    async def get_message_body(self, message_id: str) -> tuple[str, str]:
        """
        Get message body content (HTML and plain text).

        Args:
            message_id: Gmail message ID

        Returns:
            Tuple of (html_body, plain_text_body)
        """
        message = await self.get_message(message_id)
        payload = message.get("payload", {})

        html_body = ""
        text_body = ""

        def extract_parts(part: dict[str, Any]) -> None:
            nonlocal html_body, text_body

            mime_type = part.get("mimeType", "")
            body_data = part.get("body", {}).get("data", "")

            if body_data:
                decoded = base64.urlsafe_b64decode(body_data).decode(
                    "utf-8", errors="ignore"
                )
                if mime_type == "text/html":
                    html_body = decoded
                elif mime_type == "text/plain":
                    text_body = decoded

            # Recursively process nested parts
            for sub_part in part.get("parts", []):
                extract_parts(sub_part)

        # Check if body is directly in payload
        if payload.get("body", {}).get("data"):
            decoded = base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                "utf-8", errors="ignore"
            )

            if payload.get("mimeType") == "text/html":
                html_body = decoded
            else:
                text_body = decoded
        else:
            # Extract from parts
            for part in payload.get("parts", []):
                extract_parts(part)

        return html_body, text_body

    async def get_message_headers(self, message_id: str) -> dict[str, str]:
        """
        Get message headers as a dict.

        Args:
            message_id: Gmail message ID

        Returns:
            Dict of header name -> value
        """
        message = await self.get_message(message_id)
        headers = message.get("payload", {}).get("headers", [])
        return {h["name"]: h["value"] for h in headers}

    async def trash_message(self, message_id: str) -> bool:
        """
        Move message to trash (recoverable).

        Args:
            message_id: Gmail message ID

        Returns:
            True if successful
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.service.users()
                .messages()
                .trash(
                    userId="me",
                    id=message_id,
                )
                .execute(),
            )
            logger.info(f"Trashed message: {message_id}")
            return True

        except HttpError as e:
            logger.error(f"Failed to trash message {message_id}: {e}")
            return False

    async def delete_message(self, message_id: str) -> bool:
        """
        Permanently delete message (not recoverable).

        Args:
            message_id: Gmail message ID

        Returns:
            True if successful
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.service.users()
                .messages()
                .delete(
                    userId="me",
                    id=message_id,
                )
                .execute(),
            )
            logger.info(f"Deleted message: {message_id}")
            return True

        except HttpError as e:
            logger.error(f"Failed to delete message {message_id}: {e}")
            return False

    async def batch_trash_messages(self, message_ids: list[str]) -> int:
        """
        Trash multiple messages.

        Args:
            message_ids: List of message IDs to trash

        Returns:
            Number of successfully trashed messages
        """
        success_count = 0
        for msg_id in message_ids:
            if await self.trash_message(msg_id):
                success_count += 1
            await asyncio.sleep(0.1)  # Rate limiting

        logger.info(f"Trashed {success_count}/{len(message_ids)} messages")
        return success_count
