#!/usr/bin/env python3
"""
Simplified Gmail OAuth Authorization Script

Run this if the main auth.py script has issues.
"""

import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

# Gmail API scope
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Paths
CONFIG_DIR = Path.home() / ".config" / "zotero-mcp"
CREDENTIALS_PATH = CONFIG_DIR / "gmail_credentials.json"
TOKEN_PATH = CONFIG_DIR / "token.json"


def main():
    """Run OAuth authorization flow."""
    print("=" * 60)
    print("🔐 Gmail OAuth Authorization")
    print("=" * 60)
    print()

    # Check credentials file
    if not CREDENTIALS_PATH.exists():
        print(f"❌ Credentials file not found: {CREDENTIALS_PATH}")
        print()
        print("Please ensure gmail_credentials.json exists in:")
        print(f"   {CONFIG_DIR}")
        return

    print(f"✅ Found credentials: {CREDENTIALS_PATH}")
    print(f"📁 Will save token to: {TOKEN_PATH}")
    print()

    # Run authorization flow
    try:
        print("🌐 Opening browser for Google sign-in...")
        print("   Please sign in and grant Gmail access permission")
        print()

        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
        credentials = flow.run_local_server(port=0)

        # Save token
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(credentials.to_json())

        print()
        print("=" * 60)
        print("✅ Authorization successful!")
        print("=" * 60)
        print()
        print(f"📁 Token saved to: {TOKEN_PATH}")
        print()
        print("📝 For GitHub Actions:")
        print("   1. Read token file content:")
        print(f"      type {TOKEN_PATH}")
        print("   2. Copy entire JSON content")
        print("   3. Add as GMAIL_TOKEN_JSON secret in GitHub")
        print()

        # Show token content for GitHub Actions
        with open(TOKEN_PATH) as f:
            token_data = json.load(f)
        print("=" * 60)
        print("📋 Token Content (for GMAIL_TOKEN_JSON):")
        print("=" * 60)
        print(json.dumps(token_data, indent=2))
        print()

    except Exception as e:
        print()
        print("=" * 60)
        print("❌ Authorization failed")
        print("=" * 60)
        print(f"Error: {e}")
        print()
        print("Possible issues:")
        print("  1. Browser window was closed")
        print("  2. Access was denied")
        print("  3. Network connection issues")
        print("  4. Incorrect credentials file format")
        print()


if __name__ == "__main__":
    main()
