# Code Optimization Tasks

Generated from code quality analysis on 2026-01-31 using:
- Ruff refactor rules (PLR)
- Radon cyclomatic complexity analysis
- Radon maintainability index analysis

## Summary

- **Total issues found**: 68 refactor issues
- **Functions with high complexity (>15)**: 13 functions
- **Functions with medium complexity (10-15)**: 28 functions
- **Average complexity**: 3.97 (Good - below 10)
- **Maintainability index**: All files rated 'A' (Excellent)

## Critical Priority (Complexity > 20)

### 1. `cli.py` - `main()` - Complexity: 64
**Location**: `src/zotero_mcp/cli.py:76`
**Issues**:
- PLR0912: Too many branches (51 > 12)
- PLR0915: Too many statements (275 > 50)

**Recommendation**: This is the main CLI entry point. Consider:
- Extract command handlers into separate functions
- Create a command router/dispatcher pattern
- Split configuration validation into separate function
- Extract help text generation to utility

### 2. `semantic.py` - `_get_items_from_local_db()` - Complexity: 33
**Location**: `src/zotero_mcp/services/semantic.py:167`
**Issues**:
- PLR0912: Too many branches (20 > 12)
- PLR0915: Too many statements (66 > 50)

**Recommendation**: Break down into:
- Extract batch processing logic
- Create separate function for fulltext extraction
- Separate item filtering logic
- Simplify conditional branches

### 3. `scanner.py` - `scan_and_process()` - Complexity: 23
**Location**: `src/zotero_mcp/services/scanner.py:60`
**Issues**:
- PLR0912: Too many branches (21 > 12)
- PLR0915: Too many statements (69 > 50)

**Recommendation**:
- Extract item filtering logic
- Separate analysis triggering into helper function
- Create progress tracking helpers

### 4. `setup.py` - `setup_semantic_search()` - Complexity: 24
**Location**: `src/zotero_mcp/utils/setup.py:59`
**Issues**:
- PLR0912: Too many branches (21 > 12)
- PLR0915: Too many statements (90 > 50)

**Recommendation**:
- Extract embedding model download logic
- Separate ChromaDB initialization
- Create validation helper functions

### 5. `setup.py` - `main()` - Complexity: 23
**Location**: `src/zotero_mcp/utils/setup.py:293`
**Issues**:
- PLR0912: Too many branches (23 > 12)
- PLR0915: Too many statements (91 > 50)

**Recommendation**:
- Extract menu options to separate functions
- Create config editing helpers
- Separate test/validation logic

### 6. `gmail_service.py` - `_extract_item_from_row()` - Complexity: 22
**Location**: `src/zotero_mcp/services/gmail/gmail_service.py:127`
**Issues**:
- PLR0912: Too many branches (13 > 12)

**Recommendation**:
- Extract cell value parsing helpers
- Create link extraction utility
- Separate author/title parsing logic

### 7. `workflow.py` - `batch_analyze()` - Complexity: 25
**Location**: `src/zotero_mcp/services/workflow.py:154`
**Issues**:
- PLR0913: Too many arguments (15 > 5)
- PLR0912: Too many branches (14 > 12)
- PLR0915: Too many statements (54 > 50)

**Recommendation**:
- Create a configuration object for analysis parameters
- Extract progress reporting logic
- Separate batch processing from analysis

### 8. `bibtex.py` - `format_item()` - Complexity: 26
**Location**: `src/zotero_mcp/formatters/bibtex.py:111`
**Issues**:
- PLR0912: Too many branches (24 > 12)
- PLR0915: Too many statements (69 > 50)

**Recommendation**:
- Create formatter for each item type (article, book, etc.)
- Extract cite key generation logic
- Separate field formatting helpers

## High Priority (Complexity 15-20)

### 9. `updater.py` - `update_zotero_mcp()` - Complexity: 17
**Location**: `src/zotero_mcp/utils/updater.py:306`
**Issues**:
- PLR0911: Too many return statements (10 > 6)
- PLR0912: Too many branches (14 > 12)
- PLR0915: Too many statements (60 > 50)

**Recommendation**: Extract update methods for each installation type

### 10. `errors.py` - `handle_error()` - Complexity: 15
**Location**: `src/zotero_mcp/utils/errors.py:64`
**Issues**:
- PLR0911: Too many return statements (8 > 6)

**Recommendation**: Use early returns or strategy pattern for error handling

### 11. `rss_service.py` - `create_zotero_item()` - Complexity: 17
**Location**: `src/zotero_mcp/services/rss/rss_service.py:303`
**Issues**:
- PLR0911: Too many return statements (7 > 6)

**Recommendation**: Simplify return logic with early returns

### 12. `rss_filter.py` - `_parse_keywords_json()` - Complexity: 17
**Location**: `src/zotero_mcp/services/rss/rss_filter.py:183`

**Recommendation**: Extract keyword parsing logic

### 13. `llm.py` - `analyze_paper()` - Complexity: 17
**Location**: `src/zotero_mcp/clients/llm.py:98`
**Issues**:
- PLR0913: Too many arguments (8 > 5)

**Recommendation**: Create analysis configuration object

## Medium Priority (Complexity 10-15)

### 14-41. Additional Functions Requiring Review

The following 28 functions have complexity between 10-15 and should be reviewed for potential simplification:

1. `crossref.py` - `CrossrefWork.from_api_response()` - C (17)
2. `crossref.py` - `CrossrefWork.to_zotero_item()` - C (12)
3. `openalex.py` - `OpenAlexWork.from_api_response()` - C (14)
4. `openalex.py` - `OpenAlexWork.to_zotero_item()` - C (13)
5. `metadata.py` - `ArticleMetadata` class - C (17)
6. `metadata.py` - `ArticleMetadata.to_zotero_item()` - C (16)
7. `local_db.py` - `_extract_fulltext()` - C (14)
8. `local_db.py` - `ZoteroItem.get_searchable_text()` - B (8)
9. `cli_llm.py` - `analyze_paper()` - C (17)
10. `gmail.py` - `_get_credentials()` - D (21)
11. `markdown.py` - `format_item()` - C (15)
12. `workflow.py` - `_analyze_single_item()` - C (20)
13. `workflow.py` - `prepare_analysis()` - C (12)
14. `search.py` - `search_by_tag()` - C (12)
15. `search.py` - `search_items()` - B (6)
16. `batch_loader.py` - `get_item_bundle_parallel()` - C (17)
17. `rss_service.py` - `_fetch_sync()` - C (16)
18. `rss_service.py` - `process_rss_workflow()` - C (16)
19. `rss_service.py` - `_parse_creator_string()` - C (17)
20. `rss_service.py` - `_extract_doi()` - B (10)
21. `rss_filter.py` - `_matches_keyword()` - C (15)
22. `rss_filter.py` - `extract_keywords()` - C (12)
23. `rss_filter.py` - `_get_word_stem()` - C (12)
24. `rss_filter.py` - `_parse_cli_filter_output()` - C (12)
25. `gmail_service.py` - `process_gmail_workflow()` - C (17)
26. `gmail_service.py` - `parse_html_table()` - B (10)
27. `gmail_service.py` - `_extract_items_from_divs()` - B (10)
28. `updater.py` - `detect_installation_method()` - C (15)

## Low Priority (Code Quality Issues)

### Magic Values (PLR2004)

**Found**: 24 instances of magic numbers in comparisons

**Examples**:
- `15` (timeout/size limits) - appears 5 times
- `10` (batch sizes) - appears 4 times
- `500` (max items) - appears 4 times
- `404` (HTTP status) - appears 2 times
- `200` (HTTP status) - appears 1 time
- Other constants scattered throughout code

**Recommendation**: Extract to module-level constants:
```python
# Example for gmail_service.py
DEFAULT_BATCH_SIZE = 10
MAX_EMAILS_PER_REQUEST = 500
REQUEST_TIMEOUT_SECONDS = 15
MAX_ATTACHMENT_SIZE = 200
```

### Too Many Arguments (PLR0913)

**Found**: 9 functions with >5 arguments

**Recommendation**: Use configuration objects or dataclasses:
```python
@dataclass
class AnalysisConfig:
    temperature: float
    max_tokens: int
    model: str
    timeout: int
    retry_count: int
```

### Too Many Return Statements (PLR0911)

**Found**: 6 functions with >6 returns

**Files**:
- `services/rss/rss_service.py:303` - 7 returns
- `services/semantic.py:117` - 9 returns
- `utils/errors.py:64` - 8 returns
- `utils/updater.py:306` - 10 returns
- `updater.py:306` - 10 returns
- `rss_service.py:303` - 7 returns

**Recommendation**: Use guard clauses or extract to multiple functions

### Code Pattern Improvements

#### 1. PLR1714: Merge Multiple Comparisons
**Location**: `services/checkpoint.py:219`
```python
# Current:
if status_filter == "all" or status_filter == state.status:

# Suggested:
if status_filter in ("all", state.status):
```

#### 2. PLR5501: Use elif Instead of Else + If
**Location**: `services/item.py:168`
```python
# Current:
else:
    if condition:

# Suggested:
elif condition:
```

## Maintainability Analysis

**Excellent News**: All 68 files received an 'A' maintainability rating!

The codebase has excellent maintainability despite some high-complexity functions. This suggests:
- Good naming conventions
- Proper documentation
- Clean code structure
- Good separation of concerns

## Next Steps

### Immediate Actions (Week 1)
1. Refactor `cli.py:main()` - split into command handlers
2. Refactor `semantic.py:_get_items_from_local_db()` - extract batch processing
3. Extract all magic values to named constants

### Short-term Actions (Week 2-3)
4. Reduce complexity in scanner and setup utilities
5. Create configuration objects for functions with many arguments
6. Simplify return statement logic

### Long-term Actions (Month 2)
7. Review all functions with complexity 10-15
8. Add type hints where missing (use ty or mypy)
9. Consider extracting complex formatting logic to separate modules

## Notes

- **No duplicate code patterns were detected** by Ruff's PLR rules
- **All maintainability indexes are rated 'A'** - excellent code quality
- **Average complexity (3.97)** is well within acceptable range (<10)
- Main concerns are a few highly complex functions that could benefit from refactoring
- Most issues are in CLI/setup code which is expected to have more branches

## Tools Used

```bash
# Ruff refactor rules
uv run ruff check src/zotero_mcp/ --select PLR --output-format=concise

# Radon cyclomatic complexity
uv run radon cc src/zotero_mcp/ -a -s

# Radon maintainability index
uv run radon mi src/zotero_mcp/
```

## Complexity Ratings

- **A (1-5)**: Low risk - simple, clear code
- **B (6-10)**: Moderate risk - somewhat complex
- **C (11-20)**: High risk - complex, should consider refactoring
- **D (21-30)**: Very high risk - very complex, should refactor
- **F (31+)**: Extreme risk - extremely complex, must refactor

**Current Distribution**:
- A (1-5): 498 functions (90.9%)
- B (6-10): 37 functions (6.8%)
- C (11-20): 11 functions (2.0%)
- D (21-30): 5 functions (0.9%)
- F (31+): 2 functions (0.4%)

**Assessment**: The codebase is in excellent shape with 97.7% of functions at acceptable complexity levels (A-C). The 7 functions rated D/F should be prioritized for refactoring.
