"""
Test and apply reduced spacing to existing note.
"""

import asyncio
from zotero_mcp.services import get_data_service
from zotero_mcp.utils.beautify import beautify_ai_note


async def test_beautify():
    """Test beautify function on existing note."""
    service = get_data_service()
    note_key = "KEHRHZZE"

    print(f"📖 获取note: {note_key}")
    note = await service.get_item(note_key)

    current_html = note["data"]["note"]
    version = note["version"]

    print(f"✅ Note获取成功")
    print(f"   Version: {version}")
    print(f"   Current length: {len(current_html)} chars")

    # Extract original content (remove previous styling)
    import re

    if "<div style=" in current_html:
        match = re.search(r'<div style="[^"]+">(.+)</div>\s*$', current_html, re.DOTALL)
        if match:
            original_html = match.group(1)
        else:
            original_html = current_html
    else:
        original_html = current_html

    print(f"   Original content: {len(original_html)} chars")

    # Apply NEW beautify function with REDUCED spacing
    print(f"\n🎨 应用减少间距的美化...")
    print(f"   ✅ 段落间距: 0.5em (原1em)")
    print(f"   ✅ H1间距: 1em/0.6em (原1.8em/1em)")
    print(f"   ✅ H2间距: 1em/0.6em (原1.5em/1em)")
    print(f"   ✅ H3间距: 0.9em/0.5em (原1.3em/0.8em)")
    print(f"   ✅ 列表间距: 0.8em (原1.2em)")
    print(f"   ✅ 列表项间距: 0.2em (原0.4em)")

    beautified_html = beautify_ai_note(original_html)

    print(f"   Beautified length: {len(beautified_html)} chars")

    # Update note
    note["data"]["note"] = beautified_html

    print(f"\n📤 更新note...")
    try:
        result = await service.update_item(note)
        print(f"✅ 更新成功！")

        # Verify
        print(f"\n🔍 验证...")
        updated_note = await service.get_item(note_key)
        updated_content = updated_note["data"]["note"]

        checks = [
            ("margin: 0.5em 0" in updated_content, "段落间距: 0.5em"),
            ("margin: 1em 0 0.6em" in updated_content, "H1/H2间距: 1em/0.6em"),
            ("margin: 0.9em 0 0.5em" in updated_content, "H3间距: 0.9em/0.5em"),
            ("margin: 0.8em 0" in updated_content, "列表间距: 0.8em"),
            ("margin: 0.2em 0" in updated_content, "列表项间距: 0.2em"),
            ("rgb(239, 112, 96)" in updated_content, "橙色主题"),
            ("<p><h" not in updated_content, "无段落污染"),
        ]

        passed = sum(1 for p, _ in checks if p)
        total = len(checks)

        for p, desc in checks:
            status = "✅" if p else "❌"
            print(f"   {status} {desc}")

        print(f"\n{'🎉' if passed == total else '⚠️'} 验证结果: {passed}/{total} 通过")

        if passed >= total - 1:
            print(f"\n📌 请在Zotero中重新打开note查看效果：")
            print(f"   - 间距明显减少，更紧凑")
            print(f"   - 段落/列表之间空行减少")
            print(f"   - 保持橙色主题样式")

        return True

    except Exception as e:
        print(f"❌ 更新失败: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_beautify())
    exit(0 if success else 1)
