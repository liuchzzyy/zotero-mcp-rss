# CLAUDE.md

This file provides guidance to Claude Code when working in the `zotero-mcp/` sub-project.

## IMPORTANT Rules

1. **Always address the user as "干饭小伙子"** in EVERY single reply without exception. This applies to ALL responses. Never skip this.
2. **Commit to git after every file modification.** After modifying any file, immediately stage and commit with a clear message.
3. **No summary markdown files.** Do NOT create summary .md files. Display results directly in the console.
4. **All secrets via `.env` only.** Never hardcode API keys, library IDs, or credentials in source files. Always use `os.environ[...]` with `python-dotenv`.

## Project Overview

`zotero-mcp` is a Model Context Protocol (MCP) server for Zotero integration, supporting:
- Semantic search via ChromaDB
- PDF annotation extraction
- Literature metadata enrichment (OpenAlex)
- Duplicate detection and removal
- Batch analysis workflows

**GitHub repo:** `liuchzzyy/zotero-mcp` (fork of `54yyyu/zotero-mcp`)

## Python Environment

Uses **uv** as the package manager. Python 3.12+.

```bash
uv sync          # install dependencies
uv run <cmd>     # run any command in the venv
uv add <pkg>     # add a dependency
```

## Configuration

All secrets and paths live in `.env` (gitignored). Copy from `.env.example` to get started:

```bash
cp .env.example .env
# then fill in your values
```

Key variables:

| Variable | Description |
|----------|-------------|
| `ZOTERO_LIBRARY_ID` | Zotero user library ID |
| `ZOTERO_API_KEY` | Zotero Web API key |
| `DEEPSEEK_API_KEY` | DeepSeek API key (LLM tasks) |
| `ELSEVIER_API_KEY` | Elsevier API key |
| `OPENALEX_API_KEY` | OpenAlex API key |
| `ZOTERO_STORAGE_PATH` | Local Zotero storage root |
| `SHORTTERMS_SI_DIR` | SI download directory |
| `ZOTERO_SHORTTERMS_KEY` | Collection key for `01_SHORTTERMS` |
| `ZOTERO_INBOXS_AA_KEY` | Collection key for `00_INBOXS_AA` |
| `ZOTERO_INBOXS_BB_KEY` | Collection key for `00_INBOXS_BB` |
| `ZOTERO_INBOXS_CC_KEY` | Collection key for `00_INBOXS_CC` |
| `ZOTERO_INBOXS_DD_KEY` | Collection key for `00_INBOXS_DD` |

> **Security note:** Git history was rewritten (2026-03) to redact leaked API keys.
> All previously exposed keys (Zotero, DeepSeek, Elsevier, OpenAlex) should be regenerated.

## Key Scripts

### `classify_shortterms.py` — moved to skill

**Canonical location:** `~/.claude/skills/zotero-shortterms-classify/classify_shortterms.py`

Routes items from `01_SHORTTERMS` into four inboxes:

| Inbox | Criteria |
|-------|----------|
| `00_INBOXS_AA` | Single PDF, AI-tagged — ready for analysis |
| `00_INBOXS_BB` | Review articles (综述) |
| `00_INBOXS_CC` | Multiple PDFs (main + SI combined) |
| `00_INBOXS_DD` | Duplicate PDFs (same article twice) |

```bash
SCRIPT="C:/Users/chengliu/.claude/skills/zotero-shortterms-classify/classify_shortterms.py"
uv run python "$SCRIPT"            # classify new items
uv run python "$SCRIPT" recheck    # re-check CC↔DD boundary
uv run python "$SCRIPT" recheck_bb # re-verify BB review items
```

See `~/.claude/skills/zotero-shortterms-classify/SKILL.md` for full details.

### `scripts/generate_zotero_windows_shortcuts_pdf.py`

Generates a keyboard shortcut reference PDF for Zotero on Windows.

## MCP Server

```bash
uv run zotero-mcp serve          # start MCP server (stdio)
uv run zotero-mcp workflow --help  # list available workflows
```

### CLI Workflows

```bash
uv run zotero-mcp workflow deduplicate --scan-limit 100 --treated-limit 100
uv run zotero-mcp workflow metadata-update --scan-limit 200 --treated-limit 200
uv run zotero-mcp workflow item-analysis --treated-limit 20
```

## GitHub Actions CI

Workflows are defined in `.github/workflows/` and run on `liuchzzyy/zotero-mcp`.

Trigger manually via GitHub CLI:

```bash
gh workflow run metadata-update.yml --repo liuchzzyy/zotero-mcp --field treated_limit=1
gh workflow run deduplicate.yml     --repo liuchzzyy/zotero-mcp --field treated_limit=1
gh workflow run item-analysis.yml   --repo liuchzzyy/zotero-mcp --field treated_limit=1
```

| Workflow | File | Schedule (BJT) | Purpose |
|----------|------|----------------|---------|
| Metadata Update | `metadata-update.yml` | Daily 22:05 | Enrich metadata via OpenAlex |
| Deduplicate | `deduplicate.yml` | Daily 23:05 | Remove duplicate parent items |
| Item Analysis | `item-analysis.yml` | — | AI-powered item analysis |

## Language

- Code and comments: **English**
- Communication with user: **Chinese (中文)**
