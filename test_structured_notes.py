#!/usr/bin/env python3
"""Test structured note functionality."""

import asyncio
import sys
from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.services.workflow import get_workflow_service
from zotero_mcp.utils.batch_loader import BatchLoader
from zotero_mcp.clients.llm import get_llm_client
from zotero_mcp.models.common import SearchResultItem


async def main():
    ds = get_data_service()
    workflow = get_workflow_service()
    item_key = "7I72IMC4"

    print("=" * 80)
    print("测试结构化笔记功能")
    print("=" * 80)
    print()

    # Delete existing note
    print("步骤 1: 删除现有笔记...")
    notes = await ds.get_notes(item_key)
    if notes:
        for note in notes:
            await ds.delete_item(note.get("key"))
            print(f"  ✅ 删除笔记: {note.get('key')}")
    else:
        print("  ⚠️  没有现有笔记")
    print()

    # Get item
    print("步骤 2: 获取条目数据...")
    item_data = await ds.get_item(item_key)
    data = item_data.get("data", {})
    title = data.get("title")
    print(f"  ✅ 条目: {title[:60]}...")
    print()

    # Get bundle
    print("步骤 3: 获取数据包...")
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
    print(f"  ✅ 全文: {len(bundle.get('fulltext', ''))} 字符")
    print()

    # Create item object
    item = SearchResultItem(
        key=item_key,
        title=title,
        authors="Test",
        date=None,
        doi=None,
        tags=[],
    )

    # Get LLM client
    print("步骤 4: 调用 DeepSeek 分析（使用 JSON 格式）...")
    llm_client = get_llm_client(provider="deepseek")

    # Analyze with structured output enabled
    print("  ⏳ 分析中...")
    result = await workflow._analyze_single_item(
        item=item,
        bundle=bundle,
        llm_client=llm_client,
        skip_existing=False,
        template=None,
        dry_run=False,
        use_structured=True,  # Enable structured output
    )

    print()
    print("=" * 80)
    print("测试结果")
    print("=" * 80)
    print()

    if result.success:
        print(f"✅ 分析成功!")
        print(f"   笔记 key: {result.note_key}")
        print(f"   处理时间: {result.processing_time:.1f}秒")
    else:
        print(f"❌ 分析失败: {result.error}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
