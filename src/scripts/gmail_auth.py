#!/usr/bin/env python3
"""
Gmail OAuth2 Quick Authorization Script

This script helps you quickly authorize Gmail API access for Zotero MCP.

Usage:
    python src/scripts/gmail_auth.py

The script will:
1. Open a browser window for Google OAuth
2. Request permission to access your Gmail
3. Save the authorization token to ~/.config/zotero-mcp/token.json
4. Display instructions for GitHub Actions setup

Prerequisites:
    - credentials.json must be in ~/.config/zotero-mcp/
    - See docs/GMAIL-SETUP.md for setup instructions
"""

import json
import os
from pathlib import Path
import sys
from typing import cast

try:
    import click
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Please run: uv sync --group dev")
    sys.exit(1)

# Gmail API scopes
# https://developers.google.com/gmail/api/auth/scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Default paths
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "zotero-mcp"
DEFAULT_CREDENTIALS_PATH = DEFAULT_CONFIG_DIR / "gmail_credentials.json"
DEFAULT_TOKEN_PATH = DEFAULT_CONFIG_DIR / "token.json"


def get_credentials_path() -> Path:
    """Get credentials file path from env or default."""
    return Path(os.getenv("GMAIL_CREDENTIALS_PATH", DEFAULT_CREDENTIALS_PATH))


def get_token_path() -> Path:
    """Get token file path from env or default."""
    return Path(os.getenv("GMAIL_TOKEN_PATH", DEFAULT_TOKEN_PATH))


def load_existing_token(token_path: Path) -> Credentials | None:
    """Load existing token if valid."""
    if not token_path.exists():
        return None

    try:
        credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if credentials and credentials.valid:
            print(f"✅ Loaded valid token from: {token_path}")
            return credentials
        elif credentials and credentials.expired and credentials.refresh_token:
            print("⏰ Token expired, refreshing...")
            credentials.refresh(Request())
            save_token(credentials, token_path)
            print("✅ Token refreshed and saved")
            return credentials

    except (json.JSONDecodeError, ValueError) as e:
        print(f"⚠️  Error loading token: {e}")
        return None

    return None


def save_token(credentials: Credentials, token_path: Path) -> None:
    """Save credentials to token file."""
    token_path.parent.mkdir(parents=True, exist_ok=True)

    with open(token_path, "w") as token_file:
        token_file.write(credentials.to_json())

    print(f"✅ Token saved to: {token_path}")


def authorize() -> Credentials:
    """Run OAuth2 authorization flow."""
    credentials_path = get_credentials_path()
    token_path = get_token_path()

    # Check if credentials file exists
    if not credentials_path.exists():
        print(f"❌ Credentials file not found: {credentials_path}")
        print()
        print("Please follow these steps:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project and enable Gmail API")
        print("3. Create OAuth 2.0 credentials (Desktop app)")
        print("4. Download credentials.json")
        print(f"5. Save it to: {credentials_path}")
        print()
        print("See docs/GMAIL-SETUP.md for detailed instructions.")
        sys.exit(1)

    # Try to load existing token
    credentials = load_existing_token(token_path)

    # If no valid token, run authorization flow
    if not credentials:
        print("🔐 Starting OAuth2 authorization flow...")
        print("📋 A browser window will open for Google sign-in")
        print()

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            # Cast to Credentials since flow.run_local_server returns a compatible type
            credentials = cast(Credentials, flow.run_local_server(port=0))
            save_token(credentials, token_path)
        except Exception as e:
            print(f"❌ Authorization failed: {e}")
            sys.exit(1)

    # credentials is guaranteed to be non-None at this point
    assert credentials is not None
    return credentials


def display_next_steps(token_path: Path):
    """Display next steps for user."""
    print()
    print("=" * 60)
    print("✅ Authorization successful!")
    print("=" * 60)
    print()
    print("📝 Local Development:")
    print(f"   Token file: {token_path}")
    print("   You can now use Gmail integration locally.")
    print()
    print("🌐 GitHub Actions Setup:")
    print("   1. Read your token file:")
    if sys.platform == "win32":
        print("      type %USERPROFILE%\\.config\\zotero-mcp\\token.json")
    else:
        print(f"      cat {token_path}")
    print()
    print("   2. Copy the entire JSON content")
    print("   3. Go to GitHub repository Settings → Secrets and variables → Actions")
    print("   4. Add new secret: GMAIL_TOKEN_JSON")
    print("   5. Paste the JSON content as the secret value")
    print()
    print("⚠️  Important: The secret value must be the COMPLETE JSON string,")
    print("   not a file path or partial content.")
    print()
    print("📚 For more information, see:")
    print("   docs/GMAIL-SETUP.md")
    print("=" * 60)


def verify_credentials(credentials: Credentials) -> bool:
    """Verify that credentials are properly configured."""
    if not credentials:
        return False

    # Check required fields
    required_fields = ["token", "refresh_token", "client_id", "client_secret"]
    token_data = json.loads(credentials.to_json())

    for field in required_fields:
        if field not in token_data or not token_data[field]:
            print(f"⚠️  Missing field in credentials: {field}")
            return False

    # Check scopes
    if SCOPES[0] not in token_data.get("scopes", []):
        print(f"⚠️  Incorrect scope. Expected: {SCOPES[0]}")
        return False

    return True


@click.command()
@click.option(
    "--credentials-path",
    type=click.Path(exists=True),
    help="Path to credentials.json (overrides default)",
)
@click.option(
    "--token-path",
    type=click.Path(),
    help="Path to save token.json (overrides default)",
)
@click.option(
    "--verify-only",
    is_flag=True,
    help="Only verify existing token, don't authorize",
)
def main(credentials_path, token_path, verify_only):
    """
    Gmail OAuth2 Authorization Script

    Authorize Gmail API access for Zotero MCP and save token.

    Example:
        python src/scripts/gmail_auth.py

    For GitHub Actions:
        python src/scripts/gmail_auth.py --verify-only
        cat ~/.config/zotero-mcp/token.json  # Copy to GMAIL_TOKEN_JSON secret
    """
    # Override paths if provided
    if credentials_path:
        os.environ["GMAIL_CREDENTIALS_PATH"] = credentials_path
    if token_path:
        os.environ["GMAIL_TOKEN_PATH"] = token_path

    # Get actual paths
    actual_token_path = get_token_path()

    # Verify only mode
    if verify_only:
        print(f"🔍 Verifying token: {actual_token_path}")

        if not actual_token_path.exists():
            print(f"❌ Token file not found: {actual_token_path}")
            print("   Run without --verify-only to authorize.")
            sys.exit(1)

        credentials = load_existing_token(actual_token_path)

        if not credentials:
            print("❌ Failed to load token")
            sys.exit(1)

        # At this point credentials is guaranteed to be non-None
        assert credentials is not None
        if verify_credentials(credentials):
            print("✅ Token is valid and ready to use")
            display_token_content(credentials)
        else:
            print("❌ Token verification failed")
            sys.exit(1)

        return

    # Run authorization
    credentials = authorize()

    # Verify credentials
    if verify_credentials(credentials):
        display_next_steps(actual_token_path)
    else:
        print("❌ Credentials verification failed")
        sys.exit(1)


def display_token_content(credentials: Credentials):
    """Display token content for GitHub Actions setup."""
    token_data = json.loads(credentials.to_json())

    print()
    print("=" * 60)
    print("📋 Token Content (for GMAIL_TOKEN_JSON secret):")
    print("=" * 60)
    print()
    print(json.dumps(token_data, indent=2))
    print()
    print("=" * 60)
    print("⚠️  Copy the JSON above and add it as GMAIL_TOKEN_JSON secret")
    print("=" * 60)


if __name__ == "__main__":
    main()
