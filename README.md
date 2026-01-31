# Zotero MCP: Connect your Research Library with AI Agents

<p align="center">
  <a href="https://www.zotero.org/">
    <img src="https://img.shields.io/badge/Zotero-CC2936?style=for-the-badge&logo=zotero&logoColor=white" alt="Zotero">
  </a>
  <a href="https://modelcontextprotocol.io/introduction">
    <img src="https://img.shields.io/badge/MCP-0175C2?style=for-the-badge&logoColor=white" alt="MCP">
  </a>
</p>

**Zotero MCP** seamlessly connects your [Zotero](https://www.zotero.org/) research library with AI assistants via the [Model Context Protocol](https://modelcontextprotocol.io/introduction). Review papers, get summaries, analyze citations, extract PDF annotations, and more!

## Features

### AI-Powered Semantic Search
- **Vector-based similarity search** over your entire research library
- **Multiple embedding models**: Default (free), OpenAI, and Gemini options
- **Intelligent results** with similarity scores and contextual matching
- **Auto-updating database** with configurable sync schedules

### Search Your Library
- Find papers, articles, and books by title, author, or content
- Perform complex searches with multiple criteria
- Browse collections, tags, and recent additions
- Semantic search for conceptual and topic-based discovery

### Access Your Content
- Retrieve detailed metadata for any item
- Get full text content (when available)
- Access attachments, notes, and child items

### Work with Annotations
- Extract and search PDF annotations directly
- Access Zotero's native annotations
- Create and update notes and annotations

### Batch PDF Analysis
- **AI-powered paper analysis** - Analyze multiple research papers with LLM (DeepSeek)
- **Checkpoint/resume support** - Automatically save progress and resume interrupted workflows
- **Structured notes** - Generate formatted analysis notes with configurable templates
- **Dual modes** - Preview data first or run fully automatic batch analysis
- See [examples/workflow_example.py](./examples/workflow_example.py) for a complete usage example

### RSS Feed Integration
- **Automated fetching** - Fetch RSS feeds daily via GitHub Actions
- **OPML support** - Import feeds from OPML files
- **AI filtering** - Use AI to filter articles by research interests
- **Smart import** - Automatically import new articles to your Zotero Inbox
- **Deduplication** - Avoid duplicate entries with URL checking

### Gmail Integration
- **Automated ingestion** - Process Google Scholar alerts and other email sources
- **AI-powered filtering** - Filter papers by research interests using LLM
- **Metadata enrichment** - Auto-complete metadata via Crossref/OpenAlex APIs
- **Smart author handling** - Automatically truncates long author lists to avoid sync errors
- **Correct execution order** - Papers imported to Zotero before emails are deleted
- **Daily processing** - Automated via GitHub Actions with configurable schedule

### Recent Improvements (January 2025)

#### Enhanced Error Handling
- **Fixed creator name errors** - HTTP 413 "creator name too long" errors resolved with automatic truncation
- **Improved metadata matching** - Lowered threshold from 0.7 to 0.6 for better paper matching
- **Increased API timeout** - Raised from 30s to 45s to handle slow network conditions
- **Cache error tolerance** - GitHub Actions continue even if cache service fails

#### Better Reliability
- **Gmail workflow fix** - Corrected execution order to ensure papers are imported before email deletion
- **Retry mechanisms** - All API calls use exponential backoff for transient failures
- **Comprehensive logging** - Detailed logs with 3-day retention for debugging

### Automated Workflows (GitHub Actions)
- **Daily RSS ingestion** - Fetch and filter new papers from RSS feeds
- **Daily Gmail processing** - Extract papers from email alerts
- **Daily global analysis** - Scan library for unprocessed papers and analyze with AI
- **Manual triggers** - All workflows support on-demand execution with dry-run mode
- **Log archiving** - 3-day retention with GitHub Step Summary

### Structured Output
- **Type-safe responses** - All tools return structured Pydantic models
- **Consistent error handling** - Standard `success`/`error` fields across all tools
- **Built-in pagination** - `has_more` and `next_offset` for large result sets
- **Machine-readable** - Easy integration with scripts and automation

### Flexible Access Methods
- Local method for offline access (no API key needed)
- Web API for cloud library access
- Smart update system that preserves your configuration

## Development

### Code Quality

The codebase follows strict cleanup practices:
- Unused modules are regularly removed
- No dead code is kept in the repository
- All files serve a documented purpose

## Quick Install

We recommend using `uv` for installation.

### Default Installation

```bash
uv tool install "git+https://github.com/54yyyu/zotero-mcp.git"
zotero-mcp setup  # Auto-configure for Opencode CLI
```

### Updating Your Installation

```bash
# Check for updates
zotero-mcp update --check-only

# Update to latest version (preserves all configurations)
zotero-mcp update
```

## Semantic Search

Zotero MCP includes powerful AI-powered semantic search capabilities that let you find research based on concepts and meaning, not just keywords.

### Setup Semantic Search

During setup or separately, configure semantic search:

```bash
# Configure during initial setup (recommended)
zotero-mcp setup

# Or configure semantic search separately
zotero-mcp setup --semantic-config-only
```

**Available Embedding Models:**
- **Default (all-MiniLM-L6-v2)**: Free, runs locally, good for most use cases
- **OpenAI**: Better quality, requires API key (`text-embedding-3-small` or `text-embedding-3-large`)
- **Gemini**: Better quality, requires API key (`models/text-embedding-004` or experimental models)

**Update Frequency Options:**
- **Manual**: Update only when you run `zotero-mcp update-db`
- **Auto on startup**: Update database every time the server starts
- **Daily**: Update once per day automatically
- **Every N days**: Set custom interval

### Using Semantic Search

After setup, initialize your search database:

```bash
# Build the semantic search database (fast, metadata-only)
zotero-mcp update-db

# Build with full-text extraction (slower, more comprehensive)
zotero-mcp update-db --fulltext

# Use your custom zotero.sqlite path
zotero-mcp update-db --fulltext --db-path "/Your_custom_path/zotero.sqlite"

# Check database status
zotero-mcp db-status
```

**Example Semantic Queries in your AI assistant:**
- *"Find research similar to machine learning concepts in neuroscience"*
- *"Papers that discuss climate change impacts on agriculture"*
- *"Research related to quantum computing applications"*
- *"Studies about social media influence on mental health"*
- *"Find papers conceptually similar to this abstract: [paste abstract]"*

## Setup & Usage

Full documentation is available at [Zotero MCP docs](https://stevenyuyy.us/zotero-mcp/).

**Requirements**
- Python 3.10+
- Zotero 7+ (for local API with full-text access)
- An MCP-compatible client

### For MCP CLI Tools

#### Configuration
After installation, run:

```bash
zotero-mcp setup
```

This will create a configuration file at `~/.config/zotero-mcp/config.json` with your settings.

#### Usage

1. Start Zotero desktop (make sure local API is enabled in preferences)
2. Configure your MCP client with the zotero-mcp command
3. Access the Zotero-MCP tools through your AI assistant

Example prompts:
- "Search my library for papers on machine learning"
- "Find recent articles I've added about climate change"
- "Summarize the key findings from my paper on quantum computing"
- "Extract all PDF annotations from my paper on neural networks"
- "Search my notes and annotations for mentions of 'reinforcement learning'"
- "Show me papers tagged '#Arm' excluding those with '#Crypt' in my library"
- "Export the BibTeX citation for papers on machine learning"
- **"Find papers conceptually similar to deep learning in computer vision"** *(semantic search)*

### For JSON Configuration (Generic)

#### Configuration
Add the following MCP server configuration to your client's settings:

```json
{
  "mcpServers": {
    "zotero": {
      "name": "zotero",
      "type": "stdio",
      "isActive": true,
      "command": "zotero-mcp",
      "args": [],
      "env": {
        "ZOTERO_LOCAL": "true"
      }
    }
  }
}
```

Most MCP clients provide a visual configuration method for MCP servers.

## Advanced Configuration

### Using Web API Instead of Local API

For accessing your Zotero library via the web API (useful for remote setups):

```bash
zotero-mcp setup --no-local --api-key YOUR_API_KEY --library-id YOUR_LIBRARY_ID
```

### Environment Variables

**Zotero Connection:**
- `ZOTERO_LOCAL=true`: Use the local Zotero API (default: false)
- `ZOTERO_API_KEY`: Your Zotero API key (Required if ZOTERO_LOCAL=false)
- `ZOTERO_LIBRARY_ID`: Your Zotero library ID (Required if ZOTERO_LOCAL=false)
- `ZOTERO_LIBRARY_TYPE`: The type of library (user or group, default: user)

**Semantic Search:**
- `ZOTERO_EMBEDDING_MODEL`: Embedding model to use (default, openai, gemini)
- `OPENAI_API_KEY`: Your OpenAI API key (for OpenAI embeddings)
- `OPENAI_EMBEDDING_MODEL`: OpenAI model name (text-embedding-3-small, text-embedding-3-large)
- `OPENAI_BASE_URL`: Custom OpenAI endpoint URL (optional, for use with compatible APIs)
- `GEMINI_API_KEY`: Your Gemini API key (for Gemini embeddings)
- `GEMINI_EMBEDDING_MODEL`: Gemini model name (models/text-embedding-004, etc.)
- `GEMINI_BASE_URL`: Custom Gemini endpoint URL (optional, for use with compatible APIs)
- `ZOTERO_DB_PATH`: Custom `zotero.sqlite` path (optional)

**Batch PDF Analysis:**
- `DEEPSEEK_API_KEY`: DeepSeek API key (required for batch analysis)
- `DEEPSEEK_MODEL`: Model name (default: deepseek-chat)

**RSS Integration:**
- `RSS_PROMPT`: AI filtering prompt for research interests
- `ZOTERO_INBOX_COLLECTION`: Target collection for new items (default: 00_INBOXS)

**Gmail Integration:**
- `GMAIL_TOKEN_JSON`: Gmail OAuth token (for GitHub Actions)
- `GMAIL_SENDER_FILTER`: Filter emails by sender (default: scholaralerts-noreply@google.com)

**Workflow:**
- `ZOTERO_PROCESSED_COLLECTION`: Target collection for analyzed items (default: 01_SHORTTERMS)
- `ENV_MODE`: Environment mode (development, testing, production)

### Command-Line Options

```bash
# Run the server directly
zotero-mcp serve

# Specify transport method
zotero-mcp serve --transport stdio|streamable-http|sse

# Setup and configuration
zotero-mcp setup --help                    # Get help on setup options
zotero-mcp setup --semantic-config-only    # Configure only semantic search
zotero-mcp setup-info                      # Show installation path and config info for MCP clients

# Updates and maintenance
zotero-mcp update                          # Update to latest version
zotero-mcp update --check-only             # Check for updates without installing
zotero-mcp update --force                  # Force update even if up to date

# Semantic search database management
zotero-mcp update-db                       # Update semantic search database (fast, metadata-only)
zotero-mcp update-db --fulltext            # Update with full-text extraction (comprehensive but slower)
zotero-mcp update-db --force-rebuild       # Force complete database rebuild
zotero-mcp update-db --fulltext --force-rebuild  # Rebuild with full-text extraction
zotero-mcp update-db --fulltext --db-path "your_path_to/zotero.sqlite" # Customize your zotero database path
zotero-mcp db-status                       # Show database status and info

# RSS feed management
zotero-mcp rss fetch                       # Fetch RSS feeds

# Gmail ingestion
zotero-mcp gmail process                   # Process Gmail alerts

# Global scan
zotero-mcp scan                            # Scan library for unprocessed papers

# General
zotero-mcp version                         # Show current version
```

## PDF Annotation Extraction

Zotero MCP includes advanced PDF annotation extraction capabilities:

- **Direct PDF Processing**: Extract annotations directly from PDF files, even if they're not yet indexed by Zotero
- **Enhanced Search**: Search through PDF annotations and comments
- **Image Annotation Support**: Extract image annotations from PDFs
- **Seamless Integration**: Works alongside Zotero's native annotation system

For optimal annotation extraction, it is **highly recommended** to install the [Better BibTeX plugin](https://retorque.re/zotero-better-bibtex/installation/) for Zotero.

The first time you use PDF annotation features, the necessary tools will be automatically downloaded.

## Available Tools

### Semantic Search Tools
- `zotero_semantic_search`: AI-powered similarity search with embedding models
- `zotero_update_database`: Manually update the semantic search database
- `zotero_database_status`: Check database status and configuration

### Search Tools
- `zotero_search`: Search your library by keywords
- `zotero_advanced_search`: Perform complex searches with multiple criteria
- `zotero_get_collections`: List collections
- `zotero_get_collection_items`: Get items in a collection
- `zotero_get_tags`: List all tags
- `zotero_get_recent`: Get recently added items
- `zotero_search_by_tag`: Search your library using custom tag filters

### Content Tools
- `zotero_get_metadata`: Get detailed metadata (supports BibTeX export via `format="bibtex"`)
- `zotero_get_fulltext`: Get full text content
- `zotero_get_children`: Get attachments and notes
- `zotero_get_bundle`: Get comprehensive item data bundle

### Annotation & Notes Tools
- `zotero_get_annotations`: Get annotations (including direct PDF extraction)
- `zotero_get_notes`: Retrieve notes from your Zotero library
- `zotero_search_notes`: Search in notes and annotations (including PDF-extracted)
- `zotero_create_note`: Create a new note for an item

### Batch Workflow Tools
- `zotero_prepare_analysis`: Collect PDF content and annotations for review
- `zotero_batch_analyze_pdfs`: Automatically analyze papers with AI (DeepSeek)
- `zotero_resume_workflow`: Resume interrupted batch analysis workflows
- `zotero_list_workflows`: View all workflow states and progress
- `zotero_find_collection`: Find collections by name with fuzzy matching

### RSS Tools
- `rss_fetch_feed`: Fetch and parse a single RSS feed
- `rss_fetch_from_opml`: Fetch multiple feeds from an OPML file

## Documentation

### Example Code
- [Batch Workflow Example](./examples/workflow_example.py) - Production-grade example showing how to use `WorkflowService` for batch PDF analysis with progress tracking, error handling, and checkpoint/resume support.

### Structured Responses
All tools return **structured Pydantic models** instead of formatted strings:
- **Type Safety** - Full type checking for inputs and outputs
- **Consistent Errors** - Standard `success`/`error` fields
- **Pagination** - Built-in `has_more` and `next_offset` support
- **Machine-Readable** - Easy to parse and integrate

**Example Response:**
```json
{
  "success": true,
  "query": "machine learning",
  "count": 10,
  "total_count": 45,
  "has_more": true,
  "next_offset": 10,
  "results": [
    {
      "key": "ABC123",
      "title": "Deep Learning for Computer Vision",
      "creators": ["Smith, J.", "Doe, A."],
      "year": 2023,
      "item_type": "journalArticle"
    }
  ]
}
```

### Additional Docs
- [Dependency Management](./docs/DEPENDENCY_MANAGEMENT.md) - Dependency audit and management guide
- [GitHub Actions Guide](./docs/GITHUB_ACTIONS_GUIDE.md) - Workflow setup and usage
- [Gmail Setup](./docs/GMAIL-SETUP.md) - Gmail API integration setup

## Troubleshooting

### General Issues
- **No results found**: Ensure Zotero is running and the local API is enabled. You need to toggle on `Allow other applications on this computer to communicate with Zotero` in Zotero preferences.
- **Can't connect to library**: Check your API key and library ID if using web API
- **Full text not available**: Make sure you're using Zotero 7+ for local full-text access
- **Local library limitations**: Some functionality (tagging, library modifications) may not work with local JS API. Consider using web library setup for full functionality.
- **Installation/search option switching issues**: Database problems from changing install methods or search options can often be resolved with `zotero-mcp update-db --force-rebuild`

### Semantic Search Issues
- **"Missing required environment variables" when running update-db**: Run `zotero-mcp setup` to configure your environment, or the CLI will automatically load settings from your MCP client config
- **Database update takes long**: By default, `update-db` is fast (metadata-only). For comprehensive indexing with full-text, use `--fulltext` flag. Use `--limit` parameter for testing: `zotero-mcp update-db --limit 100`
- **Semantic search returns no results**: Ensure the database is initialized with `zotero-mcp update-db` and check status with `zotero-mcp db-status`
- **Limited search quality**: For better semantic search results, use `zotero-mcp update-db --fulltext` to index full-text content (requires local Zotero setup)
- **OpenAI/Gemini API errors**: Verify your API keys are correctly set and have sufficient credits/quota

### Update Issues
- **Update command fails**: Check your internet connection and try `zotero-mcp update --force`
- **Configuration lost after update**: The update process preserves configs automatically, but check `~/.config/zotero-mcp/` for backup files

### Batch Analysis Issues
- **"DeepSeek API key not found"**: Set `DEEPSEEK_API_KEY` environment variable
- **Analysis returns empty notes**: Ensure PDFs are indexed with `zotero-mcp update-db --fulltext`
- **Workflow interrupted**: Use `zotero_list_workflows()` to find the workflow ID, then `zotero_resume_workflow()` to continue
- **Rate limit errors**: The workflow automatically retries with exponential backoff. Check your API provider's rate limits if persistent.

## License

MIT
