# Scripts Analysis (2025-01-30)

## Current Scripts in src/scripts/

### 1. **analyze_new_items.py**
- **Purpose**: Automated new item analysis (staging → processing)
- **Source Collection**: "00_INBOXS"
- **Destination Collection**: "01_SHORTTERMS"
- **Workflow**:
  1. Filters items with PDF but no analysis tag
  2. Analyzes using WorkflowService with DeepSeek AI
  3. Moves processed items to destination collection
- **Uses**: WorkflowService, AnalysisStatusService, DataAccessService
- **Features**:
  - DRY_RUN mode support
  - MAX_ITEMS limit via environment variable
  - Debug mode
  - Progress tracking
  - Skips already analyzed items (using AnalysisStatusService)
- **GitHub Actions**: Not referenced in any workflow
- **Documentation**: Not referenced in docs
- **Status**: Standalone utility script, currently unused

### 2. **auto_analyze.py**
- **Purpose**: Automated collection analysis
- **Target Collection**: "1 - 中转过滤：较短期"
- **Workflow**:
  1. Filters items with PDF attachments
  2. Analyzes using WorkflowService with DeepSeek AI
  3. Does NOT move items (stays in same collection)
- **Uses**: WorkflowService, DataAccessService
- **Features**:
  - Skip items without PDF
  - Fixed MAX_ITEMS = None (process all)
  - No DRY_RUN mode (always executes)
  - No collection movement
- **GitHub Actions**: Not referenced in any current workflow
- **Documentation**: Referenced in `docs/GITHUB-ACTIONS-SETUP.md` (outdated)
- **Status**: Legacy script, replaced by CLI commands

### 3. **organize_existing_items.py**
- **Purpose**: Batch organization and re-analysis of existing items
- **Excluded Collection**: "00_INBOXS"
- **Workflow**:
  1. Scans all collections except excluded collection
  2. Filters items with PDF + notes but no tags (legacy state)
  3. Deletes old notes
  4. Re-analyzes using WorkflowService
  5. Adds "AI分析" tag to processed items
- **Uses**: WorkflowService, AnalysisStatusService, DataAccessService
- **Features**:
  - DRY_RUN mode support
  - MAX_ITEMS limit via environment variable
  - Debug mode
  - Progress tracking
  - Per-collection batch processing
- **GitHub Actions**: Not referenced in any workflow
- **Documentation**: Not referenced in docs
- **Status**: Standalone utility script for legacy data cleanup

## Functional Overlap Analysis

### Similarities
All three scripts:
1. Use `WorkflowService.batch_analyze()` for analysis
2. Use `DataAccessService` for Zotero operations
3. Filter items for PDF attachments
4. Use DeepSeek AI as LLM provider
5. Skip existing analysis (except organize_existing_items which deletes notes)
6. Include progress callbacks

### Differences

| Feature | analyze_new_items.py | auto_analyze.py | organize_existing_items.py |
|---------|---------------------|-----------------|---------------------------|
| Source | Single collection | Single collection | All collections (except one) |
| Destination | Moves to target | Stays in place | Stays in place |
| Note handling | Creates new notes | Creates new notes | Deletes old + creates new |
| Tag handling | Uses AnalysisStatusService | Skip existing | Adds "AI分析" tag |
| DRY_RUN | Yes | No | Yes |
| MAX_ITEMS | Via env var | Hardcoded None | Via env var |
| Use case | New items pipeline | Simple collection scan | Legacy data cleanup |

## Current Usage Analysis

### GitHub Actions
- **global-analysis.yml**: Uses `zotero-mcp scan` CLI command (NOT scripts)
- **rss-ingestion.yml**: Uses `zotero-mcp rss-fetch` CLI command (NOT scripts)
- **gmail-ingestion.yml**: Uses MCP tools for analysis (NOT scripts)
- **Conclusion**: No workflows use these scripts

### CLI Commands
The project has a built-in CLI command that replaces these scripts:
- `zotero-mcp scan --limit <n> --target-collection <name> --dry-run`
- Implemented in `GlobalScanner` service
- Supports priority collection scanning (00_INBOXS first)
- Supports target collection movement
- Supports dry-run mode
- Multi-stage scanning (default → priority collections → global scan)

### Documentation
- `docs/GITHUB-ACTIONS-SETUP.md`: References `auto_analyze.py` (outdated)
- No user-facing documentation for other scripts
- Scripts are mentioned in task plan documents only

## Recommendations

### Option A: Keep as User-Facing Utilities
**Pros**:
- Users can run scripts manually for one-off operations
- More flexible than CLI for custom workflows

**Cons**:
- Maintenance burden (3 scripts to update)
- Redundant with CLI functionality
- No evidence of actual usage

### Option B: Consolidate into Single Script with CLI Arguments
**Pros**:
- Single codebase to maintain
- Flexible via command-line arguments
- Can cover all three use cases

**Cons**:
- Still need to maintain parallel to CLI
- Duplication of effort with `GlobalScanner`

### Option C: Remove Scripts (RECOMMENDED)
**Pros**:
- Eliminates code duplication
- Reduces maintenance burden
- CLI provides equivalent or better functionality:
  - `zotero-mcp scan` replaces all three scripts
  - More flexible (priority collections, global scan, target collection)
  - Better integration with project architecture
  - Already tested and documented

**Cons**:
- Users who manually run scripts would need to switch to CLI

### Option D: Keep organize_existing_items.py Only
**Rationale**:
- This script has unique functionality (deleting old notes + re-analysis)
- Useful for legacy data cleanup operations
- Not easily replicated by current CLI
- Could be converted to CLI command if needed

## Decision Matrix

| Criterion | analyze_new_items.py | auto_analyze.py | organize_existing_items.py |
|-----------|---------------------|-----------------|---------------------------|
| Used by workflows | No | No | No |
| Documented for users | No | Outdated | No |
| Unique functionality | No | No | Yes (note deletion) |
| Replaced by CLI | Yes | Yes | Partially |
| Maintenance burden | High | High | Medium |

## Final Recommendation

**Phase 1: Remove Redundant Scripts**
- Delete `src/scripts/analyze_new_items.py` (replaced by `zotero-mcp scan`)
- Delete `src/scripts/auto_analyze.py` (replaced by `zotero-mcp scan`)
- Update `docs/GITHUB-ACTIONS-SETUP.md` to remove references

**Phase 2: Evaluate organize_existing_items.py**
- Keep for now (unique note deletion functionality)
- Consider converting to CLI command: `zotero-mcp reanalyze --delete-old-notes`
- Or remove if legacy cleanup is no longer needed

**Phase 3: Documentation Update**
- Remove all script references from documentation
- Update README.md to use CLI commands only
- Update CLAUDE.md to remove script mentions

## Implementation Plan

1. Delete `analyze_new_items.py` and `auto_analyze.py`
2. Update `docs/GITHUB-ACTIONS-SETUP.md` to reference `zotero-mcp scan`
3. Keep `organize_existing_items.py` for now (evaluate future use)
4. Commit with message: "refactor: remove redundant analysis scripts replaced by CLI"

## Notes

- All scripts use the same underlying `WorkflowService.batch_analyze()` method
- CLI `zotero-mcp scan` command provides equivalent functionality with more flexibility
- No evidence these scripts are actively used by anyone
- Better to have single source of truth (CLI) than multiple redundant scripts
