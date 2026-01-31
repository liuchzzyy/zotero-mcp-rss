#!/usr/bin/env python3
"""Test the BR tag fix by regenerating a note."""

import asyncio
import re
from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.services.workflow import get_workflow_service


async def main():
    ds = get_data_service()
    workflow = get_workflow_service()

    item_key = "7I72IMC4"

    print("=" * 80)
    print("测试 BR 标签清理")
    print("=" * 80)
    print()

    # Step 1: Delete existing note
    print("步骤 1: 删除现有笔记...")
    notes = await ds.get_notes(item_key)

    if notes:
        for note in notes:
            note_key = note.get("key")
            await ds.delete_item(note_key)
            print(f"  ✅ 删除笔记: {note_key}")
    else:
        print("  ⚠️  没有找到现有笔记")

    print()

    # Step 2: Get item data for analysis
    print("步骤 2: 获取条目数据...")
    item_data = await ds.get_item(item_key)
    if not item_data:
        print("  ❌ 未找到条目")
        return

    data = item_data.get("data", {})
    title = data.get("title")
    print(f"  ✅ 条目标题: {title[:60]}...")

    print()

    # Step 3: Get bundle
    print("步骤 3: 获取完整数据包...")
    from zotero_mcp.utils.batch_loader import BatchLoader

    batch_loader = BatchLoader(ds.item_service)
    bundles = await batch_loader.fetch_many_bundles(
        [item_key],
        include_fulltext=True,
        include_annotations=False,
        include_bibtex=False,
    )

    if not bundles:
        print("  ❌ 未获取到数据包")
        return

    bundle = bundles[0]
    fulltext = bundle.get("fulltext", "")

    if not fulltext:
        print("  ❌ 未获取到全文")
        return

    print(f"  ✅ 全文长度: {len(fulltext)} 字符")

    print()

    # Step 4: Analyze with LLM
    print("步骤 4: 使用 DeepSeek 分析...")
    from zotero_mcp.clients.llm import get_llm_client

    llm_client = get_llm_client(provider="deepseek")

    # Create a SearchResultItem-like object
    from zotero_mcp.models.common import SearchResultItem

    item = SearchResultItem(
        key=item_key,
        title=title,
        authors="Test Author",  # Simplified for testing
        date=None,
        doi=None,
        tags=[],
    )

    result = await workflow._analyze_single_item(
        item=item,
        bundle=bundle,
        llm_client=llm_client,
        skip_existing=False,
        template=None,
        dry_run=False,
        delete_old_notes=False,
        move_to_collection=None,
    )

    if result.success:
        print(f"  ✅ 分析成功，笔记 key: {result.note_key}")
    else:
        print(f"  ❌ 分析失败: {result.error}")
        return

    print()

    # Step 5: Check the new note for BR tags
    print("步骤 5: 检查新生成的笔记...")
    notes = await ds.get_notes(item_key)

    if not notes:
        print("  ❌ 未找到新生成的笔记")
        return

    note_key = notes[0].get("key")
    note_data = await ds.get_item(note_key)
    note_content = note_data.get("data", {}).get("note", "")

    # Count BR tags
    br_tags = re.findall(r"<br\s*/?>", note_content)
    br_between_lists = re.findall(r"(</ul>|</ol>)\s*<br\s*/?>", note_content)

    print(f"  总 <br> 标签数: {len(br_tags)}")
    print(f"  列表间的 <br> 标签数: {len(br_between_lists)}")

    print()
    print("=" * 80)
    print("测试结果")
    print("=" * 80)

    if len(br_tags) == 0:
        print("✅ 成功！所有 <br> 标签已被移除")
    elif len(br_between_lists) == 0:
        print(f"✅ 成功！列表间的 <br> 标签已被移除（剩余 {len(br_tags)} 个其他位置的 <br>）")
    else:
        print(f"⚠️  仍有 {len(br_between_lists)} 个列表间的 <br> 标签未被移除")

    print()


if __name__ == "__main__":
    asyncio.run(main())
