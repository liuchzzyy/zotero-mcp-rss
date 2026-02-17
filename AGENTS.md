# Repository Guidelines

## Project Structure & Module Organization
- Main code lives in `src/zotero_mcp/`.
- Core layers:
  - `services/` for business workflows (`scanner.py`, `workflow.py`, `services/zotero/*`).
  - `clients/` for external systems (Zotero API/local DB, LLM, metadata, vector DB).
  - `handlers/` for MCP tool/prompt dispatch.
  - `models/` for Pydantic schemas and shared operation params.
- Tests are in `tests/` with service-focused subfolders (for example `tests/services/zotero/`).
- Automation/workflows live in `.github/workflows/`.
- Utility scripts are in `scripts/`; design and planning notes are in `docs/plans/`.

## Build, Test, and Development Commands
- `uv run zotero-mcp serve`  
  Run the MCP server locally over stdio.
- `uv run pytest -q`  
  Run full test suite.
- `uv run pytest tests/services/test_workflow.py -q`  
  Run targeted tests while iterating.
- `uv run ruff check src/ tests/`  
  Run lint checks.
- `uv run ruff check --fix src/ tests/`  
  Auto-fix safe lint issues.

## Coding Style & Naming Conventions
- Python 3.12+, 4-space indentation, type hints required for new/changed code.
- Follow Ruff defaults configured in `pyproject.toml` (line length 88).
- Naming:
  - modules/functions: `snake_case`
  - classes: `PascalCase`
  - constants: `UPPER_SNAKE_CASE`
- Keep service entrypoints explicit: validate inputs via models, avoid implicit parameter behavior.

## Testing Guidelines
- Framework: `pytest` with `pytest-asyncio`.
- Add tests for each behavior change, especially:
  - parameter validation boundaries
  - workflow branch behavior (dry-run, limits, skip paths)
  - regression cases for fixed bugs.
- Test files should be named `test_*.py`; test functions should describe expected behavior.

## Commit & Pull Request Guidelines
- Use Conventional Commit style seen in history, e.g.:
  - `feat(cli): add clean-tags command`
  - `fix(llm): remove fulltext limit`
  - `ci(note-update): align defaults`
- PRs should include:
  - concise problem/solution summary
  - impacted paths (for example `services/zotero/metadata_update_service.py`)
  - test evidence (`pytest`/`ruff` output)
  - workflow impact if `.github/workflows/*` changed.

## Security & Configuration Tips
- Never commit secrets. Use environment variables (`ZOTERO_API_KEY`, `OPENAI_API_KEY`, etc.).
- Use `.env.example` as the template for local configuration.
