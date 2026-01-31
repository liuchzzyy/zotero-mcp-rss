#!/usr/bin/env python3
"""Check the generated note content."""

import asyncio
import re
from zotero_mcp.services.data_access import get_data_service


async def main():
    ds = get_data_service()
    notes = await ds.get_notes("7I72IMC4")

    if not notes:
        print("❌ No notes found")
        return

    note_key = notes[0].get("key")
    note_data = await ds.get_item(note_key)
    note_content = note_data.get("data", {}).get("note", "")

    # Count blocks
    headings = len(re.findall(r"<h[1-6]", note_content))
    paras = len(re.findall(r"<p[^>]*>", note_content))
    lists = len(re.findall(r"<ul[^>]*>|<ol[^>]*>", note_content))
    br_count = len(re.findall(r"<br\s*/?>", note_content))

    print("=" * 80)
    print("检查生成的笔记内容")
    print("=" * 80)
    print()
    print(f"H1-H4 标题: {headings} 个")
    print(f"P 段落: {paras} 个")
    print(f"UL/OL 列表: {lists} 个")
    print(f"BR 标签: {br_count} 个")
    print()

    # Show first 1500 chars
    print("内容预览 (前 1500 字符):")
    print("-" * 80)
    print(note_content[:1500])
    print("...")
    print()


if __name__ == "__main__":
    asyncio.run(main())
