# Obsidian Vault Restructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reorganize `F:\ChengL1u\ChengL1u` vault into scheme B (two-level + YAML properties).

**Architecture:** Create new numbered folders, move existing notes, patch YAML frontmatter, remove old empty folders.

**Tech Stack:** bash, sed/python for frontmatter patching.

---

### Task 1: Create new folder structure

**Files:**
- Create all target directories under `/f/ChengL1u/ChengL1u/`

**Step 1: Create directories**

```bash
mkdir -p "/f/ChengL1u/ChengL1u/00 - Daily"
mkdir -p "/f/ChengL1u/ChengL1u/01 - Research/Experiments"
mkdir -p "/f/ChengL1u/ChengL1u/01 - Research/Literature"
mkdir -p "/f/ChengL1u/ChengL1u/01 - Research/Thesis"
mkdir -p "/f/ChengL1u/ChengL1u/02 - Knowledge"
mkdir -p "/f/ChengL1u/ChengL1u/03 - Projects"
mkdir -p "/f/ChengL1u/ChengL1u/04 - References/Tools"
mkdir -p "/f/ChengL1u/ChengL1u/04 - References/Clippings"
mkdir -p "/f/ChengL1u/ChengL1u/99 - Meta"
```

**Step 2: Verify**

```bash
find "/f/ChengL1u/ChengL1u" -type d -not -path '*/.obsidian*' | sort
```
Expected: 9 new directories listed.

**Step 3: Commit**

```bash
cd /f/ChengL1u/ChengL1u && git add -A && git commit -m "feat: create new vault folder structure"
```

---

### Task 2: Move existing notes to new locations

**Files:**
- Move: `科研实验/*.md` → `01 - Research/Experiments/`
- Move: `学术与思想/*.md` → `02 - Knowledge/`
- Move: `职业发展/*.md` → `03 - Projects/`
- Move: `工具与参考/*.md` → `04 - References/Tools/`
- Move: `Clippings/*.md` → `04 - References/Clippings/`

**Step 1: Move files**

```bash
VAULT="/f/ChengL1u/ChengL1u"
mv "$VAULT/科研实验/"*.md "$VAULT/01 - Research/Experiments/"
mv "$VAULT/学术与思想/"*.md "$VAULT/02 - Knowledge/"
mv "$VAULT/职业发展/"*.md "$VAULT/03 - Projects/"
mv "$VAULT/工具与参考/"*.md "$VAULT/04 - References/Tools/"
mv "$VAULT/Clippings/"*.md "$VAULT/04 - References/Clippings/"
```

**Step 2: Verify all files moved**

```bash
find "/f/ChengL1u/ChengL1u" -name "*.md" -not -path '*/.obsidian*' | sort
```
Expected: 10 .md files, all under new numbered folders.

**Step 3: Remove old empty folders**

```bash
VAULT="/f/ChengL1u/ChengL1u"
rmdir "$VAULT/科研实验" "$VAULT/学术与思想" "$VAULT/职业发展" "$VAULT/工具与参考" "$VAULT/Clippings"
```

**Step 4: Commit**

```bash
cd /f/ChengL1u/ChengL1u && git add -A && git commit -m "feat: migrate notes to new folder structure"
```

---

### Task 3: Patch YAML frontmatter — add type/status tags

**Files:**
- Modify: all 10 `.md` files — add `type/` and `status/` tags if missing

**Mapping:**
| Folder | type tag |
|--------|----------|
| `01 - Research/Experiments/` | `type/experiment` |
| `02 - Knowledge/` | `type/note` |
| `03 - Projects/` | `type/project` |
| `04 - References/Tools/` | `type/reference` |
| `04 - References/Clippings/` | `type/clipping` |

**Step 1: Write patch script**

Create `/f/ICMAB-Data/UAB-Thesis/zotero-mcp/scripts/patch_vault_frontmatter.py`:

```python
import os
import re

VAULT = r"F:\ChengL1u\ChengL1u"

# folder → type tag
FOLDER_TYPE = {
    "01 - Research/Experiments": "type/experiment",
    "01 - Research/Literature":  "type/literature",
    "01 - Research/Thesis":      "type/note",
    "02 - Knowledge":            "type/note",
    "03 - Projects":             "type/project",
    "04 - References/Tools":     "type/reference",
    "04 - References/Clippings": "type/clipping",
    "00 - Daily":                "type/daily",
}

def get_type_tag(filepath):
    rel = os.path.relpath(filepath, VAULT).replace("\\", "/")
    for folder, tag in FOLDER_TYPE.items():
        if rel.startswith(folder):
            return tag
    return None

def patch_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.startswith("---"):
        return False  # no frontmatter, skip

    type_tag = get_type_tag(filepath)
    if not type_tag:
        return False

    # check if type/ tag already present
    if "type/" in content:
        print(f"  SKIP (has type/): {os.path.basename(filepath)}")
        return False

    # inject type/ and status/active into tags list
    # find the tags: block and append
    def inject_tags(m):
        existing = m.group(0)
        lines = existing.rstrip().split("\n")
        lines.append(f"  - {type_tag}")
        if "status/" not in content:
            lines.append("  - status/active")
        return "\n".join(lines)

    new_content = re.sub(r"tags:.*?(?=\n\w|\n---)", inject_tags, content, flags=re.DOTALL)

    if new_content != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"  PATCHED: {os.path.basename(filepath)}")
        return True
    return False

def main():
    patched = 0
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if fname.endswith(".md"):
                fp = os.path.join(root, fname)
                if patch_file(fp):
                    patched += 1
    print(f"\nDone. {patched} files patched.")

if __name__ == "__main__":
    main()
```

**Step 2: Run script**

```bash
cd /f/ICMAB-Data/UAB-Thesis/zotero-mcp
uv run python scripts/patch_vault_frontmatter.py
```
Expected: ~10 files PATCHED, 0 errors.

**Step 3: Spot-check one file**

```bash
head -15 "/f/ChengL1u/ChengL1u/01 - Research/Experiments/CLAESS实验笔记.md"
```
Expected: frontmatter now contains `type/experiment` and `status/active`.

**Step 4: Commit**

```bash
cd /f/ChengL1u/ChengL1u && git add -A && git commit -m "feat: add type/ and status/ tags to all notes"
```

---

### Task 4: Create starter template in 99 - Meta

**Files:**
- Create: `99 - Meta/templates/daily-note.md`

**Step 1: Write daily note template**

```bash
mkdir -p "/f/ChengL1u/ChengL1u/99 - Meta/templates"
cat > "/f/ChengL1u/ChengL1u/99 - Meta/templates/daily-note.md" << 'EOF'
---
tags:
  - type/daily
  - status/active
date: {{date:YYYY-MM-DD}}
---

# {{date:YYYY-MM-DD}}

## 今日收集

## 任务

## 笔记
EOF
```

**Step 2: Commit**

```bash
cd /f/ChengL1u/ChengL1u && git add -A && git commit -m "feat: add daily note template"
```
