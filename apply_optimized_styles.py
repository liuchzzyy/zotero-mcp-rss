"""
Clean HTML and apply optimized Typora Orange Heart inline styles.
Fixes spacing issues by removing redundant tags.
"""

import asyncio
import re
from zotero_mcp.services import get_data_service


def clean_html(html: str) -> str:
    """
    Clean up redundant HTML tags that cause spacing issues.
    """
    # Remove redundant </p><p> after headers
    html = re.sub(r"(</h[1-6]>)</p>\s*<p>", r"\1", html)

    # Remove <br/> immediately after <ul> or <ol>
    html = re.sub(r"(<u[lo][^>]*>)\s*<br/>", r"\1", html)

    # Remove <br/> immediately after </li>
    html = re.sub(r"(</li>)\s*<br/>", r"\1", html)

    # Remove nested <p><p>
    html = re.sub(r"<p>\s*<p>", "<p>", html)
    html = re.sub(r"</p>\s*</p>", "</p>", html)

    # Remove empty <p></p>
    html = re.sub(r"<p>\s*</p>", "", html)

    # Clean up multiple consecutive <br/>
    html = re.sub(r"(<br\s*/?>)\s*(<br\s*/?>)+", r"\1", html)

    return html


def apply_optimized_inline_styles(html: str) -> str:
    """
    Apply Typora Orange Heart theme with optimized spacing.
    """
    # Clean HTML first
    html = clean_html(html)

    # Wrap in styled container
    styled_html = "<div style=\"max-width: 860px; font-size: 1rem; color: black; line-height: 1.6; word-spacing: 0; letter-spacing: 0; font-family: Optima-Regular, Optima, PingFangSC-light, PingFangTC-light, 'PingFang SC', Cambria, Cochin, Georgia, Times, 'Times New Roman', serif;\">"

    # Style paragraphs - add proper spacing
    html = re.sub(
        r"<p>",
        r'<p style="margin: 0.5rem 0; line-height: 1.5rem; color: black;">',
        html,
    )

    # Style H1 - larger margin for visual separation
    html = re.sub(
        r"<h1>",
        r'<h1 style="font-size: 1.5rem; margin: 1.5em 0 1em; padding: 0; font-weight: bold; color: black;">',
        html,
    )

    # Style H2 - Orange background with better padding
    html = re.sub(
        r"<h2>",
        r'<h2 style="font-size: 1.3rem; margin: 1.5em 0 1em; padding: 8px 15px; font-weight: bold; background: rgb(239, 112, 96); color: #ffffff; border-bottom: 2px solid rgb(239, 112, 96); border-radius: 3px;">',
        html,
    )

    # Style H3 - Orange color, good spacing
    html = re.sub(
        r"<h3>",
        r'<h3 style="font-size: 1.3rem; margin: 1.3em 0 0.8em; padding: 0; font-weight: bold; color: rgb(239, 112, 96);">',
        html,
    )

    # Style H4
    html = re.sub(
        r"<h4>",
        r'<h4 style="font-size: 1.2rem; margin: 1.2em 0 0.8em; padding: 0; font-weight: bold; color: rgb(239, 112, 96);">',
        html,
    )

    # Style blockquote - Pink background
    html = re.sub(
        r"<blockquote>",
        r'<blockquote style="display: block; font-size: 0.9em; margin: 1.2em 0; padding: 10px 10px 10px 20px; border-left: 4px solid rgb(239, 112, 96); background: #fff9f9; color: #6a737d; overflow: auto;">',
        html,
    )

    # Style links - Orange with underline
    html = re.sub(
        r"<a\s+([^>]*)>",
        r'<a \1 style="text-decoration: none; word-wrap: break-word; font-weight: bold; color: rgb(239, 112, 96); border-bottom: 1px solid rgb(239, 112, 96);">',
        html,
    )

    # Style code - Orange inline code
    html = re.sub(
        r"<code>",
        r'<code style="font-size: 0.9rem; word-wrap: break-word; padding: 2px 4px; border-radius: 4px; margin: 0 2px; color: rgb(239, 112, 96); background-color: rgba(27,31,35,0.05); font-family: Operator Mono, Consolas, Monaco, Menlo, monospace; word-break: break-all;">',
        html,
    )

    # Style bold - Orange color
    html = re.sub(
        r"<b>", r'<b style="font-weight: bold; color: rgb(239, 112, 96);">', html
    )

    # Style strong - Orange color
    html = re.sub(
        r"<strong>",
        r'<strong style="font-weight: bold; color: rgb(239, 112, 96);">',
        html,
    )

    # Style UL - better spacing
    html = re.sub(
        r"<ul>",
        r'<ul style="margin: 1em 0; padding-left: 25px; color: black; list-style-type: disc;">',
        html,
    )

    # Style OL - better spacing
    html = re.sub(
        r"<ol>",
        r'<ol style="margin: 1em 0; padding-left: 25px; color: black; list-style-type: decimal;">',
        html,
    )

    # Style LI - proper line spacing
    html = re.sub(
        r"<li>",
        r'<li style="margin: 0.3em 0; line-height: 1.7rem; color: rgb(1,1,1);">',
        html,
    )

    # Style HR - subtle divider
    html = re.sub(
        r"<hr\s*/?>",
        r'<hr style="margin: 1.5em 0; border: 0; border-top: 1px solid #e0e0e0;"/>',
        html,
    )

    # Style tables
    html = re.sub(
        r"<table>",
        r'<table style="display: table; text-align: left; border-collapse: collapse; margin: 1em 0;">',
        html,
    )

    html = re.sub(
        r"<th>",
        r'<th style="font-size: 1rem; border: 1px solid #ccc; padding: 8px 12px; text-align: left; font-weight: bold; background-color: #f0f0f0;">',
        html,
    )

    html = re.sub(
        r"<td>",
        r'<td style="font-size: 1rem; border: 1px solid #ccc; padding: 8px 12px; text-align: left;">',
        html,
    )

    # Style italic
    html = re.sub(r"<i>", r'<i style="font-style: italic; color: inherit;">', html)

    # Style em
    html = re.sub(r"<em>", r'<em style="font-style: italic; color: inherit;">', html)

    styled_html += html + "</div>"

    return styled_html


async def apply_optimized_styles():
    """Apply optimized Typora Orange Heart theme."""
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
    if "<div style=" in current_html and "</div>" in current_html:
        print(f"   移除之前的样式...")
        # Extract content between outer div
        match = re.search(r'<div style="[^"]+">(.+)</div>\s*$', current_html, re.DOTALL)
        if match:
            original_html = match.group(1)
            print(f"   提取原始内容: {len(original_html)} chars")
        else:
            original_html = current_html
    else:
        original_html = current_html

    # Apply optimized styles
    print(f"\n🎨 应用优化的Typora Orange Heart主题...")
    print(f"   - 清理多余标签（<br/>, 嵌套<p>）")
    print(f"   - 优化间距（margin, padding）")
    print(f"   - 应用完整配色方案")

    styled_html = apply_optimized_inline_styles(original_html)

    print(f"   Styled length: {len(styled_html)} chars")

    # Update note
    note["data"]["note"] = styled_html

    print(f"\n📤 更新note到Zotero...")
    try:
        result = await service.update_item(note)
        print(f"✅ 更新成功！")

        # Verify
        print(f"\n🔍 验证更新...")
        updated_note = await service.get_item(note_key)
        updated_content = updated_note["data"]["note"]

        checks = [
            ('style="' in updated_content, "Inline styles present"),
            ("rgb(239, 112, 96)" in updated_content, "Orange color present"),
            ("<h2 style=" in updated_content, "H2 styled"),
            ("margin: 1.5em" in updated_content, "Optimized margins"),
            ("padding: 8px" in updated_content, "Optimized padding"),
            ("<br/><li" not in updated_content, "Cleaned redundant <br/>"),
        ]

        all_pass = True
        for passed, desc in checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {desc}")
            all_pass = all_pass and passed

        if all_pass:
            print(f"\n🎉 所有验证通过！")
            print(f"\n📌 请在Zotero中重新打开note查看优化后的效果：")
            print(f"   - H2标题：橙色背景 + 白色文字 + 圆角")
            print(f"   - 段落：合适的行间距和段落间距")
            print(f"   - 列表：清晰的间距，无多余换行")
            print(f"   - 粗体：橙色突出显示")
            print(f"\n💡 提示：关闭note窗口后重新打开以看到最新效果")
        else:
            print(f"\n⚠️ 部分验证未通过")

        return True

    except Exception as e:
        print(f"❌ 更新失败: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(apply_optimized_styles())
    exit(0 if success else 1)
