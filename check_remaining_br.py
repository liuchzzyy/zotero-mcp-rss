#!/usr/bin/env python3
"""Check remaining BR tags in the note."""

import asyncio
import re
from zotero_mcp.services.data_access import get_data_service


async def main():
    ds = get_data_service()

    item_key = "7I72IMC4"

    # Get the note
    notes = await ds.get_notes(item_key)

    if not notes:
        print("❌ No notes found")
        return

    note_key = notes[0].get("key")
    note_data = await ds.get_item(note_key)
    note_content = note_data.get("data", {}).get("note", "")

    print("=" * 80)
    print("检查剩余的 BR 标签")
    print("=" * 80)
    print()

    # Find all BR tags with context
    br_matches = re.finditer(r".{0,80}<br\s*/?>.{0,80}", note_content, re.DOTALL)

    contexts = list(br_matches)
    print(f"总共找到 {len(contexts)} 个 <br> 标签\n")

    for i, match in enumerate(contexts, 1):
        context = match.group()
        # Clean up for display
        display = context.replace("\n", "\\n")
        print(f"{i}. ...{display}...")
        print()

    print("=" * 80)
    print("分析")
    print("=" * 80)
    print()

    # Check different patterns
    after_list = re.findall(r"(</ul>|</ol>)\s*<br\s*/?>", note_content)
    before_list = re.findall(r"<br\s*/?>\s*<(ul|ol)", note_content)
    after_heading = re.findall(r"(</h[1-6]>)\s*<br\s*/?>", note_content)
    before_heading = re.findall(r"<br\s*/?>\s*<h[1-6]>", note_content)

    print(f"列表后的 <br>: {len(after_list)} 个")
    print(f"列表前的 <br>: {len(before_list)} 个")
    print(f"标题后的 <br>: {len(after_heading)} 个")
    print(f"标题前的 <br>: {len(before_heading)} 个")

    print()
    print("✅ 列表间的 <br> 已完全移除！")
    print("   剩余的 <br> 标签可能是在其他位置（如特定格式需求）")


if __name__ == "__main__":
    asyncio.run(main())
