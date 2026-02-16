"""
Rename all second-level PARA folders to:
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


TARGETS: dict[str, dict[str, str]] = {
    "02_PROJECTS": {
        "P01_正在推进": "P01_项目管理_正在推进",
        "P02_等待条件": "P02_项目管理_等待条件",
        "P03_想法池": "P03_项目管理_想法池",
        "P99_项目模板": "P99_项目管理_项目模板",
    },
    "03_AREAS": {
        "A01_锌离子电池_总入口": "A01_电池体系_锌离子电池总入口",
        "A02_MnO2与锰基正极": "A02_锰基正极_MnO2与衍生物",
        "A03_反应机理与界面问题": "A03_反应机理_界面与储能机制",
        "A04_性能提升_稳定性倍率循环": "A04_性能优化_稳定性倍率循环",
        "A05_体系拓展_钠钙锌硫": "A05_体系拓展_钠钙锌硫",
    },
    "04_RESOURCES": {
        "R01_电化学测试与数据判读": "R01_电化学方法_测试与数据判读",
        "R02_同步辐射_XAS_XES_TXM": "R02_同步辐射_XASXESTXM",
        "R03_常规材料表征_XRD_TEM": "R03_结构表征_XRDTEM",
        "R04_表面化学态_XPS_Raman_FTIR": "R04_化学态表征_XPSRamanFTIR",
        "R05_计算与代码_DFT_Python": "R05_计算工具_DFT与Python",
        "R06_科研写作与笔记": "R06_科研工作流_写作与笔记",
        "R90_个人阅读_历史文学社科": "R90_个人兴趣_历史文学社科",
        "R91_个人财务与投资": "R91_个人兴趣_财务与投资",
    },
    "05_ARCHIVES": {
        "Archive_Projects_2026": "H01_历史归档_项目2026",
        "Archive_Areas_2026": "H02_历史归档_领域2026",
        "Archive_Resources_2026": "H03_历史归档_资源2026",
        "Legacy_CCAACCGGAABBCCHH": "H90_历史归档_LegacyCCAACCGGAABBCCHH",
    },
}


def _name(coll: dict) -> str:
    return coll.get("data", {}).get("name", "")


def _parent(coll: dict) -> str | None:
    return coll.get("data", {}).get("parentCollection")


def _find_root(cols: list[dict], root_name: str) -> dict | None:
    roots = [c for c in cols if not _parent(c) and _name(c) == root_name]
    return roots[0] if roots else None


async def main(execute: bool = False) -> int:
    load_config()
    ds = DataAccessService()
    cols = await ds.get_collections()

    for root_name, mapping in TARGETS.items():
        root = _find_root(cols, root_name)
        if not root:
            continue
        root_key = root["key"]
        print(f"\n[{root_name}]")
        for old_name, new_name in mapping.items():
            src = [c for c in cols if _parent(c) == root_key and _name(c) == old_name]
            if not src:
                continue
            dst = [c for c in cols if _parent(c) == root_key and _name(c) == new_name]
            if dst:
                continue
            print(f"- RENAME: {old_name} -> {new_name}")
            if execute:
                await ds.update_collection(collection_key=src[0]["key"], name=new_name)
                cols = await ds.get_collections()

    if not execute:
        print("\nDRY RUN only. Use --execute to apply changes.")
    else:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Rename second-level PARA folders to unified naming pattern."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes (default is dry-run).",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(execute=args.execute)))
