"""
Redesign 03_AREAS with 7-dimension second-level folders.

Strategy:
- Keep all existing content.
- Create dimension folders under 03_AREAS.
- Move current topic folders under mapped dimensions as level-3.

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


DIMENSIONS = [
    "A01_研究维度_综述",
    "A02_研究维度_制备",
    "A03_研究维度_表征",
    "A04_研究维度_理论",
    "A05_研究维度_改进",
    "A06_研究维度_机制",
    "A07_研究维度_其他",
]

TOPIC_TO_DIMENSION = {
    "A01_电池体系_锌离子电池总入口": "A01_研究维度_综述",
    "A02_锰基正极_MnO2与衍生物": "A02_研究维度_制备",
    "A03_反应机理_界面与储能机制": "A06_研究维度_机制",
    "A04_性能优化_稳定性倍率循环": "A05_研究维度_改进",
    "A05_体系拓展_钠钙锌硫": "A07_研究维度_其他",
}


def _name(coll: dict) -> str:
    return coll.get("data", {}).get("name", "")


def _parent(coll: dict) -> str | None:
    return coll.get("data", {}).get("parentCollection")


def _find_root(cols: list[dict], name: str) -> dict | None:
    roots = [c for c in cols if not _parent(c) and _name(c) == name]
    return roots[0] if roots else None


def _find_child(cols: list[dict], parent_key: str, name: str) -> dict | None:
    matches = [c for c in cols if _parent(c) == parent_key and _name(c) == name]
    return matches[0] if matches else None


async def main(execute: bool = False) -> int:
    load_config()
    ds = DataAccessService()
    cols = await ds.get_collections()

    areas_root = _find_root(cols, "03_AREAS")
    if not areas_root:
        print("03_AREAS not found.")
        return 1
    root_key = areas_root["key"]

    print("[AREAS_DIMENSIONS]")
    # 1) Ensure dimension folders
    for dim in DIMENSIONS:
        exists = _find_child(cols, root_key, dim)
        if exists:
            continue
        print(f"- CREATE: {dim}")
        if execute:
            await ds.create_collection(name=dim, parent_key=root_key)
            cols = await ds.get_collections()

    # 2) Move topic folders under target dimensions
    for topic_name, dim_name in TOPIC_TO_DIMENSION.items():
        cols = await ds.get_collections()
        topic = _find_child(cols, root_key, topic_name)
        if not topic:
            continue
        dim = _find_child(cols, root_key, dim_name)
        if not dim:
            print(f"- SKIP: missing dimension {dim_name} for {topic_name}")
            continue

        # If same-name child already exists under dimension, skip to avoid collision.
        collision = _find_child(cols, dim["key"], topic_name)
        if collision:
            continue

        print(f"- MOVE: {topic_name} -> {dim_name}")
        if execute:
            await ds.update_collection(collection_key=topic["key"], parent_key=dim["key"])

    if not execute:
        print("\nDRY RUN only. Use --execute to apply changes.")
    else:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Redesign 03_AREAS by 7-dimension structure."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes (default is dry-run).",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(execute=args.execute)))
