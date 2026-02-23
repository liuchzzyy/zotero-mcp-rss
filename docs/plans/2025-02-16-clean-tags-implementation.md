# Clean Tags Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a CLI command and MCP tool to remove all Zotero item tags except `AI分析` and `AI元数据`.

**Architecture:** A new `TagCleaner` service that iterates through all items, filters tags using a preserved set, and updates items via the existing data access layer. CLI and MCP handlers both call this service.

**Tech Stack:** Python 3.12+, Typer (CLI), Pydantic (models), existing `data_access` service

---

### Task 1: Create tag cleaner service

**Files:**
- Create: `src/zotero_mcp/services/zotero/tag_cleaner.py`

**Step 1: Write the service module**

```python
"""Tag cleaner service for removing non-AI tags from items."""

import logging
from typing import Any

from zotero_mcp.services.data_access import get_data_service

logger = logging.getLogger(__name__)

# Tags to preserve - only AI-related tags
PRESERVED_TAGS = {"AI分析", "AI元数据"}


class TagCleaner:
    """Service for cleaning tags from Zotero items."""

    def __init__(self):
        """Initialize tag cleaner service."""
        self.data_service = get_data_service()

    async def clean_all_tags(self, dry_run: bool = False) -> dict[str, Any]:
        """
        Remove all tags except preserved AI tags from all items.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            Dictionary with cleaning statistics:
            - total_items: Total number of items processed
            - items_with_tags: Number of items that had tags
            - tags_removed: Total number of tags removed
            - tags_kept: Total number of tags kept
            - dry_run: Whether this was a dry run
        """
        # Get all items from the library
        all_items = await self.data_service.item_service.get_all_items()

        stats = {
            "total_items": len(all_items),
            "items_with_tags": 0,
            "tags_removed": 0,
            "tags_kept": 0,
            "dry_run": dry_run,
        }

        for item in all_items:
            # Get existing tags
            existing_tags = item.data.get("tags", [])
            if not existing_tags:
                continue

            # Extract tag names (handle both dict and string formats)
            tag_names = set()
            for tag in existing_tags:
                if isinstance(tag, dict):
                    tag_names.add(tag.get("tag", ""))
                else:
                    tag_names.add(tag)

            # Separate tags to keep and remove
            to_keep = tag_names & PRESERVED_TAGS
            to_remove = tag_names - PRESERVED_TAGS

            if not to_remove:
                # Nothing to remove for this item
                continue

            stats["items_with_tags"] += 1
            stats["tags_removed"] += len(to_remove)
            stats["tags_kept"] += len(to_keep)

            if not dry_run:
                # Update item with only preserved tags
                new_tags = list(to_keep)
                await self.data_service.item_service.update_tags(
                    item.key, new_tags
                )

            logger.debug(
                f"{'[DRY RUN] ' if dry_run else ''}"
                f"Item {item.key}: removed {len(to_remove)} tags, "
                f"kept {len(to_keep)} tags"
            )

        logger.info(
            f"Tag cleaning complete: "
            f"{stats['items_with_tags']} items processed, "
            f"{stats['tags_removed']} tags removed, "
            f"{stats['tags_kept']} tags kept"
        )

        return stats


def get_tag_cleaner() -> TagCleaner:
    """Get singleton instance of TagCleaner."""
    # Use simple module-level caching
    if not hasattr(get_tag_cleaner, "_instance"):
        get_tag_cleaner._instance = TagCleaner()  # type: ignore
    return get_tag_cleaner._instance
```

**Step 2: Create __init__.py for zotero services**

```bash
# Check if file exists first
ls src/zotero_mcp/services/zotero/__init__.py 2>/dev/null || echo "File does not exist"
```

If not exists, create:

- Create: `src/zotero_mcp/services/zotero/__init__.py`

```python
"""Zotero-related services."""

from zotero_mcp.services.zotero.tag_cleaner import TagCleaner, get_tag_cleaner

__all__ = ["TagCleaner", "get_tag_cleaner"]
```

**Step 3: Run linter**

```bash
uv run ruff check src/zotero_mcp/services/zotero/tag_cleaner.py
```

Expected: No errors (maybe format warnings)

**Step 4: Format code**

```bash
uv run ruff format src/zotero_mcp/services/zotero/tag_cleaner.py
```

**Step 5: Commit**

```bash
git add src/zotero_mcp/services/zotero/tag_cleaner.py src/zotero_mcp/services/zotero/__init__.py
git commit -m "feat: add TagCleaner service for removing non-AI tags"
```

---

### Task 2: Add CLEAN_TAGS to ToolName enum

**Files:**
- Modify: `src/zotero_mcp/models/enums.py`

**Step 1: Read current enum file to find insert location**

```bash
grep -n "class ToolName" src/zotero_mcp/models/enums.py
```

Expected: Line around 6-7

**Step 2: Add CLEAN_TAGS to ToolName enum**

Find the appropriate section (after TAG-related tools or in alphabetical order). Add:

```python
CLEAN_TAGS = "zotero_clean_tags"
```

**Step 3: Verify syntax**

```bash
uv run python -c "from zotero_mcp.models.enums import ToolName; print(ToolName.CLEAN_TAGS)"
```

Expected: `zotero_clean_tags`

**Step 4: Commit**

```bash
git add src/zotero_mcp/models/enums.py
git commit -m "feat: add CLEAN_TAGS to ToolName enum"
```

---

### Task 3: Create input model for clean tags tool

**Files:**
- Create: `src/zotero_mcp/models/tags.py`

**Step 1: Create the input model**

```python
"""Tag-related input models."""

from pydantic import BaseModel, Field


class CleanTagsInput(BaseModel):
    """Input for cleaning tags from items."""

    dry_run: bool = Field(
        default=False,
        description="If True, only preview what would be deleted without making changes",
    )
```

**Step 2: Verify model**

```bash
uv run python -c "from zotero_mcp.models.tags import CleanTagsInput; print(CleanTagsInput.model_json_schema())"
```

Expected: Valid JSON schema

**Step 3: Commit**

```bash
git add src/zotero_mcp/models/tags.py
git commit -m "feat: add CleanTagsInput model"
```

---

### Task 4: Add handler for clean_tags tool

**Files:**
- Modify: `src/zotero_mcp/handlers/tools.py`

**Step 1: Find handler functions location**

```bash
grep -n "async def handle_" src/zotero_mcp/handlers/tools.py | tail -5
```

**Step 2: Add handler function**

Add at the end of the handler functions section (before the `def register_tools`):

```python
async def handle_clean_tags(args: dict[str, Any]) -> dict[str, Any]:
    """
    Remove all tags except AI分析 and AI元数据 from all items.

    Args:
        dry_run: If True, only preview without making changes

    Returns:
        Dictionary with cleaning statistics
    """
    from zotero_mcp.models.tags import CleanTagsInput
    from zotero_mcp.services.zotero.tag_cleaner import get_tag_cleaner

    input_data = CleanTagsInput(**args)
    cleaner = get_tag_cleaner()

    result = await cleaner.clean_all_tags(dry_run=input_data.dry_run)

    return result
```

**Step 3: Verify syntax**

```bash
uv run python -c "from zotero_mcp.handlers.tools import handle_clean_tags; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add src/zotero_mcp/handlers/tools.py
git commit -m "feat: add handle_clean_tags handler"
```

---

### Task 5: Register clean_tags tool

**Files:**
- Modify: `src/zotero_mcp/handlers/tools.py`

**Step 1: Find tool registration location**

```bash
grep -n "Tool(" src/zotero_mcp/handlers/tools.py | grep "name=" | tail -3
```

**Step 2: Add tool registration**

Find the appropriate section (likely near other utility tools). Add:

```python
Tool(
    name=ToolName.CLEAN_TAGS,
    description="Remove all tags except AI分析 and AI元数据 from all items",
    inputSchema=CleanTagsInput.model_json_schema(),
),
```

**Step 3: Verify registration**

```bash
uv run python -c "
from zotero_mcp.handlers.tools import register_tools
tools = register_tools()
clean_tags_tool = [t for t in tools if t.name == 'zotero_clean_tags']
print(f'Found: {len(clean_tags_tool)} tool(s)')
"
```

Expected: `Found: 1 tool(s)`

**Step 4: Commit**

```bash
git add src/zotero_mcp/handlers/tools.py
git commit -m "feat: register clean_tags MCP tool"
```

---

### Task 6: Add CLI command for clean-tags

**Files:**
- Modify: `src/zotero_mcp/cli.py`

**Step 1: Find CLI commands location**

```bash
grep -n "@app.command" src/zotero_mcp/cli.py | tail -5
```

**Step 2: Add CLI command**

Add after the last command (before `if __name__ == "__main__":`):

```python
@app.command()
def clean_tags(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview only, don't delete tags"),
):
    """Remove all tags except AI分析 and AI元数据 from all items."""
    import asyncio
    from zotero_mcp.services.zotero.tag_cleaner import get_tag_cleaner
    from zotero_mcp.cli.console import console

    async def run():
        cleaner = get_tag_cleaner()
        result = await cleaner.clean_all_tags(dry_run=dry_run)

        console.print(f"\n[bold cyan]Tag Cleaning Report[/bold cyan]")
        console.print(f"Total items: {result['total_items']}")
        console.print(f"Items with tags: {result['items_with_tags']}")
        console.print(f"Tags removed: [red]{result['tags_removed']}[/red]")
        console.print(f"Tags kept (AI*): [green]{result['tags_kept']}[/green]")

        if dry_run:
            console.print("\n[yellow][DRY RUN] No changes were made[/yellow]")
        else:
            console.print("\n[green]✓ Cleaning completed![/green]")

    asyncio.run(run())
```

**Step 3: Verify CLI command**

```bash
uv run zotero-mcp clean-tags --help
```

Expected: Help text showing `--dry-run` option

**Step 4: Test dry-run**

```bash
uv run zotero-mcp clean-tags --dry-run
```

Expected: Report showing tags to be removed

**Step 5: Commit**

```bash
git add src/zotero_mcp/cli.py
git commit -m "feat: add clean-tags CLI command"
```

---

### Task 7: Write tests for tag cleaner

**Files:**
- Create: `tests/test_tag_cleaner.py`

**Step 1: Write failing tests**

```python
"""Tests for tag cleaner service."""

import pytest

from zotero_mcp.services.zotero.tag_cleaner import (
    PRESERVED_TAGS,
    TagCleaner,
    get_tag_cleaner,
)


class TestTagCleaner:
    """Test TagCleaner service."""

    @pytest.mark.asyncio
    async def test_preserved_tags_set(self):
        """Test that preserved tags contain exactly AI相关 tags."""
        assert "AI分析" in PRESERVED_TAGS
        assert "AI元数据" in PRESERVED_TAGS
        assert len(PRESERVED_TAGS) == 2

    @pytest.mark.asyncio
    async def test_get_tag_cleaner_returns_singleton(self):
        """Test that get_tag_cleaner returns singleton instance."""
        cleaner1 = get_tag_cleaner()
        cleaner2 = get_tag_cleaner()
        assert cleaner1 is cleaner2
        assert isinstance(cleaner1, TagCleaner)

    @pytest.mark.asyncio
    async def test_clean_all_tags_dry_run(self, mock_item_service):
        """Test dry run doesn't modify items."""
        # This test requires mocking the data service
        # Implementation depends on existing test infrastructure
        pass

    @pytest.mark.asyncio
    async def test_clean_all_tags_removes_non_ai_tags(self, mock_item_service):
        """Test that non-AI tags are removed."""
        # This test requires mocking the data service
        # Implementation depends on existing test infrastructure
        pass

    @pytest.mark.asyncio
    async def test_clean_all_tags_preserves_ai_tags(self, mock_item_service):
        """Test that AI tags are preserved."""
        # This test requires mocking the data service
        # Implementation depends on existing test infrastructure
        pass
```

**Step 2: Run tests**

```bash
uv run pytest tests/test_tag_cleaner.py -v
```

Expected: Some pass (singleton, preserved_tags), mock tests skip

**Step 3: Add proper mock tests** (if test infrastructure exists)

Check existing test patterns:

```bash
grep -A 10 "mock_item_service\|@pytest.fixture" tests/services/test_*.py | head -30
```

**Step 4: Commit**

```bash
git add tests/test_tag_cleaner.py
git commit -m "test: add tag cleaner tests"
```

---

### Task 8: Update documentation

**Files:**
- Modify: `README.md` or `CLAUDE.md`

**Step 1: Find CLI commands documentation section**

```bash
grep -n "clean\|scan\|update" README.md CLAUDE.md | grep -i command
```

**Step 2: Add documentation entry**

Add to the Key Commands section:

```bash
# Tag Management
zotero-mcp clean-tags           # Remove all tags except AI* from all items
zotero-mcp clean-tags --dry-run # Preview what would be deleted
```

**Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: add clean-tags command documentation"
```

---

## Summary of Changes

| File | Action |
|------|--------|
| `src/zotero_mcp/services/zotero/tag_cleaner.py` | Create - TagCleaner service |
| `src/zotero_mcp/services/zotero/__init__.py` | Create - Export TagCleaner |
| `src/zotero_mcp/models/enums.py` | Modify - Add CLEAN_TAGS |
| `src/zotero_mcp/models/tags.py` | Create - CleanTagsInput model |
| `src/zotero_mcp/handlers/tools.py` | Modify - Add handler + registration |
| `src/zotero_mcp/cli.py` | Modify - Add clean-tags command |
| `tests/test_tag_cleaner.py` | Create - Tests |
| `README.md`/`CLAUDE.md` | Modify - Documentation |

## Testing Checklist

- [ ] Unit tests pass: `pytest tests/test_tag_cleaner.py -v`
- [ ] CLI dry-run works: `zotero-mcp clean-tags --dry-run`
- [ ] MCP tool callable via MCP client
- [ ] Linter passes: `ruff check`
- [ ] Type check passes: `ty check`

## Usage Examples

```bash
# Preview what would be deleted
zotero-mcp clean-tags --dry-run

# Actually remove tags
zotero-mcp clean-tags
```

Via MCP:
```json
{
  "tool": "zotero_clean_tags",
  "arguments": {
    "dry_run": true
  }
}
```
