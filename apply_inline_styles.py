"""
Apply Typora Orange Heart theme using INLINE STYLES (no <style> tag).
This ensures Zotero's note editor will display the styles correctly.
"""

import asyncio
import re
from zotero_mcp.services import get_data_service


def apply_inline_styles(html: str) -> str:
    """
    Apply Typora Orange Heart theme colors using inline styles.
    This converts CSS rules to inline style attributes.
    """
    # Define style mappings based on Typora Orange Heart theme

    # Wrap everything in a styled div
    styled_html = f"<div style=\"max-width: 860px; font-size: 1rem; color: black; line-height: 1.6; font-family: Optima-Regular, Optima, PingFangSC-light, PingFangTC-light, 'PingFang SC', Cambria, Cochin, Georgia, Times, 'Times New Roman', serif;\">"

    # Process H1 tags
    html = re.sub(
        r"<h1>(.*?)</h1>",
        r'<h1 style="font-size: 1.5rem; margin: 1.2em 0 1em; font-weight: bold; color: black;">\1</h1>',
        html,
        flags=re.DOTALL,
    )

    # Process H2 tags - Orange background with white text
    html = re.sub(
        r"<h2>(.*?)</h2>",
        r'<h2 style="font-size: 1.3rem; margin: 1.2em 0 1em; font-weight: bold; background: rgb(239, 112, 96); color: #ffffff; padding: 5px 10px; border-bottom: 2px solid rgb(239, 112, 96);">\1</h2>',
        html,
        flags=re.DOTALL,
    )

    # Process H3 tags
    html = re.sub(
        r"<h3>(.*?)</h3>",
        r'<h3 style="font-size: 1.3rem; margin: 1.2em 0 1em; font-weight: bold; color: rgb(239, 112, 96);">\1</h3>',
        html,
        flags=re.DOTALL,
    )

    # Process H4 tags
    html = re.sub(
        r"<h4>(.*?)</h4>",
        r'<h4 style="font-size: 1.2rem; margin: 1.2em 0 1em; font-weight: bold; color: rgb(239, 112, 96);">\1</h4>',
        html,
        flags=re.DOTALL,
    )

    # Process blockquote
    html = re.sub(
        r"<blockquote>(.*?)</blockquote>",
        r'<blockquote style="display: block; font-size: 0.9em; overflow: auto; border-left: 3px solid rgb(239, 112, 96); color: #6a737d; padding: 10px 10px 10px 20px; margin: 20px 0; background: #fff9f9;">\1</blockquote>',
        html,
        flags=re.DOTALL,
    )

    # Process links
    html = re.sub(
        r"<a\s+([^>]*)>",
        r'<a \1 style="text-decoration: none; font-weight: bold; color: rgb(239, 112, 96); border-bottom: 1px solid rgb(239, 112, 96);">',
        html,
    )

    # Process code tags
    html = re.sub(
        r"<code>(.*?)</code>",
        r'<code style="font-size: 0.9rem; padding: 2px 4px; border-radius: 4px; margin: 0 2px; color: rgb(239, 112, 96); background-color: rgba(27,31,35,0.05); font-family: Consolas, Monaco, Menlo, monospace;">\1</code>',
        html,
        flags=re.DOTALL,
    )

    # Process bold tags
    html = re.sub(
        r"<b>(.*?)</b>",
        r'<b style="font-weight: bold; color: rgb(239, 112, 96);">\1</b>',
        html,
        flags=re.DOTALL,
    )

    # Process strong tags
    html = re.sub(
        r"<strong>(.*?)</strong>",
        r'<strong style="font-weight: bold; color: rgb(239, 112, 96);">\1</strong>',
        html,
        flags=re.DOTALL,
    )

    # Process lists
    html = re.sub(
        r"<ul>", r'<ul style="margin: 8px 0; padding-left: 25px; color: black;">', html
    )

    html = re.sub(
        r"<ol>", r'<ol style="margin: 8px 0; padding-left: 25px; color: black;">', html
    )

    html = re.sub(
        r"<li>(.*?)</li>",
        r'<li style="margin: 5px 0; line-height: 1.7rem; color: rgb(1,1,1); font-weight: 500;">\1</li>',
        html,
        flags=re.DOTALL,
    )

    # Process tables
    html = re.sub(
        r"<table>",
        r'<table style="display: table; text-align: left; border-collapse: collapse;">',
        html,
    )

    html = re.sub(
        r"<th>(.*?)</th>",
        r'<th style="font-size: 1rem; border: 1px solid #ccc; padding: 5px 10px; text-align: left; font-weight: bold; background-color: #f0f0f0;">\1</th>',
        html,
        flags=re.DOTALL,
    )

    html = re.sub(
        r"<td>(.*?)</td>",
        r'<td style="font-size: 1rem; border: 1px solid #ccc; padding: 5px 10px; text-align: left;">\1</td>',
        html,
        flags=re.DOTALL,
    )

    styled_html += html + "</div>"

    return styled_html


async def apply_inline_styles_and_update():
    """Apply Typora Orange Heart theme using inline styles."""
    service = get_data_service()
    note_key = "KEHRHZZE"

    print(f"📖 获取note: {note_key}")
    note = await service.get_item(note_key)

    current_html = note["data"]["note"]
    version = note["version"]

    print(f"✅ Note获取成功")
    print(f"   Version: {version}")
    print(f"   Current length: {len(current_html)} chars")

    # Remove previous styling if exists
    if "<style>" in current_html and "</style>" in current_html:
        print(f"   移除之前的<style>标签...")
        # Extract original content between <div id="write"> and </div>
        match = re.search(r'<div id="write">(.*)</div>\s*$', current_html, re.DOTALL)
        if match:
            original_html = match.group(1)
            print(f"   提取原始内容: {len(original_html)} chars")
        else:
            print(f'   未找到<div id="write">，使用当前内容')
            original_html = current_html
    else:
        original_html = current_html

    # Apply inline styles
    print(f"\n🎨 应用内联样式（Typora Orange Heart主题）...")
    styled_html = apply_inline_styles(original_html)

    print(f"   Styled length: {len(styled_html)} chars")
    print(f"   Preview (first 300 chars):")
    print(f"   {styled_html[:300]}...")

    # Update note content
    note["data"]["note"] = styled_html

    print(f"\n📤 更新note到Zotero...")
    try:
        result = await service.update_item(note)
        print(f"✅ 更新成功！")

        # Verify update
        print(f"\n🔍 验证更新...")
        updated_note = await service.get_item(note_key)
        updated_content = updated_note["data"]["note"]

        checks = [
            ('style="' in updated_content, "Inline styles present"),
            (
                "rgb(239, 112, 96)" in updated_content or "#EF7060" in updated_content,
                "Orange Heart color present",
            ),
            ("<h2 style=" in updated_content, "H2 styled"),
            (
                "<b style=" in updated_content or "<strong style=" in updated_content,
                "Bold styled",
            ),
        ]

        all_pass = True
        for passed, desc in checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {desc}")
            all_pass = all_pass and passed

        if all_pass:
            print(f"\n🎉 所有验证通过！")
            print(f"\n📌 请在Zotero中刷新或重新打开note查看效果：")
            print(f"   Item Key: 7INN7H7H")
            print(f"   Note Key: {note_key}")
            print(f"\n💡 提示：")
            print(f"   1. 在Zotero中，关闭note窗口后重新打开")
            print(f"   2. 或者右键note选择'刷新'")
            print(f"   3. 如果还是看不到，尝试重启Zotero")
        else:
            print(f"\n⚠️ 部分验证未通过，请检查")

        return True

    except Exception as e:
        print(f"❌ 更新失败: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(apply_inline_styles_and_update())
    exit(0 if success else 1)
