# Getting Started with Zotero MCP

This guide will walk you through the setup and basic usage of the Zotero MCP server, which allows AI assistants like Claude to interact with your Zotero library.

## Prerequisites

1.  **Zotero Desktop**: Recommended for the best experience.
2.  **Better BibTeX**: A Zotero plugin that improves citation keys and annotation extraction. Highly recommended.
3.  **uv**: A modern Python package manager.

## Installation

We recommend using `uv` to install `zotero-mcp` globally. This ensures it runs in an isolated environment without conflicting with other Python packages.

```bash
# Install as a global tool
uv tool install zotero-mcp

# Verify installation
zotero-mcp version
```

## Configuration

The easiest way to configure Zotero MCP is using the interactive setup wizard.

### 1. Run Setup Wizard

Open your terminal and run:

```bash
zotero-mcp setup
```

This wizard will:
1.  **Detect Installation**: Locate your `zotero-mcp` executable.
2.  **Configure Claude**: Automatically update your Claude Desktop configuration file (`claude_desktop_config.json`).
3.  **Choose Mode**:
    *   **Local (Recommended)**: Connects to your local Zotero database (fast, supports full-text search). Requires Zotero to be running.
    *   **Web API**: Connects via Zotero's cloud API. Useful if you can't run Zotero locally.
4.  **Semantic Search**: Configure embedding models (OpenAI, Gemini, or local) to enable AI-powered search.

### 2. Manual Configuration (Advanced)

If you prefer to configure it manually or are using the Web API mode, you can use flags:

```bash
# For Web API access
zotero-mcp setup --no-local --api-key YOUR_KEY --library-id YOUR_ID
```

## Semantic Search

Zotero MCP includes a powerful semantic search engine that allows you to find papers by concept rather than just keywords.

### Initialize the Database

Before using semantic search, you must build the index:

```bash
# Basic index (metadata only, fast)
zotero-mcp update-db

# Full-text index (reads PDFs, slower but more accurate)
zotero-mcp update-db --fulltext
```

You can update this database anytime by running the command again.

### Check Status

```bash
zotero-mcp db-status
```

## Available Tools

Once connected, your AI assistant will have access to these tools:

### Search
- **`zotero_search`**: Search by keyword.
- **`zotero_semantic_search`**: Search by natural language concept/meaning.
- **`zotero_search_by_tag`**: Filter items by tags.
- **`zotero_advanced_search`**: Complex queries (title, author, year, etc.).
- **`zotero_get_recent`**: See recently added items.

### Items
- **`zotero_get_metadata`**: Get detailed item info (supports BibTeX).
- **`zotero_get_fulltext`**: Read the full text of a paper.
- **`zotero_get_bundle`**: Get everything about an item (metadata, notes, annotations, text) in one go.
- **`zotero_get_children`**: List attachments and notes.

### Annotations
- **`zotero_get_annotations`**: Extract highlights and comments from PDFs.
- **`zotero_get_notes`**: Read Zotero notes.
- **`zotero_search_notes`**: Search inside notes and annotations.

## Example Prompts

Try asking Claude:

*   "Find papers about **[topic]** in my library."
*   "Summarize the key findings of **[Paper Title]**."
*   "What are the recent papers I added about **[topic]**?"
*   "Find papers conceptually similar to this abstract: ..."
*   "Get all my highlights for **[Paper]** and summarize them."

## CLI Reference

`zotero-mcp` provides several useful commands:

| Command | Description |
|---------|-------------|
| `zotero-mcp setup` | Run the interactive setup wizard |
| `zotero-mcp serve` | Run the MCP server (used by clients) |
| `zotero-mcp update-db` | Update the semantic search database |
| `zotero-mcp db-status` | Show database status and stats |
| `zotero-mcp db-inspect` | Inspect indexed documents |
| `zotero-mcp setup-info` | Show installation path and config info |
| `zotero-mcp update` | Self-update to the latest version |

## Troubleshooting

**Q: Zotero database not found?**
A: Ensure Zotero has run at least once. If your database is in a custom location, specify it:
```bash
zotero-mcp update-db --db-path /path/to/zotero.sqlite
```

**Q: Full text extraction failing?**
A: Ensure PDF files are downloaded locally in Zotero.

**Q: Semantic search errors?**
A: Ensure you have run `update-db`. Check your API keys if using OpenAI/Gemini.

**Q: How to update?**
A: Run `uv tool upgrade zotero-mcp`.

**Q: How to uninstall?**
A: Run `uv tool uninstall zotero-mcp`. The config folder is at `~/.config/zotero-mcp`.
