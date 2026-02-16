"""
Flatten Zotero collection hierarchy by removing all second-level folders.

For each root collection (level-1):
- Collect all items from each second-level folder and its descendants.
- Add those items to the root collection.
- Delete the second-level folder (which removes its subtree).

Default mode is dry-run. Use --execute to apply changes.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from zotero_mcp.services.data_access import DataAccessService
from zotero_mcp.utils.config import load_config


def _name(coll: dict) -> str:
    return coll.get("data", {}).get("name", "")


def _parent(coll: dict) -> str | None:
    return coll.get("data", {}).get("parentCollection")


async def _iter_collection_item_keys(ds: DataAccessService, collection_key: str):
    start = 0
    while True:
        try:
            batch = await _get_collection_items_with_retry(
                ds, collection_key=collection_key, limit=100, start=start
            )
        except Exception as e:
            # Collection may have been deleted, skip it
            print(f"  [WARN] Failed to get items for collection {collection_key}: {e}")
            break
        if not batch:
            break
        for it in batch:
            if it.key:
                yield it.key
        if len(batch) < 100:
            break
        start += 100


async def _get_collection_items_with_retry(
    ds: DataAccessService,
    collection_key: str,
    limit: int,
    start: int,
    max_retries: int = 5,
):
    delay = 1.0
    for attempt in range(max_retries):
        try:
            return await ds.get_collection_items(collection_key, limit=limit, start=start)
        except Exception:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * 2, 8.0)
    return []


def _collect_subtree_keys(children_by_parent: dict[str, list[dict]], second_level_key: str) -> list[str]:
    out: list[str] = []
    stack = [second_level_key]
    while stack:
        k = stack.pop()
        out.append(k)
        for child in children_by_parent.get(k, []):
            stack.append(child["key"])
    return out


async def main(execute: bool = False) -> int:
    load_config()
    ds = DataAccessService()
    collections = await ds.get_collections()

    children_by_parent: dict[str, list[dict]] = defaultdict(list)
    roots: list[dict] = []
    for c in collections:
        p = _parent(c)
        if p:
            children_by_parent[p].append(c)
        else:
            roots.append(c)

    total_second_level = 0
    total_item_refs = 0
    total_added = 0
    total_failed_add = 0
    total_deleted = 0
    total_failed_delete = 0

    for root in sorted(roots, key=_name):
        root_key = root["key"]
        root_name = _name(root)
        second_levels = sorted(children_by_parent.get(root_key, []), key=_name)
        if not second_levels:
            continue
        print(f"\n[{root_name}] second-level={len(second_levels)}")
        total_second_level += len(second_levels)

        for sec in second_levels:
            sec_name = _name(sec)
            sec_key = sec["key"]
            subtree_keys = _collect_subtree_keys(children_by_parent, sec_key)

            item_keys: set[str] = set()
            try:
                for ck in subtree_keys:
                    async for item_key in _iter_collection_item_keys(ds, ck):
                        item_keys.add(item_key)
            except Exception as e:
                print(f"  [ERROR] Failed to collect items from {sec_name}: {e}")
                continue

            item_count = len(item_keys)
            total_item_refs += item_count
            print(f"- FLATTEN: {sec_name} -> {root_name} (items={item_count}, subtree={len(subtree_keys)})")

            if execute:
                for k in item_keys:
                    try:
                        await ds.add_item_to_collection(root_key, k)
                        total_added += 1
                    except Exception:
                        total_failed_add += 1
                try:
                    await ds.delete_collection(sec_key)
                    total_deleted += 1
                except Exception:
                    total_failed_delete += 1

    print("\nSUMMARY")
    print(f"second_level_folders={total_second_level}")
    print(f"unique_item_refs_to_preserve={total_item_refs}")
    if not execute:
        print("DRY RUN only. Use --execute to apply changes.")
    else:
        print(f"item_add_success={total_added}")
        print(f"item_add_failed={total_failed_add}")
        print(f"delete_success={total_deleted}")
        print(f"delete_failed={total_failed_delete}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Flatten all second-level Zotero folders into root folders."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes (default is dry-run).",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(execute=args.execute)))
