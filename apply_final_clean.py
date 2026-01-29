"""
FINAL VERSION: Deep HTML cleaning + Optimized Typora Orange Heart styles.
Removes ALL paragraph pollution and redundant tags.
"""

import asyncio
import re
from zotero_mcp.services import get_data_service


def deep_clean_html(html: str) -> str:
    """
    Aggressively clean HTML structure to remove pollution.
    """
    # Step 1: Remove wrapping <p> tags around block elements
    # Pattern: <p><h1...>...</h1></p> -> <h1...>...</h1>
    html = re.sub(
        r"<p>\s*(<h[1-6][^>]*>.*?</h[1-6]>)\s*</p>", r"\1", html, flags=re.DOTALL
    )

    # Pattern: <p><ul...>...</ul></p> -> <ul...>...</ul>
    html = re.sub(r"<p>\s*(<ul[^>]*>.*?</ul>)\s*</p>", r"\1", html, flags=re.DOTALL)
    html = re.sub(r"<p>\s*(<ol[^>]*>.*?</ol>)\s*</p>", r"\1", html, flags=re.DOTALL)

    # Pattern: <p><hr/></p> -> <hr/>
    html = re.sub(r"<p>\s*(<hr\s*/?>)\s*</p>", r"\1", html)

    # Pattern: <p><blockquote>...</blockquote></p> -> <blockquote>...</blockquote>
    html = re.sub(
        r"<p>\s*(<blockquote[^>]*>.*?</blockquote>)\s*</p>",
        r"\1",
        html,
        flags=re.DOTALL,
    )

    # Step 2: Remove <br/> tags that pollute structure
    # Remove <br/> after headers
    html = re.sub(r"(</h[1-6]>)\s*<br\s*/?>", r"\1", html)

    # Remove <br/> immediately after <ul> or <ol> opening
    html = re.sub(r"(<[uo]l[^>]*>)\s*<br\s*/?>", r"\1", html)

    # Remove <br/> immediately before <li>
    html = re.sub(r"<br\s*/?>\s*(<li[^>]*>)", r"\1", html)

    # Remove <br/> immediately after </li>
    html = re.sub(r"(</li>)\s*<br\s*/?>", r"\1", html)

    # Step 3: Fix nested paragraphs
    html = re.sub(r"<p>\s*<p>", "<p>", html)
    html = re.sub(r"</p>\s*</p>", "</p>", html)

    # Step 4: Remove empty paragraphs
    html = re.sub(r"<p>\s*</p>", "", html)
    html = re.sub(r"<p>\s*<br\s*/?>\s*</p>", "", html)

    # Step 5: Clean multiple consecutive <br/>
    html = re.sub(r"(<br\s*/?>\s*){2,}", r"<br/>", html)

    # Step 6: Remove trailing/leading <p> tags
    html = html.strip()
    if html.startswith("<p>") and not html.startswith("<p style="):
        html = html[3:]
    if html.endswith("</p>"):
        html = html[:-4]

    return html


def apply_final_typora_styles(html: str) -> str:
    """
    Apply完整的 Typora Orange Heart 主题with optimized spacing.
    """
    # First, deep clean the HTML
    html = deep_clean_html(html)

    # Styled container with Typora Orange Heart settings
    container_style = (
        "max-width: 860px; "
        "font-size: 1rem; "
        "color: black; "
        "line-height: 1.6; "
        "word-spacing: 0; "
        "letter-spacing: 0; "
        'font-family: Optima-Regular, Optima, PingFangSC-light, PingFangTC-light, "PingFang SC", Cambria, Cochin, Georgia, Times, "Times New Roman", serif; '
        "padding: 10px;"
    )

    styled_html = f'<div style="{container_style}">'

    # Apply inline styles to each element type

    # Paragraphs - proper spacing
    html = re.sub(
        r"<p(?:\s+[^>]*)?>",
        '<p style="margin: 0.8em 0; line-height: 1.6; color: black;">',
        html,
    )

    # H1 - Large, bold, black
    html = re.sub(
        r"<h1(?:\s+[^>]*)?>",
        '<h1 style="font-size: 1.5rem; margin: 1.8em 0 1em; padding: 0; font-weight: bold; color: black;">',
        html,
    )

    # H2 - Orange background, white text (signature Orange Heart style)
    h2_style = (
        "font-size: 1.3rem; "
        "margin: 1.5em 0 1em; "
        "padding: 8px 15px; "
        "font-weight: bold; "
        "background: rgb(239, 112, 96); "
        "color: #ffffff; "
        "border-bottom: 2px solid rgb(239, 112, 96); "
        "border-radius: 3px; "
        "display: block;"
    )
    html = re.sub(r"<h2(?:\s+[^>]*)?>", f'<h2 style="{h2_style}">', html)

    # H3 - Orange color
    html = re.sub(
        r"<h3(?:\s+[^>]*)?>",
        '<h3 style="font-size: 1.3rem; margin: 1.3em 0 0.8em; padding: 0; font-weight: bold; color: rgb(239, 112, 96);">',
        html,
    )

    # H4 - Orange color, smaller
    html = re.sub(
        r"<h4(?:\s+[^>]*)?>",
        '<h4 style="font-size: 1.2rem; margin: 1.2em 0 0.8em; padding: 0; font-weight: bold; color: rgb(239, 112, 96);">',
        html,
    )

    # Blockquote - Pink background with orange border
    blockquote_style = (
        "display: block; "
        "font-size: 0.9em; "
        "margin: 1.2em 0; "
        "padding: 10px 10px 10px 20px; "
        "border-left: 4px solid rgb(239, 112, 96); "
        "background: #fff9f9; "
        "color: #6a737d; "
        "overflow: auto;"
    )
    html = re.sub(
        r"<blockquote(?:\s+[^>]*)?>", f'<blockquote style="{blockquote_style}">', html
    )

    # Links - Orange with underline
    html = re.sub(
        r"<a\s+",
        '<a style="text-decoration: none; word-wrap: break-word; font-weight: bold; color: rgb(239, 112, 96); border-bottom: 1px solid rgb(239, 112, 96);" ',
        html,
    )

    # Code - Orange inline code
    code_style = (
        "font-size: 0.9rem; "
        "word-wrap: break-word; "
        "padding: 2px 4px; "
        "border-radius: 4px; "
        "margin: 0 2px; "
        "color: rgb(239, 112, 96); "
        "background-color: rgba(27,31,35,0.05); "
        "font-family: Operator Mono, Consolas, Monaco, Menlo, monospace; "
        "word-break: break-all;"
    )
    html = re.sub(r"<code(?:\s+[^>]*)?>", f'<code style="{code_style}">', html)

    # Bold - Orange
    html = re.sub(
        r"<b(?:\s+[^>]*)?>",
        '<b style="font-weight: bold; color: rgb(239, 112, 96);">',
        html,
    )
    html = re.sub(
        r"<strong(?:\s+[^>]*)?>",
        '<strong style="font-weight: bold; color: rgb(239, 112, 96);">',
        html,
    )

    # Lists - proper spacing
    ul_style = (
        "margin: 1.2em 0; padding-left: 25px; color: black; list-style-type: disc;"
    )
    ol_style = (
        "margin: 1.2em 0; padding-left: 25px; color: black; list-style-type: decimal;"
    )
    html = re.sub(r"<ul(?:\s+[^>]*)?>", f'<ul style="{ul_style}">', html)
    html = re.sub(r"<ol(?:\s+[^>]*)?>", f'<ol style="{ol_style}">', html)

    # List items - proper line height
    html = re.sub(
        r"<li(?:\s+[^>]*)?>",
        '<li style="margin: 0.4em 0; line-height: 1.7; color: rgb(1,1,1);">',
        html,
    )

    # HR - subtle divider
    html = re.sub(
        r"<hr(?:\s+[^>]*)?/?>",
        '<hr style="margin: 1.5em 0; border: 0; border-top: 1px solid #e0e0e0;"/>',
        html,
    )

    # Tables
    html = re.sub(
        r"<table(?:\s+[^>]*)?>",
        '<table style="display: table; text-align: left; border-collapse: collapse; margin: 1.2em 0;">',
        html,
    )
    html = re.sub(
        r"<th(?:\s+[^>]*)?>",
        '<th style="font-size: 1rem; border: 1px solid #ccc; padding: 8px 12px; text-align: left; font-weight: bold; background-color: #f0f0f0;">',
        html,
    )
    html = re.sub(
        r"<td(?:\s+[^>]*)?>",
        '<td style="font-size: 1rem; border: 1px solid #ccc; padding: 8px 12px; text-align: left;">',
        html,
    )

    # Italic
    html = re.sub(r"<i(?:\s+[^>]*)?>", '<i style="font-style: italic;">', html)
    html = re.sub(r"<em(?:\s+[^>]*)?>", '<em style="font-style: italic;">', html)

    styled_html += html + "</div>"

    return styled_html


async def apply_final_update():
    """Apply final cleaned and styled version."""
    service = get_data_service()
    note_key = "KEHRHZZE"

    print(f"📖 获取note: {note_key}")
    note = await service.get_item(note_key)

    current_html = note["data"]["note"]
    version = note["version"]

    print(f"✅ Note获取成功")
    print(f"   Version: {version}")
    print(f"   Current length: {len(current_html)} chars")

    # Extract original content
    if "<div style=" in current_html:
        print(f"   提取原始内容...")
        match = re.search(r'<div style="[^"]+">(.+)</div>\s*$', current_html, re.DOTALL)
        if match:
            original_html = match.group(1)
        else:
            original_html = current_html
    else:
        original_html = current_html

    print(f"   Original content: {len(original_html)} chars")

    # Apply final styling
    print(f"\n🧹 深度清理HTML（移除段落污染）...")
    print(f"   - 移除 <p> 包裹的标题和列表")
    print(f"   - 清理所有多余的 <br/> 标签")
    print(f"   - 修复嵌套段落")
    print(f"\n🎨 应用最终Typora Orange Heart样式...")

    styled_html = apply_final_typora_styles(original_html)

    print(f"   Final length: {len(styled_html)} chars")
    print(f"   Preview (first 500 chars):")
    print(f"   {styled_html[:500]}...")

    # Update
    note["data"]["note"] = styled_html

    print(f"\n📤 更新note...")
    try:
        result = await service.update_item(note)
        print(f"✅ 更新成功！")

        # Verify
        print(f"\n🔍 最终验证...")
        updated_note = await service.get_item(note_key)
        updated_content = updated_note["data"]["note"]

        checks = [
            ("rgb(239, 112, 96)" in updated_content, "橙色主题色存在"),
            (
                "<h2 style=" in updated_content
                and "background: rgb(239, 112, 96)" in updated_content,
                "H2橙色背景",
            ),
            (
                "margin: 1.5em 0 1em" in updated_content
                or "margin: 1.8em 0 1em" in updated_content,
                "优化的标题间距",
            ),
            ("margin: 1.2em 0" in updated_content, "优化的列表间距"),
            (updated_content.count("<p><h") == 0, "无段落包裹标题"),
            (updated_content.count("<p><ul") == 0, "无段落包裹列表"),
            ("<br/><li" not in updated_content, "无多余<br/>"),
        ]

        passed_count = sum(1 for passed, _ in checks if passed)
        total_count = len(checks)

        for passed, desc in checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {desc}")

        print(
            f"\n{'🎉' if passed_count == total_count else '⚠️'} 验证结果: {passed_count}/{total_count} 通过"
        )

        if passed_count >= total_count - 1:  # Allow 1 failure
            print(f"\n📌 请在Zotero中查看最终效果：")
            print(f"   1. 关闭当前note窗口")
            print(f"   2. 重新打开note (Item: 7INN7H7H)")
            print(f"   3. 应该看到：")
            print(f"      - H2标题：白字橙底，圆角边框")
            print(f"      - 清晰的段落和列表间距")
            print(f"      - 粗体文字为橙色")
            print(f"      - 整体使用Optima字体")

        return True

    except Exception as e:
        print(f"❌ 更新失败: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(apply_final_update())
    exit(0 if success else 1)
