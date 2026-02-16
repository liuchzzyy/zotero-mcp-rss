"""
Normalize P99 project template into 7 dimensions:
综述, 制备, 表征, 理论, 改进, 机制, 其他

Naming pattern:
<Letter><2digits>_<CategoryName>_<SpecificName>

Default mode is dry-run. Use --execute to apply changes.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from zotero_mcp.services.data_access import DataAccessService
from zotero_mcp.utils.config import load_config


TARGET_CHILDREN = [
    "T01_项目维度_综述",
    "T02_项目维度_制备",
    "T03_项目维度_表征",
    "T04_项目维度_理论",
    "T05_项目维度_改进",
    "T06_项目维度_机制",
    "T07_项目维度_其他",
]

OLD_TO_TARGET = {
    "00_SCOPE": "T01_项目维度_综述",
    "01_CORE_PAPERS": "T01_项目维度_综述",
    "02_METHODS": "T02_项目维度_制备",
    "03_OUTPUTS": "T07_项目维度_其他",
    "00_研究目标与范围": "T01_项目维度_综述",
    "01_核心文献": "T01_项目维度_综述",
    "02_实验与方法": "T02_项目维度_制备",
    "03_结果与输出": "T07_项目维度_其他",
}


def _name(coll: dict) -> str:
    return coll.get("data", {}).get("name", "")


def _parent(coll: dict) -> str | None:
    return coll.get("data", {}).get("parentCollection")


def _count_items_batch_needed() -> int:
    return 100


async def _collection_item_count(ds: DataAccessService, key: str) -> int:
    total = 0
    start = 0
    limit = _count_items_batch_needed()
    while True:
        batch = await ds.get_collection_items(key, limit=limit, start=start)
        if not batch:
            break
        total += len(batch)
        if len(batch) < limit:
            break
        start += limit
    return total


async def main(execute: bool = False) -> int:
    load_config()
    ds = DataAccessService()
    cols = await ds.get_collections()
    by_name = {_name(c): c for c in cols}

    p99 = by_name.get("P99_项目管理_项目模板")
    if not p99:
        print("P99_项目管理_项目模板 not found.")
        return 1
    p99_key = p99["key"]

    # Ensure target folders exist.
    for t in TARGET_CHILDREN:
        exists = [c for c in cols if _parent(c) == p99_key and _name(c) == t]
        if exists:
            continue
        print(f"- CREATE: {t}")
        if execute:
            await ds.create_collection(name=t, parent_key=p99_key)
            cols = await ds.get_collections()

    # Move legacy folders' items into mapped target, then delete empty legacy folders.
    for old_name, target_name in OLD_TO_TARGET.items():
        cols = await ds.get_collections()
        old_matches = [c for c in cols if _parent(c) == p99_key and _name(c) == old_name]
        if not old_matches:
            continue
        target_matches = [c for c in cols if _parent(c) == p99_key and _name(c) == target_name]
        if not target_matches:
            print(f"- SKIP: target missing for {old_name} -> {target_name}")
            continue
        old = old_matches[0]
        target = target_matches[0]

        item_count = await _collection_item_count(ds, old["key"])
        if item_count > 0:
            print(f"- MOVE ITEMS: {old_name} ({item_count}) -> {target_name}")
            if execute:
                start = 0
                while True:
                    batch = await ds.get_collection_items(old["key"], limit=100, start=start)
                    if not batch:
                        break
                    for it in batch:
                        await ds.add_item_to_collection(target["key"], it.key)
                        await ds.remove_item_from_collection(old["key"], it.key)
                    if len(batch) < 100:
                        break
                    # items are removed from old, so keep start at 0 to avoid skipping
                    start = 0

        # Delete old folder if it has no subfolders and no items.
        cols = await ds.get_collections()
        old_matches = [c for c in cols if _parent(c) == p99_key and _name(c) == old_name]
        if not old_matches:
            continue
        old = old_matches[0]
        subfolders = [c for c in cols if _parent(c) == old["key"]]
        remaining_items = await _collection_item_count(ds, old["key"])
        if not subfolders and remaining_items == 0:
            print(f"- DELETE: {old_name}")
            if execute:
                await ds.delete_collection(old["key"])
        else:
            print(f"- KEEP: {old_name} (subfolders={len(subfolders)}, items={remaining_items})")

    if not execute:
        print("\nDRY RUN only. Use --execute to apply changes.")
    else:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Normalize P99 project template into 7 dimension folders."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes (default is dry-run).",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(execute=args.execute)))
