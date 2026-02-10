# Zotero MCP

<p align="center">
  <a href="https://www.zotero.org/">
    <img src="https://img.shields.io/badge/Zotero-CC2936?style=for-the-badge&logo=zotero&logoColor=white" alt="Zotero">
  </a>
  <a href="https://modelcontextprotocol.io/introduction">
    <img src="https://img.shields.io/badge/MCP-0175C2?style=for-the-badge&logoColor=white" alt="MCP">
  </a>
  <a href="https://github.com/liuchzzyy/zotero-mcp/releases">
    <img src="https://img.shields.io/github/v/release/liuchzzyy/zotero-mcp?style=for-the-badge" alt="Release">
  </a>
</p>

**Zotero MCP** connects your [Zotero](https://www.zotero.org/) research library with AI assistants via the [Model Context Protocol](https://modelcontextprotocol.io/introduction). Search papers, extract PDF annotations, analyze research with AI, and automate your research workflow!

## ✨ Key Features

### 🤖 AI-Powered Research Analysis
- **Batch PDF Analysis**: Analyze multiple papers with LLM (DeepSeek/OpenAI/Gemini)
- **Multi-Modal PDF Analysis**: Advanced image and text analysis with OCR support
- **Intelligent Metadata Enhancement**: Auto-complete metadata via Crossref/OpenAlex APIs
- **Checkpoint/Resume**: Interrupted workflows automatically save progress and can be resumed
- **Configurable Templates**: Customizable analysis output formats (JSON/Markdown)

### 🔍 Semantic Search
- **Vector-based similarity search** over your entire research library
- **Multiple embedding models**: Default (free), OpenAI, and Gemini options
- **Smart results** with similarity scores and contextual matching
- **Auto-updating database** with configurable sync schedules

### 📚 Advanced Search & Access
- Multi-criteria search (title, author, tags, collections)
- Browse collections, tags, and recent additions
- Retrieve full text, attachments, notes, and child items
- Export citations in multiple formats (JSON, Markdown)

### 📝 PDF Annotation Extraction
- Extract annotations directly from PDF files
- Search through PDF annotations and comments
- Image annotation support
- Works alongside Zotero's native annotation system

### 🗑️ Duplicate Detection & Removal
- **Smart deduplication** by DOI, title, or URL priority
- **Cross-folder copy detection**: Identical items in multiple folders are preserved
- **Safe removal**: Duplicates moved to trash collection (not permanently deleted)
- **Preview mode**: Dry-run to review before actual deletion
- **Note/attachment protection**: Notes and attachments are never deleted

## 📦 Installation

### Quick Install with uv

```bash
# Install via uv
uv tool install "git+https://github.com/liuchzzyy/zotero-mcp.git"

# Configure
zotero-mcp setup

# Start server
zotero-mcp serve
```

### Requirements
- Python 3.10+
- Zotero 7+ (for local API with full-text access)
- An MCP-compatible client (Claude Desktop, Continue.dev, etc.)

## 🚀 Quick Start

### 1. Configuration

```bash
zotero-mcp setup
```

This creates `~/.config/zotero-mcp/config.json` with your settings.

### 2. Initialize Semantic Search (Optional)

```bash
# Fast metadata-only index
zotero-mcp update-db

# Comprehensive full-text index
zotero-mcp update-db --fulltext

# Check database status
zotero-mcp db-status
```

### 3. Start the Server

```bash
zotero-mcp serve
```

### 4. Configure Your MCP Client

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "zotero": {
      "command": "zotero-mcp",
      "args": [],
      "env": {
        "ZOTERO_LOCAL": "true"
      }
    }
  }
}
```

## 🛠️ Command-Line Tools

### Semantic Search
```bash
zotero-mcp update-db                      # Update database (metadata)
zotero-mcp update-db --fulltext           # Update with full-text
zotero-mcp update-db --force-rebuild      # Force complete rebuild
zotero-mcp db-status                      # Check database status
zotero-mcp db-inspect                     # Inspect indexed documents
```

### Research Workflow
```bash
zotero-mcp scan                            # Scan for unprocessed papers
zotero-mcp update-metadata                 # Enhance metadata from APIs
zotero-mcp deduplicate                     # Find and remove duplicates
zotero-mcp deduplicate --dry-run           # Preview duplicates
zotero-mcp pdf-find --item-key ABCD1234     # Find PDFs/SI for a single item
zotero-mcp pdf-find --collection-name 00_INBOXS  # Batch find PDFs/SI by collection
```

### Updates & Maintenance
```bash
zotero-mcp update                          # Update to latest version
zotero-mcp update --check-only             # Check for updates
zotero-mcp version                         # Show version info
zotero-mcp setup-info                      # Show installation info
```

## 🤖 Available MCP Tools

### Search & Discovery
- `zotero_semantic_search` - AI-powered similarity search
- `zotero_search` - Keyword search
- `zotero_advanced_search` - Multi-criteria search
- `zotero_search_by_tag` - Tag-based search
- `zotero_get_recent` - Recent items

### Content Access
- `zotero_get_metadata` - Item metadata
- `zotero_get_fulltext` - Full text content
- `zotero_get_bundle` - Comprehensive item data
- `zotero_get_children` - Attachments and notes

### Collections & Tags
- `zotero_get_collections` - List collections
- `zotero_find_collection` - Find by name (fuzzy matching)
- `zotero_get_tags` - List all tags

### Annotations & Notes
- `zotero_get_annotations` - PDF annotations
- `zotero_get_notes` - Retrieve notes
- `zotero_search_notes` - Search in notes/annotations
- `zotero_create_note` - Create new note

### Batch Workflow
- `zotero_prepare_analysis` - Collect PDF content for review
- `zotero_batch_analyze_pdfs` - AI-powered batch analysis
- `zotero_resume_workflow` - Resume interrupted workflow
- `zotero_list_workflows` - View workflow states

### PDF Discovery
- `zotero_find_pdf_si` - Find PDFs and supporting information (single)
- `zotero_find_pdf_si_batch` - Batch find PDFs and supporting information

## 🔧 Configuration

### Environment Variables

**Zotero Connection:**
```bash
ZOTERO_LOCAL=true                    # Use local API (default)
ZOTERO_API_KEY=your_key             # Required for web API
ZOTERO_LIBRARY_ID=your_id           # Required for web API
ZOTERO_LIBRARY_TYPE=user            # or 'group'
```

**Semantic Search:**
```bash
ZOTERO_EMBEDDING_MODEL=default      # default, openai, gemini
OPENAI_API_KEY=your_key
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
GEMINI_API_KEY=your_key
GEMINI_EMBEDDING_MODEL=models/text-embedding-004
```

**Batch Analysis:**
```bash
DEEPSEEK_API_KEY=your_key
DEEPSEEK_MODEL=deepseek-chat
```

**Multi-Modal Analysis:**
```bash
# CLI LLM Provider Configuration
ZOTERO_MCP_CLI_LLM_PROVIDER=deepseek       # deepseek, openai, gemini, claude
ZOTERO_MCP_CLI_LLM_MODEL=deepseek-chat     # Model to use
ZOTERO_MCP_CLI_LLM_API_KEY=your_key       # API key for the provider

# OCR Configuration
ZOTERO_MCP_CLI_LLM_OCR_ENABLED=true        # Enable OCR mode
ZOTERO_MCP_CLI_LLM_OCR_LANGUAGES=zh,en     # OCR languages
ZOTERO_MCP_CLI_LLM_OCR_ENGINE=tesseract    # OCR engine

# Analysis Parameters
ZOTERO_MCP_CLI_LLM_MAX_PAGES=50            # Max pages to process
ZOTERO_MCP_CLI_LLM_MAX_IMAGES=20           # Max images to extract
ZOTERO_MCP_CLI_LLM_CHUNK_SIZE=2000         # Text chunk size
```

### Web API Setup

For remote access without Zotero desktop:

```bash
zotero-mcp setup --no-local \
  --api-key YOUR_API_KEY \
  --library-id YOUR_LIBRARY_ID
```

Get your API key from https://www.zotero.org/settings/keys

## 📊 Automated Workflows (GitHub Actions)

### Pre-configured Workflows

**Daily Global Analysis**
- Scans library for unprocessed papers
- Analyzes with AI (DeepSeek/CLI)
- Creates structured notes
- Runs daily at 17:00 UTC

**Metadata Update**
- Enriches bibliographic fields via Crossref/OpenAlex
- Runs on schedule or manual trigger

**Deduplication**
- Finds and quarantines duplicates by DOI/title/URL
- Runs on schedule or manual trigger

**Manual Triggers**
All workflows support on-demand execution with dry-run mode.

### Setup Guide

See [GitHub Actions Guide](./docs/GITHUB_ACTIONS_GUIDE.md) for detailed setup instructions.

## 🔍 Deduplication

### How It Works

1. **Priority Matching**: DOI > Title > URL
2. **Smart Detection**: Identifies true duplicates vs. cross-folder copies
3. **Safe Removal**: Moves to trash collection (`06_TRASHES` by default)
4. **Preview Mode**: `--dry-run` to review before deletion

### Usage

```bash
# Preview duplicates
zotero-mcp deduplicate --dry-run --scan-limit 100 --treated-limit 10

# Remove duplicates
zotero-mcp deduplicate --scan-limit 100 --treated-limit 50

# Custom trash collection
zotero-mcp deduplicate --trash-collection "My Trash"

# Limit to specific collection
zotero-mcp deduplicate --collection ABC123
```

### What Gets Deleted

✅ **Deleted (True Duplicates):**
- Same DOI but different metadata
- Same title but different metadata
- Same URL but different metadata
- Items without attachments/notes are deleted, most complete kept

❌ **Preserved (Cross-Folder Copies):**
- Identical metadata in multiple collections
- Notes and attachments are never deleted
- Most complete item (with attachments/notes) is kept

## 🐛 Troubleshooting

### Common Issues

**"No results found"**
- Ensure Zotero is running
- Enable "Allow other applications to communicate" in Zotero preferences
- Check `zotero-mcp db-status` for semantic search

**"DeepSeek API key not found"**
- Set `DEEPSEEK_API_KEY` environment variable
- Or configure in `~/.config/zotero-mcp/config.json`

**"Database update takes too long"**
- Default `update-db` is fast (metadata-only)
- Use `--limit 100` for testing
- Use `--fulltext` only when needed (comprehensive but slow)

**Workflow interrupted**
- Use `zotero_list_workflows()` to find workflow ID
- Use `zotero_resume_workflow(workflow_id)` to continue

**Items not moving to trash collection**
- Verify collection name is correct (default: `06_TRASHES`)
- Check that collection exists in your library
- Use `--dry-run` to preview before actual deletion

### Recovery

**Restore deleted duplicates:**
Items are moved to trash collection, not permanently deleted. Simply move them back to restore.

**Rebuild search database:**
```bash
zotero-mcp update-db --force-rebuild
```

**Reset configuration:**
```bash
rm ~/.config/zotero-mcp/config.json
zotero-mcp setup
```

## 📚 Documentation

- [CLAUDE.md](./CLAUDE.md) - Development guidelines for Claude Code
- [中文指南](./docs/中文指南.md) - 最新逻辑框架与函数说明
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Contribution guidelines
- [Batch Workflow Example](./examples/workflow_example.py) - Production-grade code example

## 🏗️ Architecture Overview

Zotero MCP is now a single, cohesive package with a Logseq-inspired layering:

```
src/zotero_mcp
├── server.py    # MCP stdio server entrypoint
├── cli.py       # CLI entrypoint
├── clients/     # External APIs (Zotero, metadata, LLM, database)
├── input/       # External input adapters (paper-feed)
├── handlers/    # MCP tool/prompt handlers (logseq-mcp style)
├── services/    # Core business logic (search, items, workflows)
├── models/      # Pydantic schemas and AI models
├── analyzer/    # PDF analysis and LLM pipelines
├── settings.py  # Pydantic Settings (logseq-mcp aligned)
└── utils/       # Shared helpers (config, logging, formatting)
```

The PDF analyzer and Zotero core logic are fully integrated into the main package to reduce duplication and keep a single source of truth.

## 📝 Changelog

The current version is defined in `pyproject.toml`. See `CHANGELOG.md` for the full release history.

## 📄 License

MIT License - see [LICENSE](./LICENSE) for details.

## 🙏 Acknowledgments

- [Zotero](https://www.zotero.org/) - Excellent reference management software
- [Model Context Protocol](https://modelcontextprotocol.io/) - Standard for AI tool integration
- [ChromaDB](https://www.trychroma.com/) - Vector database for semantic search
- All contributors and users of Zotero MCP!

---

**Made with ❤️ for researchers worldwide**
