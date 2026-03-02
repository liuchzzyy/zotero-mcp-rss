# Tag System Design for Materials Science/Battery Research

**Date:** 2025-02-16
**Status:** Design Approved
**Author:** User + Claude

## Overview

A hierarchical tagging system for Zotero literature management, tailored for materials science/battery research. The system focuses on three core needs:

1. **Workflow status tracking** - Track reading and citation progress
2. **Functional classification** - Organize by usage (thesis chapters, papers)
3. **Innovation dimension tagging** - Categorize by prep, characterization, performance, mechanism, theory

## Tag Structure

### 1. Status Tags (`status/`)

Track the lifecycle of a literature item.

| Tag | Description |
|-----|-------------|
| `status/new` | Unread, newly imported |
| `status/reading` | Currently reading |
| `status/read` | Read completed |
| `status/todo` | To be cited |
| `status/cited` | Already cited |
| `status/skip` | Will not cite |
| `status/archive` | Archived, no longer relevant |

**Behavior:** Status tags are mutually exclusive. Setting a new status automatically removes the old one.

### 2. Use Tags (`use/`)

Classify literature by its intended use in writing.

| Tag | Description |
|-----|-------------|
| `use/intro` | Introduction material |
| `use/related` | Related work material |
| `use/discuss` | Discussion material |
| `use/reference` | Method/data reference |
| `use/compare` | Comparison study |

**Behavior:** Multiple use tags can be applied to a single item.

### 3. Focus Tags (`focus/`)

Categorize by innovation dimensions - the core classification for materials science/battery research.

#### Preparation (`focus/prep/`)

| Tag | Description |
|-----|-------------|
| `focus/prep/synth` | Synthesis methods (sol-gel, hydrothermal, solid-state, etc.) |
| `focus/prep/coat` | Coating/surface modification |
| `focus/prep/dope` | Doping |
| `focus/prep/nano` | Nanostructure design |

#### Characterization (`focus/char/`)

| Tag | Description |
|-----|-------------|
| `focus/char/struct` | Structure characterization (XRD, TEM, SEM, AFM) |
| `focus/char/surf` | Surface characterization (XPS, BET, TGA-DSC) |
| `focus/char/electro` | Electrochemical characterization (EIS, CV, GCD, dQ/dV) |
| `focus/char/spec` | Spectroscopy (XAFS, Raman, FTIR) |

#### Performance (`focus/perf/`)

| Tag | Description |
|-----|-------------|
| `focus/perf/energy` | Energy density |
| `focus/perf/power` | Power density |
| `focus/perf/cycle` | Cycle life |
| `focus/perf/rate` | Rate capability |

#### Mechanism (`focus/mech/`)

| Tag | Description |
|-----|-------------|
| `focus/mech/react` | Reaction mechanism (intercalation, conversion, alloying, deposition) |
| `focus/mech/decay` | Degradation mechanism |
| `focus/mech/inter` | Interface mechanism |

#### Theory (`focus/theory/`)

| Tag | Description |
|-----|-------------|
| `focus/theory/dft` | DFT calculations |
| `focus/theory/md` | Molecular dynamics |
| `focus/theory/ml` | Machine learning |

## Example Usage

A paper on **sol-gel prepared nano-porous LiFePO4 cathode material** would be tagged:

```
status/read
use/related
focus/prep/synth
focus/prep/nano
focus/char/electro
focus/perf/cycle
focus/mech/react
```

## MCP Tools

| Tool Name | Description |
|-----------|-------------|
| `zotero_set_status` | Set item status (removes old status tags) |
| `zotero_add_use_tags` | Add use tags |
| `zotero_add_focus_tags` | Add focus/innovation tags |
| `zotero_remove_tags` | Remove specified tags |
| `zotero_get_items_by_status` | Get items filtered by status |
| `zotero_suggest_tags` | AI suggests focus tags based on title, abstract, and notes |

## Data Models

```python
# src/zotero_mcp/models/tags.py

class StatusTag(StrEnum):
    NEW = "new"
    READING = "reading"
    READ = "read"
    TODO = "todo"
    CITED = "cited"
    SKIP = "skip"
    ARCHIVE = "archive"

class UseTag(StrEnum):
    INTRO = "intro"
    RELATED = "related"
    DISCUSS = "discuss"
    REFERENCE = "reference"
    COMPARE = "compare"

# Focus tag categories and subtags
FOCUS_PREP_TAGS = {"synth", "coat", "dope", "nano"}
FOCUS_CHAR_TAGS = {"struct", "surf", "electro", "spec"}
FOCUS_PERF_TAGS = {"energy", "power", "cycle", "rate"}
FOCUS_MECH_TAGS = {"react", "decay", "inter"}
FOCUS_THEORY_TAGS = {"dft", "md", "ml"}

def build_focus_tag(category: str, subtag: str) -> str:
    return f"focus/{category}/{subtag}"

def is_valid_focus_tag(tag: str) -> bool:
    # Validation logic
    ...
```

## Integration with Existing Code

### Existing Tags (Preserved)

- `AI/条目分析` - AI analysis completed
- `AI/元数据更新` - AI metadata updated

### Auto-Tagging on Import

When a new item is imported via scanner:
```python
# In scanner.py
async def on_item_added(item):
    await add_tags(item, ["status/new"])
```

### AI Tag Suggestion

Uses title + abstract + note content to recommend focus tags:
```python
prompt = f"""
Based on the following paper, suggest appropriate innovation dimension tags (max 3):

Title: {item.title}
Abstract: {item.abstract}
Notes: {note_content}

Available tags:
- prep: synth, coat, dope, nano
- char: struct, surf, electro, spec
- perf: energy, power, cycle, rate
- mech: react, decay, inter
- theory: dft, md, ml

Return only tag names, comma-separated, e.g.: prep/synth, char/electro
"""
```

## Workflow Example

```
1. Import paper       → auto: status/new
2. Start reading      → status:reading
3. Finish reading     → status:read
4. AI suggests tags   → focus/prep/synth, focus/char/electro
5. Mark use case      → use:related
6. Plan to cite       → status:todo
7. Cite in paper      → status:cited
8. Archive            → status:archive
```

## Implementation Files

| File | Purpose |
|------|---------|
| `src/zotero_mcp/models/tags.py` | Tag constants, enums, validation |
| `src/zotero_mcp/models/tags/inputs.py` | Input models for MCP tools |
| `src/zotero_mcp/handlers/tags.py` | Tag handler functions |
| `src/zotero_mcp/handlers/tools.py` | Register new tools |
| `src/zotero_mcp/config/tags.py` | Tag system configuration |
| `tests/test_tag_system.py` | Unit and integration tests |

## Naming Convention

- **Format:** `category/subcategory` (hierarchical, lowercase)
- **Separators:** Forward slash (`/`)
- **Values:** English abbreviations for brevity
- **Examples:** `status/read`, `focus/prep/synth`, `use/intro`

## Query Examples

```
# Find papers to cite with reaction mechanism focus
status/todo + focus/mech/react

# Find intro material on synthesis methods
use/intro + focus/prep/*

# Find read but unprocessed papers
status/read (without use or focus tags)
```

## Notes

- Total categories: 3 (status, use, focus)
- Total core tags: ~35
- Preserved existing tags: `AI/条目分析`, `AI/元数据更新`
- Compatible with Zotero's native color coding
- No material/battery-type tags (use focus tags instead)

