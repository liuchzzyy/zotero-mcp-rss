"""
Rename selected third-level PARA folders to unified naming pattern:
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


THIRD_LEVEL_TARGETS: dict[str, dict[str, str]] = {
    "A02_锰基正极_MnO2与衍生物": {
        "MnO2_多晶型": "M01_晶型家族_MnO2多晶型",
        "MnOOH_含氢锰矿": "M02_晶相类型_MnOOH含氢锰矿",
        "ZSH_锌硫氢": "M03_中间相_ZSH锌硫氢",
        "ZnMn2O4_尖晶石": "M04_尖晶石_ZnMn2O4",
        "ZnMn3O7_低价锰": "M05_低价锰_ZnMn3O7",
    },
    "A03_反应机理_界面与储能机制": {
        "储能机制_探究": "K01_储能机制_反应路径",
        "界面化学": "K02_界面过程_电荷与传质",
        "装置设计": "K03_器件行为_结构与工况",
    },
    "A04_性能优化_稳定性倍率循环": {
        "性能优化_改性": "O01_改性策略_性能优化",
    },
    "A05_体系拓展_钠钙锌硫": {
        "氟碳体系": "E01_体系拓展_氟碳体系",
        "钙离子电池": "E02_体系拓展_钙离子电池",
        "钠离子电池": "E03_体系拓展_钠离子电池",
        "锌硫电池": "E04_体系拓展_锌硫电池",
    },
    "R01_电化学方法_测试与数据判读": {
        "EQCM_微天平": "C01_电化学方法_EQCM微天平",
        "pH_环境影响": "C02_电化学方法_pH环境影响",
        "电化学表征_通用": "C03_电化学方法_通用表征",
    },
    "R02_同步辐射_XASXESTXM": {
        "TXM_透射成像": "S01_同步辐射_TXM透射成像",
        "XAS_XES_吸收发射": "S02_同步辐射_XASXES吸收发射",
    },
    "R03_结构表征_XRDTEM": {
        "TEM_电子显微": "T01_结构表征_TEM电子显微",
        "XRD_晶体结构": "T02_结构表征_XRD晶体结构",
    },
    "R04_化学态表征_XPSRamanFTIR": {
        "FTIR_红外光谱": "U01_化学态表征_FTIR红外",
        "Raman_拉曼光谱": "U02_化学态表征_Raman拉曼",
        "XPS_表面价态": "U03_化学态表征_XPS表面价态",
    },
    "R05_计算工具_DFT与Python": {
        "数学代码_Python": "D01_计算工具_Python代码",
        "理论计算_DFT": "D02_计算工具_DFT理论",
    },
    "R06_科研工作流_写作与笔记": {
        "笔记技能": "W01_科研工作流_笔记技能",
    },
    "R90_个人兴趣_历史文学社科": {
        "历史_人文": "I01_个人阅读_历史人文",
    },
    "R91_个人兴趣_财务与投资": {
        "金融_投资": "F01_个人财务_金融投资",
    },
    "H90_历史归档_LegacyCCAACCGGAABBCCHH": {
        "AA - 暂存": "L01_遗留分类_暂存",
        "BB - 工作 - 资源分类：长期性": "L02_遗留分类_工作资源长期",
        "CC - 工作 - 未来思路：赚钱！": "L03_遗留分类_工作副业思路",
        "DD - 归档输出：持久性": "L04_遗留分类_归档输出持久",
        "EE - 生活 - 资源管理：长期性": "L05_遗留分类_生活资源长期",
        "FF - 生活 - 副业管理：赚钱": "L06_遗留分类_生活副业管理",
    },
}


def _name(coll: dict) -> str:
    return coll.get("data", {}).get("name", "")


def _parent(coll: dict) -> str | None:
    return coll.get("data", {}).get("parentCollection")


def _find_by_name(cols: list[dict], name: str) -> dict | None:
    matches = [c for c in cols if _name(c) == name]
    return matches[0] if matches else None


async def main(execute: bool = False) -> int:
    load_config()
    ds = DataAccessService()
    cols = await ds.get_collections()

    for parent_name, renames in THIRD_LEVEL_TARGETS.items():
        parent = _find_by_name(cols, parent_name)
        if not parent:
            continue
        print(f"\n[{parent_name}]")
        parent_key = parent["key"]
        for old_name, new_name in renames.items():
            src = [c for c in cols if _parent(c) == parent_key and _name(c) == old_name]
            if not src:
                continue
            dst = [c for c in cols if _parent(c) == parent_key and _name(c) == new_name]
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
        description="Rename third-level PARA folders to unified naming pattern."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes (default is dry-run).",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(execute=args.execute)))
