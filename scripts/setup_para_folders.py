"""
Create/normalize PARA collection folders in Zotero.

Default mode is dry-run. Use --execute to create missing collections.
This script is idempotent and only creates missing folders.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from zotero_mcp.services.data_access import DataAccessService
from zotero_mcp.utils.config import load_config


ROOTS = [
    "00_INBOXS",
    "01_SHORTTERMS",
    "02_PROJECTS",
    "03_AREAS",
    "04_RESOURCES",
    "05_ARCHIVES",
    "06_TRASHES",
]

# Tailored for current library and PARA workflow.
TARGET_CHILDREN: dict[str, list[str]] = {
    "02_PROJECTS": [
        "P_ACTIVE_进行中",
        "P_WAITING_待推进",
        "P_SOMEDAY_孵化",
        "P_TEMPLATE_项目模板",
    ],
    "03_AREAS": [
        "材料体系_锰基",
        "研究方向_新型电池",
        "研究方向_机理",
    ],
    "04_RESOURCES": [
        "电化学方法",
        "表征技术_同步辐射",
        "表征技术_常规",
        "通用技能",
        "个人兴趣",
    ],
    "05_ARCHIVES": [
        "Archive_Projects_2026",
        "Archive_Areas_2026",
        "Archive_Resources_2026",
        "Legacy_CCAACCGGAABBCCHH",
    ],
}

PROJECT_TEMPLATE_CHILDREN = {
    "P_TEMPLATE_项目模板": [
        "T01_项目维度_综述",
        "T02_项目维度_制备",
        "T03_项目维度_表征",
        "T04_项目维度_理论",
        "T05_项目维度_改进",
        "T06_项目维度_机制",
        "T07_项目维度_其他",
    ]
}


@dataclass
class CreatePlan:
    name: str
    parent_name: str
    parent_key: str


def _coll_name(coll: dict) -> str:
    return coll.get("data", {}).get("name", "")


async def build_create_plan(ds: DataAccessService) -> tuple[list[CreatePlan], dict[str, str]]:
    collections = await ds.get_collections()
    by_key = {c["key"]: c for c in collections}

    root_key_by_name: dict[str, str] = {}
    for root_name in ROOTS:
        root_matches = [c for c in collections if _coll_name(c) == root_name and not c.get("data", {}).get("parentCollection")]
        if not root_matches:
            raise RuntimeError(f"Required root collection missing: {root_name}")
        root_key_by_name[root_name] = root_matches[0]["key"]

    existing_pairs: set[tuple[str, str]] = set()
    for c in collections:
        parent = c.get("data", {}).get("parentCollection")
        if not parent:
            continue
        existing_pairs.add((parent, _coll_name(c)))

    plans: list[CreatePlan] = []

    # Ensure target level-2 collections exist.
    for parent_name, child_names in TARGET_CHILDREN.items():
        parent_key = root_key_by_name[parent_name]
        for child_name in child_names:
            pair = (parent_key, child_name)
            if pair not in existing_pairs:
                plans.append(
                    CreatePlan(
                        name=child_name,
                        parent_name=parent_name,
                        parent_key=parent_key,
                    )
                )

    # Refresh relationships in memory with planned level-2 creates,
    # then plan template level-3 children.
    level2_key_by_name: dict[str, str] = {}
    for c in collections:
        parent = c.get("data", {}).get("parentCollection")
        if parent and parent in root_key_by_name.values():
            level2_key_by_name[_coll_name(c)] = c["key"]

    # Fake keys for dry-run planning are not needed; only plan if parent exists already.
    for parent_name, child_names in PROJECT_TEMPLATE_CHILDREN.items():
        parent_key = level2_key_by_name.get(parent_name)
        if not parent_key:
            # Parent may be newly planned; skip nested planning in first pass.
            continue
        for child_name in child_names:
            pair = (parent_key, child_name)
            if pair not in existing_pairs:
                plans.append(
                    CreatePlan(
                        name=child_name,
                        parent_name=parent_name,
                        parent_key=parent_key,
                    )
                )

    return plans, root_key_by_name


async def create_missing_templates(ds: DataAccessService, dry_run: bool) -> tuple[int, int]:
    """
    Second pass to create template children if parent was just created.
    """
    collections = await ds.get_collections()
    existing_pairs = {
        (c.get("data", {}).get("parentCollection"), _coll_name(c))
        for c in collections
        if c.get("data", {}).get("parentCollection")
    }
    by_name = {_coll_name(c): c for c in collections}

    created = 0
    failed = 0
    for parent_name, child_names in PROJECT_TEMPLATE_CHILDREN.items():
        parent = by_name.get(parent_name)
        if not parent:
            continue
        parent_key = parent["key"]
        for child_name in child_names:
            if (parent_key, child_name) in existing_pairs:
                continue
            if dry_run:
                print(f"- CREATE: {child_name} (parent={parent_name})")
                continue
            try:
                await ds.create_collection(name=child_name, parent_key=parent_key)
                print(f"  created: {child_name} (parent={parent_name})")
                created += 1
            except Exception as exc:
                print(f"  failed: {child_name} (parent={parent_name}) ({exc})")
                failed += 1
    return created, failed


async def main(execute: bool = False) -> int:
    load_config()
    ds = DataAccessService()

    plans, _ = await build_create_plan(ds)
    if not plans:
        print("No missing PARA folders at level-2.")
    else:
        print("Planned PARA folder creations:")
        for p in plans:
            print(f"- CREATE: {p.name} (parent={p.parent_name})")

    if not execute:
        print("\nDRY RUN only. Use --execute to create missing folders.")
        # Still show second-pass dry-run view.
        await create_missing_templates(ds, dry_run=True)
        return 0

    created = 0
    failed = 0
    for p in plans:
        try:
            await ds.create_collection(name=p.name, parent_key=p.parent_key)
            print(f"  created: {p.name}")
            created += 1
        except Exception as exc:
            print(f"  failed: {p.name} ({exc})")
            failed += 1

    c2, f2 = await create_missing_templates(ds, dry_run=False)
    created += c2
    failed += f2

    print(f"\nDone. created={created}, failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create/normalize PARA collection folders in Zotero."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes (default is dry-run).",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(execute=args.execute)))
