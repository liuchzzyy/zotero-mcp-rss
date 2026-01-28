# Gmail Integration Setup Guide

This guide explains how to configure Gmail integration for Zotero MCP, including both local development and GitHub Actions automation.

## 📋 Overview

Gmail integration allows you to:
- **Search emails** by sender, subject, or custom queries
- **Extract research items** from email newsletters and updates
- **Import to Zotero** automatically
- **Auto-delete** processed emails (optional)

Works with:
- 📧 Gmail newsletters with research paper links
- 📚 Email alerts from journals and databases
- 🎯 Custom email sources with structured content

## 🔧 Prerequisites

- A Google account with Gmail enabled
- Python 3.10+ installed
- [Google Cloud Console](https://console.cloud.google.com/) access

---

## 📝 Step 1: Create Google Cloud Project

### 1.1 Enable Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Create Project"** or select existing project
3. Navigate to **APIs & Services** → **Library**
4. Search for **"Gmail API"**
5. Click **"Enable"**

### 1.2 Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **"External"** user type
3. Click **"Create"**
4. Fill in:
   - **App name**: `Zotero MCP` (or any name you prefer)
   - **User support email**: Your email
   - **Developer contact**: Your email
5. Click **"Save and Continue"** (skip additional steps for testing)

### 1.3 Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **"+ Create Credentials"** → **"OAuth client ID"**
3. Select **"Desktop app"** as application type
4. Name it: `Zotero MCP Desktop`
5. Click **"Create"**

### 1.4 Download Credentials

1. After creation, click the download icon (↓)
2. Save as `credentials.json`
3. Move to: `~/.config/zotero-mcp/credentials.json`

**Windows users**: The `~` path resolves to `C:\Users\YourUsername\.config\zotero-mcp\`

---

## 🚀 Step 2: Authorize Application (Local)

### Option A: Quick Authorization Script

Run the included authorization script:

```bash
# Run authorization flow
uv run python src/scripts/gmail_auth.py

# This will:
# 1. Open a browser window
# 2. Ask you to sign in with Google
# 3. Request Gmail access permission
# 4. Save token.json automatically
```

### Option B: Manual Authorization

If the script doesn't work, follow these steps:

1. Create a Python script `authorize_gmail.py`:

```python
import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

def authorize():
    """Authorize Gmail OAuth2 and save token."""
    creds_path = Path.home() / ".config" / "zotero-mcp" / "credentials.json"
    token_path = Path.home() / ".config" / "zotero-mcp" / "token.json"

    credentials = None

    # Load existing token
    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(token_path, SCOPES)

    # If no valid credentials, get new ones
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            credentials = flow.run_local_server(port=0)

        # Save credentials
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as token:
            token.write(credentials.to_json())

    print(f"✅ Token saved to: {token_path}")
    print("📝 Use this file for local development")
    print("🌐 For GitHub Actions, copy this file content to GMAIL_TOKEN_JSON secret")

if __name__ == "__main__":
    authorize()
```

2. Run the script:

```bash
python authorize_gmail.py
```

3. Browser will open → Sign in → Grant permissions → Token saved

---

## 🎯 Step 3: Configure Local Development

### 3.1 Create .env File

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

### 3.2 Update .env (Optional)

```bash
# Only needed if you want to customize these settings
GMAIL_SENDER_FILTER="newsletter@example.com"
GMAIL_SUBJECT_FILTER="Weekly Research Update"
GMAIL_COLLECTION="00_INBOXS"          # Zotero collection name
GMAIL_TRASH_ONLY="true"               # Move to trash vs delete
```

**Default behavior** (if you leave them empty):
- Process ALL emails (no filters)
- Import to `00_INBOXS` collection
- Move to trash after processing

### 3.3 Test Gmail Connection

```bash
# Run a test script (you'll need to create this)
uv run python src/scripts/test_gmail.py
```

Expected output:
```
✅ Gmail client initialized
✅ Token loaded from ~/.config/zotero-mcp/token.json
✅ Gmail API service ready
🔍 Found 5 emails matching criteria
```

---

## 🌐 Step 4: Configure GitHub Actions

### 4.1 Get Token Content

Read your `token.json` file:

```bash
# macOS/Linux
cat ~/.config/zotero-mcp/token.json

# Windows
type %USERPROFILE%\.config\zotero-mcp\token.json
```

Copy the entire JSON content (it should look like):

```json
{
  "token": "ya29.a0AfH6...",
  "refresh_token": "1//0g...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "...",
  "client_secret": "...",
  "scopes": ["https://www.googleapis.com/auth/gmail.modify"],
  "expiry": "2024-01-29T00:00:00Z"
}
```

### 4.2 Add GitHub Secrets

1. Go to your repository on GitHub
2. **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**
4. Add:

| Secret Name | Value | Required |
|-------------|-------|----------|
| `GMAIL_TOKEN_JSON` | Full JSON content from `token.json` | ✅ Yes |
| `GMAIL_SENDER_FILTER` | Email address to filter (optional) | ❌ No |
| `GMAIL_SUBJECT_FILTER` | Subject keywords (optional) | ❌ No |

**Important**: `GMAIL_TOKEN_JSON` must be the **complete JSON string**, not a path.

### 4.3 Create/Update GitHub Workflow

Add Gmail workflow to `.github/workflows/gmail-auto.yml`:

```yaml
name: Gmail Auto-Import

on:
  schedule:
    # Run daily at 8:00 AM Beijing Time (UTC+8)
    - cron: '0 0 * * *'

  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Preview only, no actual changes'
        type: boolean
        default: false

jobs:
  import-gmail:
    runs-on: ubuntu-latest
    environment: production

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v7
        with:
          version: "latest"
          enable-cache: true

      - name: Set up Python
        run: uv python install 3.12

      - name: Install Dependencies
        run: uv sync --locked

      - name: Import from Gmail
        env:
          ZOTERO_LIBRARY_ID: ${{ secrets.ZOTERO_LIBRARY_ID }}
          ZOTERO_API_KEY: ${{ secrets.ZOTERO_API_KEY }}
          GMAIL_TOKEN_JSON: ${{ secrets.GMAIL_TOKEN_JSON }}
          GMAIL_SENDER_FILTER: ${{ secrets.GMAIL_SENDER_FILTER }}
          ZOTERO_LOCAL: "false"
        run: |
          echo "=== Gmail Auto-Import ==="
          uv run python src/scripts/gmail_auto_import.py

      - name: Upload Logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: gmail-import-logs-${{ github.run_number }}
          path: *.log
          retention-days: 30
```

---

## 📚 Step 5: Usage Examples

### Local Usage

```python
import asyncio
from zotero_mcp.services.gmail import GmailService

async def main():
    service = GmailService()

    # Fetch and process emails
    result = await service.process_gmail_workflow(
        sender="newsletter@example.com",
        subject="Research Update",
        max_emails=10,
        delete_after=True,  # Move to trash
        collection="00_INBOXS"
    )

    print(f"Processed: {result.emails_processed} emails")
    print(f"Imported: {result.items_imported} items")
    print(f"Deleted: {result.emails_deleted} emails")

asyncio.run(main())
```

### GitHub Actions Usage

The workflow runs automatically and:
1. Fetches emails matching filters
2. Extracts research items from email content
3. Imports to specified Zotero collection
4. Deletes processed emails (or moves to trash)

---

## 🔧 Configuration Options

### Email Filtering

| Option | Description | Example |
|--------|-------------|---------|
| `sender` | Filter by email address | `GMAIL_SENDER_FILTER="nature@nature.com"` |
| `subject` | Filter by subject keywords | `GMAIL_SUBJECT_FILTER="weekly digest"` |
| `query` | Custom Gmail search query | Use `query=` parameter in code |

**Gmail Query Examples:**
- `from:arxiv.org` - Emails from arXiv
- `subject:(alert OR digest)` - Subject contains "alert" or "digest"
- `has:attachment` - Only emails with attachments

### Import Settings

| Option | Default | Description |
|--------|---------|-------------|
| `collection` | `00_INBOXS` | Zotero collection to import into |
| `trash_only` | `true` | Move to trash vs permanent delete |
| `max_emails` | `50` | Maximum emails per run |

---

## 🐛 Troubleshooting

### "InvalidCredentials: Token has been revoked"

**Solution**: Re-run authorization script

```bash
uv run python src/scripts/gmail_auth.py
```

### "File not found: credentials.json"

**Solution**: Ensure file is in correct location

```bash
# macOS/Linux
ls ~/.config/zotero-mcp/credentials.json

# Windows
dir %USERPROFILE%\.config\zotero-mcp\credentials.json

# Or set custom path
export GMAIL_CREDENTIALS_PATH="/path/to/your/credentials.json"
```

### "GMAIL_TOKEN_JSON secret not found" (GitHub Actions)

**Solution**:
1. Check secret name matches exactly (case-sensitive)
2. Ensure secret was added (not just committed to repo)
3. Verify secret content is valid JSON

### "No emails found matching criteria"

**Possible causes**:
1. No emails match your filters
2. Emails are in trash/spam folders
3. OAuth token has insufficient permissions

**Debug**:
```python
# Test without filters first
result = await service.process_gmail_workflow(
    query="",  # No filters
    max_emails=10
)
```

### "Rate limit exceeded"

**Gmail API quotas**:
- Daily usage: 1 billion quota units per day
- Full email access: 5-50 quota units per email

**Solution**:
- Reduce `max_emails` parameter
- Add delays between email processing
- Implement retry logic with exponential backoff

---

## 🔒 Security Best Practices

### Local Development

1. ✅ **Never commit** `credentials.json` or `token.json`
2. ✅ **Add to .gitignore**:
   ```
   *.json
   !.env.example
   ```
3. ✅ **Rotate tokens** periodically
4. ✅ **Use minimal scopes** (`gmail.modify` is sufficient)

### GitHub Actions

1. ✅ **Use repository secrets** (never commit tokens)
2. ✅ **Restrict workflow permissions** (read/write only when needed)
3. ✅ **Enable branch protection** (require reviews for changes)
4. ✅ **Monitor workflow runs** for suspicious activity

---

## 📖 Advanced Topics

### Custom Email Parsing

The `GmailService` automatically extracts items from common email formats:

1. **HTML Tables**: Newsletter layouts with paper metadata
2. **Div structures**: Email newsletters with div-based layouts
3. **Links**: Simple emails with paper URLs

To add custom parsing logic:

```python
class CustomGmailService(GmailService):
    def _extract_custom_items(self, html_content, email_id, email_subject):
        """Custom extraction logic."""
        # Your parsing code here
        return items
```

### Batch Processing with Retry

```python
import asyncio
from zotero_mcp.services.gmail import GmailService

async def process_with_retry():
    service = GmailService()

    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = await service.process_gmail_workflow(
                sender="newsletter@example.com",
                max_emails=20,
                delete_after=True
            )
            print(f"✅ Success: {result.emails_processed} emails")
            break
        except Exception as e:
            print(f"⚠️ Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise

asyncio.run(process_with_retry())
```

---

## 📚 Additional Resources

- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Python Google API Client Library](https://github.com/googleapis/python-api-core)
- [Gmail Search Operators](https://support.google.com/mail/answer/7190)

---

## 🆘 Support

If you encounter issues:

1. **Check logs**: Review log files in project directory
2. **Test connection**: Run test scripts locally first
3. **Verify credentials**: Ensure OAuth token is valid
4. **Consult documentation**: Review this guide's troubleshooting section
5. **Open issue**: Report bugs or feature requests in the repository

---

**Last Updated**: 2026-01-29
