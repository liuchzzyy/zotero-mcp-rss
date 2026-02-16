"""
Restructure Zotero PARA folders to V0 numbered naming.

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


ROOTS = [
    "02_PROJECTS",
    "03_AREAS",
    "04_RESOURCES",
]

PROJECT_TARGETS = [
    "P01_正在推进",
    "P02_等待条件",
    "P03_想法池",
    "P99_项目模板",
]

AREA_TARGETS = [
    "A01_锌离子电池_总入口",
    "A02_MnO2与锰基正极",
    "A03_反应机理与界面问题",
    "A04_性能提升_稳定性倍率循环",
    "A05_体系拓展_钠钙锌硫",
]

RESOURCE_TARGETS = [
    "R01_电化学测试与数据判读",
    "R02_同步辐射_XAS_XES_TXM",
    "R03_常规材料表征_XRD_TEM",
    "R04_表面化学态_XPS_Raman_FTIR",
    "R05_计算与代码_DFT_Python",
    "R06_科研写作与笔记",
    "R90_个人阅读_历史文学社科",
    "R91_个人财务与投资",
]


def _name(coll: dict) -> str:
    return coll.get("data", {}).get("name", "")


def _parent(coll: dict) -> str | None:
    return coll.get("data", {}).get("parentCollection")


async def _create_if_missing(
    ds: DataAccessService,
    all_cols: list[dict],
    parent_key: str,
    wanted_name: str,
    execute: bool,
) -> list[dict]:
    exists = [c for c in all_cols if _parent(c) == parent_key and _name(c) == wanted_name]
    if exists:
        return all_cols
    print(f"- CREATE: {wanted_name}")
    if execute:
        await ds.create_collection(name=wanted_name, parent_key=parent_key)
    return await ds.get_collections()


async def _rename_if_exists(
    ds: DataAccessService,
    all_cols: list[dict],
    parent_key: str,
    old_name: str,
    new_name: str,
    execute: bool,
) -> list[dict]:
    src = [c for c in all_cols if _parent(c) == parent_key and _name(c) == old_name]
    if not src:
        return all_cols
    dst = [c for c in all_cols if _parent(c) == parent_key and _name(c) == new_name]
    if dst:
        return all_cols
    print(f"- RENAME: {old_name} -> {new_name}")
    if execute:
        await ds.update_collection(collection_key=src[0]["key"], name=new_name)
    return await ds.get_collections()


async def _move_if_exists(
    ds: DataAccessService,
    all_cols: list[dict],
    old_parent_key: str,
    name: str,
    new_parent_key: str,
    execute: bool,
) -> list[dict]:
    src = [c for c in all_cols if _parent(c) == old_parent_key and _name(c) == name]
    if not src:
        return all_cols
    dst = [c for c in all_cols if _parent(c) == new_parent_key and _name(c) == name]
    if dst:
        return all_cols
    print(f"- MOVE: {name} -> new parent")
    if execute:
        await ds.update_collection(collection_key=src[0]["key"], parent_key=new_parent_key)
    return await ds.get_collections()


def _find_root(all_cols: list[dict], root_name: str) -> dict:
    roots = [c for c in all_cols if not _parent(c) and _name(c) == root_name]
    if not roots:
        raise RuntimeError(f"Required root missing: {root_name}")
    return roots[0]


def _find_child(all_cols: list[dict], parent_key: str, name: str) -> dict | None:
    matches = [c for c in all_cols if _parent(c) == parent_key and _name(c) == name]
    return matches[0] if matches else None


async def main(execute: bool = False) -> int:
    load_config()
    ds = DataAccessService()
    all_cols = await ds.get_collections()

    # Validate roots
    roots = {r: _find_root(all_cols, r) for r in ROOTS}

    # 1) Projects: rename old second-level names to V0 names, then ensure all exist.
    project_root_key = roots["02_PROJECTS"]["key"]
    project_renames = [
        ("P_ACTIVE_进行中", "P01_正在推进"),
        ("P_WAITING_待推进", "P02_等待条件"),
        ("P_SOMEDAY_孵化", "P03_想法池"),
        ("P_TEMPLATE_项目模板", "P99_项目模板"),
    ]
    print("\n[PROJECTS]")
    for old, new in project_renames:
        all_cols = await _rename_if_exists(ds, all_cols, project_root_key, old, new, execute)
    for target in PROJECT_TARGETS:
        all_cols = await _create_if_missing(ds, all_cols, project_root_key, target, execute)

    # Keep project template nested structure compatible if template exists.
    template = _find_child(all_cols, project_root_key, "P99_项目模板")
    if template:
        tpl_children = [
            "T01_项目维度_综述",
            "T02_项目维度_制备",
            "T03_项目维度_表征",
            "T04_项目维度_理论",
            "T05_项目维度_改进",
            "T06_项目维度_机制",
            "T07_项目维度_其他",
        ]
        # Rename old template children if present.
        tpl_renames = [
            ("00_SCOPE", "T01_项目维度_综述"),
            ("01_CORE_PAPERS", "T01_项目维度_综述"),
            ("02_METHODS", "T02_项目维度_制备"),
            ("03_OUTPUTS", "T07_项目维度_其他"),
            ("00_研究目标与范围", "T01_项目维度_综述"),
            ("01_核心文献", "T01_项目维度_综述"),
            ("02_实验与方法", "T02_项目维度_制备"),
            ("03_结果与输出", "T07_项目维度_其他"),
        ]
        for old, new in tpl_renames:
            all_cols = await _rename_if_exists(ds, all_cols, template["key"], old, new, execute)
        for target in tpl_children:
            all_cols = await _create_if_missing(ds, all_cols, template["key"], target, execute)

    # 2) Areas: rename current second-level and ensure targets.
    area_root_key = roots["03_AREAS"]["key"]
    area_renames = [
        ("材料体系_锰基", "A02_MnO2与锰基正极"),
        ("研究方向_机理", "A03_反应机理与界面问题"),
        ("研究方向_新型电池", "A05_体系拓展_钠钙锌硫"),
    ]
    print("\n[AREAS]")
    for old, new in area_renames:
        all_cols = await _rename_if_exists(ds, all_cols, area_root_key, old, new, execute)
    for target in AREA_TARGETS:
        all_cols = await _create_if_missing(ds, all_cols, area_root_key, target, execute)

    # Move "性能优化_改性" from A03 to A04 if both exist.
    a03 = _find_child(all_cols, area_root_key, "A03_反应机理与界面问题")
    a04 = _find_child(all_cols, area_root_key, "A04_性能提升_稳定性倍率循环")
    if a03 and a04:
        all_cols = await _move_if_exists(
            ds,
            all_cols,
            old_parent_key=a03["key"],
            name="性能优化_改性",
            new_parent_key=a04["key"],
            execute=execute,
        )

    # 3) Resources: rename second-level and ensure targets.
    resource_root_key = roots["04_RESOURCES"]["key"]
    resource_renames = [
        ("电化学方法", "R01_电化学测试与数据判读"),
        ("表征技术_同步辐射", "R02_同步辐射_XAS_XES_TXM"),
        ("通用技能", "R05_计算与代码_DFT_Python"),
        ("个人兴趣", "R90_个人阅读_历史文学社科"),
    ]
    print("\n[RESOURCES]")
    for old, new in resource_renames:
        all_cols = await _rename_if_exists(ds, all_cols, resource_root_key, old, new, execute)

    # Split old "表征技术_常规" into R03 and R04 by moving its children.
    all_cols = await _create_if_missing(
        ds, all_cols, resource_root_key, "R03_常规材料表征_XRD_TEM", execute
    )
    all_cols = await _create_if_missing(
        ds, all_cols, resource_root_key, "R04_表面化学态_XPS_Raman_FTIR", execute
    )
    old_common = _find_child(all_cols, resource_root_key, "表征技术_常规")
    r03 = _find_child(all_cols, resource_root_key, "R03_常规材料表征_XRD_TEM")
    r04 = _find_child(all_cols, resource_root_key, "R04_表面化学态_XPS_Raman_FTIR")
    if old_common and r03 and r04:
        for child in ["XRD_晶体结构", "TEM_电子显微"]:
            all_cols = await _move_if_exists(
                ds, all_cols, old_common["key"], child, r03["key"], execute
            )
        for child in ["XPS_表面价态", "Raman_拉曼光谱", "FTIR_红外光谱"]:
            all_cols = await _move_if_exists(
                ds, all_cols, old_common["key"], child, r04["key"], execute
            )
        # Remove old container if empty (best effort)
        all_cols = await ds.get_collections()
        still_children = [c for c in all_cols if _parent(c) == old_common["key"]]
        if not still_children:
            print("- DELETE EMPTY: 表征技术_常规")
            if execute:
                await ds.delete_collection(old_common["key"])
                all_cols = await ds.get_collections()

    # Split R05 content: keep code/calculation in R05, move note skills to R06.
    all_cols = await _create_if_missing(
        ds, all_cols, resource_root_key, "R06_科研写作与笔记", execute
    )
    r05 = _find_child(all_cols, resource_root_key, "R05_计算与代码_DFT_Python")
    r06 = _find_child(all_cols, resource_root_key, "R06_科研写作与笔记")
    if r05 and r06:
        all_cols = await _move_if_exists(
            ds, all_cols, r05["key"], "笔记技能", r06["key"], execute
        )

    # Split personal interests into reading and finance.
    all_cols = await _create_if_missing(
        ds, all_cols, resource_root_key, "R91_个人财务与投资", execute
    )
    r90 = _find_child(all_cols, resource_root_key, "R90_个人阅读_历史文学社科")
    r91 = _find_child(all_cols, resource_root_key, "R91_个人财务与投资")
    if r90 and r91:
        all_cols = await _move_if_exists(
            ds, all_cols, r90["key"], "金融_投资", r91["key"], execute
        )

    # Ensure all resource targets exist.
    for target in RESOURCE_TARGETS:
        all_cols = await _create_if_missing(ds, all_cols, resource_root_key, target, execute)

    if not execute:
        print("\nDRY RUN only. Use --execute to apply changes.")
    else:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Restructure Zotero PARA folders to V0 numbered naming."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes (default is dry-run).",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(execute=args.execute)))
