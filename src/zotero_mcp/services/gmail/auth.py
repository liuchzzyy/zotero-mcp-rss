import json
import logging
import os
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def get_gmail_credentials() -> Credentials | None:
    """
    Get Gmail credentials from environment variables or file.

    Priority:
    1. GMAIL_TOKEN_JSON env var (Full token info)
    2. GMAIL_CREDENTIALS_JSON env var (Client config for auth flow)
    """
    creds = None

    # 1. Try to load from Token JSON (Environment Variable)
    token_json = os.getenv("GMAIL_TOKEN_JSON")
    if token_json:
        try:
            # Handle case where it might be wrapped in single quotes in .env
            if token_json.startswith("'") and token_json.endswith("'"):
                token_json = token_json[1:-1]

            info = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(info, SCOPES)
            logger.info("Loaded Gmail credentials from GMAIL_TOKEN_JSON")
        except Exception as e:
            logger.error(f"Failed to load GMAIL_TOKEN_JSON: {e}")

    # 2. Check if valid
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            logger.info("Refreshed expired Gmail credentials")
        except Exception as e:
            logger.error(f"Failed to refresh credentials: {e}")
            # Don't invalidate creds yet, maybe we can re-auth?
            # But usually if refresh fails, we need new auth.
            creds = None

    # 3. If still no valid creds, try interactive flow (fallback)
    # This might not work well in MCP server mode, but we keep it for local dev
    if not creds or not creds.valid:
        creds_json = os.getenv("GMAIL_CREDENTIALS_JSON")
        if creds_json:
            try:
                if creds_json.startswith("'") and creds_json.endswith("'"):
                    creds_json = creds_json[1:-1]

                config = json.loads(creds_json)
                flow = InstalledAppFlow.from_client_config(config, SCOPES)
                # Run local server for auth
                creds = flow.run_local_server(port=0)

                # Log the new token so user can save it
                logger.info("New token obtained. Please save to GMAIL_TOKEN_JSON:")
                logger.info(creds.to_json())
            except Exception as e:
                logger.error(f"Failed to run interactive auth flow: {e}")

    return creds


def get_gmail_service() -> Resource | None:
    """Build and return the Gmail service."""
    creds = get_gmail_credentials()
    if not creds:
        logger.error("No valid Gmail credentials found.")
        return None

    try:
        service = build("gmail", "v1", credentials=creds)
        return service
    except Exception as e:
        logger.error(f"Failed to build Gmail service: {e}")
        return None
