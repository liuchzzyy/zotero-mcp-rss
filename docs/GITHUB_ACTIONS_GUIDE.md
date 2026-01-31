# GitHub Actions Workflows Guide

This document explains the GitHub Actions workflows used in Zotero MCP.

## Overview

Zotero MCP uses GitHub Actions for automated tasks:
- **CI/CD**: Code quality checks, testing, and security auditing
- **RSS Ingestion**: Daily RSS feed processing
- **Gmail Ingestion**: Daily Gmail alerts processing
- **Global Analysis**: Daily batch PDF analysis

## Quick Setup

### Prerequisites

1. Fork the repository to your GitHub account
2. Create a personal access token (PAT) with `repo` and `workflow` scopes
3. Enable GitHub Actions in your fork repository settings

### Required GitHub Secrets

Configure these secrets in your fork (Settings → Secrets and variables → Actions):

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `ZOTERO_USER_ID` | Your Zotero user ID (numeric) | `1234567` |
| `ZOTERO_API_KEY` | Zotero API key from zotero.org/settings/keys | `abc123...` |
| `OPENAI_API_KEY` | OpenAI API key for AI analysis | `sk-...` |
| `DEEPSEEK_API_KEY` | DeepSeek API key (optional, preferred) | `sk-...` |
| `GMAIL_CREDENTIALS` | Base64-encoded Gmail credentials JSON | `eyJ...` |
| `GMAIL_TOKEN` | Base64-encoded Gmail token pickle | `gASV...` |
| `CHROMADB_API_KEY` | ChromaDB API key (optional) | `...` |
| `CHROMADB_HOST` | ChromaDB host (optional) | `...` |

### Secret Generation

**Gmail Credentials:**
```bash
# Encode credentials.json
base64 -i path/to/credentials.json -w 0

# Encode token.pickle
base64 -i path/to/token.pickle -w 0
```

For detailed setup instructions, see `.env.example` in the repository root.

### Workflow Configuration

All workflows use these defaults (override via workflow `with:` inputs):
- **RSS Schedule**: Daily at 02:00 Beijing Time
- **Gmail Schedule**: Daily at 00:00 Beijing Time
- **Global Analysis**: Daily at 03:00 Beijing Time

All workflows support:
- `dry_run: true` - Test mode without making changes
- Manual triggering via GitHub Actions UI

## Workflow Files

### CI/CD Pipeline (`.github/workflows/ci.yml`)

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

**Jobs:**

1. **Lint and Type Check**
   - Runs Ruff linter
   - Checks code formatting
   - Runs type checker (ty)
   - Required before tests

2. **Unit Tests**
   - Runs pytest with coverage
   - Uploads coverage reports to Codecov
   - Depends on lint job

3. **Security Audit**
   - Runs pip-audit for vulnerability scanning
   - Checks for outdated dependencies
   - Runs independently

4. **Build Test**
   - Builds the package
   - Checks for dependency conflicts
   - Depends on lint and test jobs

### RSS Ingestion (`.github/workflows/rss-ingestion.yml`)

**Triggers:**
- Scheduled: Daily at 18:00 UTC (02:00 Beijing Time)
- Manual: Via workflow dispatch

**Inputs:**
- `opml_path`: Path to OPML file (default: `RSS/RSS_official.opml`)
- `collection_name`: Target Zotero collection (default: `00_INBOXS`)
- `days`: Days back to fetch (default: `15`)
- `dry_run`: Preview mode (default: `false`)

**Steps:**
1. Checkout code
2. Setup Python 3.11
3. Cache uv dependencies
4. Install dependencies
5. Run RSS fetch command
6. Upload logs as artifacts
7. Create and upload log archives
8. Generate summary

**Timeout:** 30 minutes

### Gmail Ingestion (`.github/workflows/gmail-ingestion.yml`)

**Triggers:**
- Scheduled: Daily at 16:00 UTC (00:00 Beijing Time)
- Manual: Via workflow dispatch

**Inputs:**
- `collection_name`: Target Zotero collection (default: `00_INBOXS`)
- `sender_filter`: Filter by sender (optional)
- `subject_filter`: Filter by subject (optional)
- `max_emails`: Maximum emails to process (default: `50`)
- `dry_run`: Preview mode (default: `false`)

**Steps:**
1. Checkout code
2. Setup Python 3.11
3. Cache uv dependencies
4. Install dependencies
5. Run Gmail process command
6. Upload logs as artifacts
7. Create and upload log archives
8. Generate summary

**Timeout:** 30 minutes

### Global Analysis (`.github/workflows/global-analysis.yml`)

**Triggers:**
- Scheduled: Daily at 19:00 UTC (03:00 Beijing Time)
- Manual: Via workflow dispatch

**Inputs:**
- `scan_limit`: Maximum items to process (default: `20`)
- `target_collection`: Target collection (default: `01_SHORTTERMS`)
- `dry_run`: Preview mode (default: `false`)

**Steps:**
1. Checkout code
2. Setup Python 3.11
3. Cache uv dependencies
4. Install dependencies
5. Verify installation
6. Run global scan command
7. Upload logs as artifacts
8. Create and upload log archives
9. Generate summary

**Timeout:** 60 minutes

## Best Practices Implemented

### 1. Concurrency Control

All workflows use `concurrency` to cancel in-progress runs:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

This prevents:
- Resource waste from duplicate runs
- Conflicts from simultaneous executions
- unnecessary API calls

### 2. Caching

Workflows cache dependencies for faster builds:

```yaml
- name: Cache uv cache
  uses: actions/cache@v4
  with:
    path: ~/.cache/uv
    key: ${{ runner.os }}-uv-${{ hashFiles('uv.lock') }}
```

Benefits:
- Faster dependency installation
- Reduced network usage
- Quicker workflow execution

### 3. Timeout Protection

Each job has a timeout to prevent hanging:

```yaml
timeout-minutes: 30
```

This prevents:
- Infinite loops
- Stalled processes
- Excessive resource usage

### 4. Input Validation

Workflow inputs use `type` for validation:

```yaml
dry_run:
  description: 'Preview mode'
  type: boolean
  default: false
```

This ensures:
- Type-safe inputs
- Clear UI in GitHub Actions
- Better error handling

### 5. Comprehensive Logging

All workflows log to:
- Console output (real-time)
- Log files (archived)
- GitHub Actions summaries
- Artifacts (downloadable)

This provides:
- Real-time monitoring
- Historical analysis
- Easy debugging
- Audit trail

### 6. Artifact Management

Log artifacts are:
- Uploaded with `if: always()` (preserved on failure)
- Retained for 3 days (storage optimization)
- Compressed with tar.gz (bandwidth savings)

### 7. Environment Mode

All workflows set `ENV_MODE: production`:

```yaml
env:
  ENV_MODE: production
```

This ensures:
- Consistent behavior
- Production-ready logging
- No debug overhead

### 8. Failure Handling

Workflows handle failures gracefully:

```yaml
- name: Upload logs
  if: always()  # Run even if previous steps fail
  uses: actions/upload-artifact@v4
```

This ensures:
- Logs are always available
- Debugging information preserved
- No data loss on failure

## Workflow Dispatch

### Manual Trigger

All scheduled workflows can be manually triggered:

1. Go to **Actions** tab in GitHub
2. Select the workflow
3. Click **Run workflow**
4. Configure inputs
5. Click **Run workflow**

### Example: Manual Global Analysis

1. Navigate to Actions → Global Analysis
2. Click **Run workflow**
3. Set parameters:
   - Scan limit: `50`
   - Target collection: `01_SHORTTERMS`
   - Dry run: `false` (unchecked)
4. Click **Run workflow**

## Secrets Management

Workflows use GitHub Secrets for sensitive data:

### Required Secrets

- `ZOTERO_LIBRARY_ID` - Zotero library ID
- `ZOTERO_API_KEY` - Zotero API key
- `OPENAI_API_KEY` - OpenAI API key (optional)
- `DEEPSEEK_API_KEY` - DeepSeek API key (optional)
- `GEMINI_API_KEY` - Gemini API key (optional)
- `GMAIL_TOKEN_JSON` - Gmail OAuth token (JSON)
- `GMAIL_SENDER_FILTER` - Gmail sender filter (optional)
- `RSS_PROMPT` - RSS filtering prompt

### Adding Secrets

1. Go to repository **Settings**
2. Click **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add name and value
5. Click **Add secret**

## Monitoring and Debugging

### Viewing Workflow Runs

1. Go to **Actions** tab
2. Select workflow from left sidebar
3. Click on run to view details
4. Expand steps to see logs

### Downloading Artifacts

1. Open workflow run
2. Scroll to **Artifacts** section
3. Click artifact name to download
4. Extract tar.gz to access logs

### Common Issues

**Workflow fails at dependency installation:**
- Check `uv.lock` is up to date
- Verify Python version compatibility
- Check for dependency conflicts

**Workflow times out:**
- Check timeout-minutes setting
- Review logs for hanging operations
- Consider reducing workload (items/emails)

**Logs missing artifacts:**
- Check `~/.cache/zotero-mcp/logs/` exists
- Verify log retention settings
- Check artifact upload permissions

## Performance Optimization

### Scheduled Workflows Schedule

Workflows are scheduled to avoid peak times:

- **RSS Ingestion**: 18:00 UTC (02:00 Beijing)
- **Gmail Ingestion**: 16:00 UTC (00:00 Beijing)
- **Global Analysis**: 19:00 UTC (03:00 Beijing)

This distribution prevents:
- Concurrent heavy operations
- Resource contention
- API rate limits

### Caching Strategy

Cache keys use `uv.lock` hash:

```yaml
key: ${{ runner.os }}-uv-${{ hashFiles('uv.lock') }}
```

This ensures:
- Cache invalidates on dependency changes
- Fast cache restoration
- Minimal cache misses

## Workflow Status

### Current Status

✅ CI/CD - Active
✅ RSS Ingestion - Active
✅ Gmail Ingestion - Active
✅ Global Analysis - Active

### Maintenance

To update workflows:

1. Edit `.github/workflows/*.yml`
2. Test changes in a feature branch
3. Create pull request
4. Review workflow run logs
5. Merge after verification

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [GitHub Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Artifact Documentation](https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts)
