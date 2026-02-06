# paper-feed

Academic paper collection framework supporting RSS feeds and Gmail alerts.

## Installation

### Local Development Install

```bash
# Clone repository (if not already cloned)
git clone <repository-url>
cd paper-feed

# Install in editable mode
pip install -e .
```

### With Optional Dependencies

```bash
# Install with Gmail support
pip install -e ".[gmail]"

# Install with LLM-based filtering
pip install -e ".[llm]"

# Install with Zotero export
pip install -e ".[zotero]"

# Install everything
pip install -e ".[all]"
```

## Quick Start

```python
from paper_feed import RSSSource, FilterPipeline, JSONAdapter

# Fetch from arXiv
source = RSSSource("https://arxiv.org/rss/cs.AI")
papers = await source.fetch_papers()

# Filter
criteria = FilterCriteria(keywords=["machine learning"])
filtered = await FilterPipeline().filter(papers, criteria)

# Export
await JSONAdapter().export(filtered.papers, "papers.json")
```

## Features

- RSS feed parsing (arXiv, bioRxiv, Nature, Science)
- Gmail alert parsing (Google Scholar, journal TOCs)
- Multi-stage filtering (keyword + AI semantic)
- Flexible export adapters (Zotero, JSON, etc.)

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check
```

## License

MIT
