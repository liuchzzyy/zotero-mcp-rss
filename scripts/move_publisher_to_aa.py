"""
把 00_INBOXS_AA 中出版社为 Wiley、RSC、ACS 且含有一个 PDF 附件的条目移动到 00_AA。
通过 publicationTitle / publisher / extra 字段进行出版社识别。
"""
import re
import sys
from pyzotero import zotero

# ── 配置 ──────────────────────────────────────────────────────────────────────
LIBRARY_ID = "5452188"
API_KEY = "***ZOTERO_API_KEY***"

# ── 出版社识别规则（匹配 publicationTitle / publisher 字段，不区分大小写）──────
PUBLISHER_PATTERNS = {
    "Wiley": [
        r"wiley",
        r"angewandte chemie",
        r"advanced materials",
        r"advanced energy materials",
        r"advanced functional materials",
        r"advanced science",
        r"\bsmall\b",
        r"chemsuschem",
        r"chemelectrochem",
        r"chemcatchem",
        r"chemistry[- ]+a european journal",
        r"batteries.*supercaps",
        r"electroanalysis",
        r"european journal of inorganic chemistry",
        r"european journal of organic chemistry",
        r"macromolecular",
    ],
    "RSC": [
        r"royal society of chemistry",
        r"\brsc\b",
        r"journal of materials chemistry",
        r"energy.*environmental science",
        r"physical chemistry chemical physics",
        r"\bnanoscale\b",
        r"green chemistry",
        r"chemical communications",
        r"\bchem\.?\s*comm",
        r"dalton transactions",
        r"rsc advances",
        r"chemical science",
        r"new journal of chemistry",
        r"crystengcomm",
        r"faraday discuss",
        r"materials chemistry frontiers",
        r"journal of the chemical society",
    ],
    "ACS": [
        r"american chemical society",
        r"\bacs\s+\w",           # ACS Nano, ACS Energy Letters, etc.
        r"journal of the american chemical society",
        r"\bjacs\b",
        r"nano letters",
        r"chemistry of materials",
        r"journal of physical chemistry",
        r"\blangmuir\b",
        r"inorganic chemistry",
        r"analytical chemistry",
        r"environmental science.*technology",
        r"accounts of chemical research",
        r"crystal growth.*design",
        r"macromolecules",
        r"organometallics",
        r"biochemistry",
        r"the journal of organic chemistry",
        r"industrial.*engineering chemistry",
    ],
}

# 编译为正则
COMPILED = {
    pub: [re.compile(p, re.IGNORECASE) for p in patterns]
    for pub, patterns in PUBLISHER_PATTERNS.items()
}


def detect_publisher(item: dict) -> str | None:
    """返回匹配的出版社名称，或 None。"""
    fields = [
        item["data"].get("publicationTitle", ""),
        item["data"].get("publisher", ""),
        item["data"].get("extra", ""),
    ]
    text = " | ".join(fields)
    for pub, regexes in COMPILED.items():
        for rx in regexes:
            if rx.search(text):
                matched = item["data"].get("publicationTitle") or item["data"].get("publisher", "")
                return pub, matched[:50]
    return None, None


def move_item(zot, item: dict, inbox_key: str, aa_key: str) -> bool:
    current_cols = item["data"].get("collections", [])
    new_cols = list(set(current_cols + [aa_key]) - {inbox_key})
    try:
        zot.update_item({
            "key": item["key"],
            "version": item["version"],
            "collections": new_cols,
        })
        return True
    except Exception as e:
        print(f"    ❌ 移动失败: {e}")
        return False


def main():
    zot = zotero.Zotero(LIBRARY_ID, "user", API_KEY)

    # 1. 获取 collections
    print("正在获取 collections...")
    col_map = {c["data"]["name"]: c["key"]
               for c in zot.everything(zot.collections())}
    inbox_key = col_map.get("00_INBOXS_AA")
    aa_key = col_map.get("00_AA")
    if not inbox_key or not aa_key:
        sys.exit(f"❌ 找不到所需 collection。现有: {sorted(col_map.keys())}")
    print(f"✅ 00_INBOXS_AA={inbox_key}, 00_AA={aa_key}\n")

    # 2. 获取条目
    print("正在获取条目...")
    items = zot.everything(zot.collection_items(inbox_key, itemType="-attachment"))
    total = len(items)
    print(f"共 {total} 个条目\n{'─'*65}")

    moved, skipped_no_pdf, skipped_multi_pdf, skipped_no_match = [], [], [], []

    for i, item in enumerate(items, 1):
        key = item["key"]
        title = item["data"].get("title", "(无标题)")[:50]
        prefix = f"[{i:3d}/{total}]"

        # 获取 PDF 附件数量
        children = zot.children(key)
        pdfs = [c for c in children
                if c["data"].get("itemType") == "attachment"
                and c["data"].get("contentType") == "application/pdf"]
        pdf_count = len(pdfs)

        if pdf_count == 0:
            print(f"{prefix} ⏭️  无PDF: {title}")
            skipped_no_pdf.append(key)
            continue
        if pdf_count > 1:
            print(f"{prefix} ⏭️  {pdf_count}个PDF（跳过）: {title}")
            skipped_multi_pdf.append(key)
            continue

        # 检测出版社
        pub, journal = detect_publisher(item)
        if pub:
            print(f"{prefix} ✅ [{pub}] {journal} | {title}")
            ok = move_item(zot, item, inbox_key, aa_key)
            if ok:
                moved.append((key, title, pub, journal))
        else:
            journal_raw = item["data"].get("publicationTitle", "")[:40]
            print(f"{prefix} ➖ 非目标出版社 ({journal_raw}): {title}")
            skipped_no_match.append(key)

    # 汇总
    print(f"\n{'═'*65}")
    print(f"完成！")
    print(f"  ✅ 已移动到 00_AA : {len(moved)} 条")
    print(f"  ⏭️  无PDF跳过     : {len(skipped_no_pdf)} 条")
    print(f"  ⏭️  多PDF跳过     : {len(skipped_multi_pdf)} 条")
    print(f"  ➖ 非目标出版社  : {len(skipped_no_match)} 条")

    if moved:
        print("\n移动明细：")
        by_pub = {}
        for key, title, pub, journal in moved:
            by_pub.setdefault(pub, []).append((key, title, journal))
        for pub, entries in sorted(by_pub.items()):
            print(f"\n  [{pub}] {len(entries)} 条：")
            for key, title, journal in entries:
                print(f"    {key}  {journal}  |  {title}")


if __name__ == "__main__":
    main()
