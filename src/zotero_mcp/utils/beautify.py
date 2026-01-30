"""
Typora Orange Heart theme beautification for AI-generated notes.

Auto-applies when notes are created via workflow.
Supports configurable themes via environment variables.
"""

import re

from zotero_mcp.utils.templates import get_note_theme_config


def beautify_ai_note(html: str) -> str:
    """
    Apply configured theme to AI-generated note HTML.

    Reduces spacing, cleans redundant tags, and applies consistent styling.
    Theme configuration is loaded from environment variables or config files.

    Args:
        html: Raw HTML from markdown_to_html conversion

    Returns:
        Beautified HTML with configured theme styles
    """
    # Step 1: Deep clean HTML (remove paragraph pollution)
    html = _deep_clean_html(html)

    # Step 2: Apply inline styles with configured theme
    theme_config = get_note_theme_config()
    html = _apply_theme_styles(html, theme_config)

    return html


def _deep_clean_html(html: str) -> str:
    """Remove redundant tags that cause spacing issues."""
    # Remove <p> wrappers around block elements (with or without attributes)
    # This needs to be done BEFORE styling is applied
    html = re.sub(
        r"<p\s+[^>]*>\s*(<h[1-6][^>]*>.*?</h[1-6]>)\s*</p>",
        r"\1",
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"<p>\s*(<h[1-6][^>]*>.*?</h[1-6]>)\s*</p>", r"\1", html, flags=re.DOTALL
    )

    html = re.sub(
        r"<p\s+[^>]*>\s*(<ul[^>]*>.*?</ul>)\s*</p>",
        r"\1",
        html,
        flags=re.DOTALL,
    )
    html = re.sub(r"<p>\s*(<ul[^>]*>.*?</ul>)\s*</p>", r"\1", html, flags=re.DOTALL)

    html = re.sub(
        r"<p\s+[^>]*>\s*(<ol[^>]*>.*?</ol>)\s*</p>",
        r"\1",
        html,
        flags=re.DOTALL,
    )
    html = re.sub(r"<p>\s*(<ol[^>]*>.*?</ol>)\s*</p>", r"\1", html, flags=re.DOTALL)

    html = re.sub(r"<p\s+[^>]*>\s*(<hr\s*/?>\s*)</p>", r"\1", html)
    html = re.sub(r"<p>\s*(<hr\s*/?>\s*)</p>", r"\1", html)

    html = re.sub(
        r"<p\s+[^>]*>\s*(<blockquote[^>]*>.*?</blockquote>)\s*</p>",
        r"\1",
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"<p>\s*(<blockquote[^>]*>.*?</blockquote>)\s*</p>",
        r"\1",
        html,
        flags=re.DOTALL,
    )

    # Remove <br/> pollution
    html = re.sub(r"(</h[1-6]>)\s*<br\s*/?>", r"\1", html)
    html = re.sub(r"(<[uo]l[^>]*>)\s*<br\s*/?>", r"\1", html)
    html = re.sub(r"<br\s*/?>\s*(<li[^>]*>)", r"\1", html)
    html = re.sub(r"(</li>)\s*<br\s*/?>", r"\1", html)

    # Fix nested paragraphs
    html = re.sub(r"<p>\s*<p>", "<p>", html)
    html = re.sub(r"</p>\s*</p>", "</p>", html)

    # Remove empty paragraphs
    html = re.sub(r"<p>\s*</p>", "", html)
    html = re.sub(r"<p>\s*<br\s*/?>\s*</p>", "", html)

    # Clean multiple <br/>
    html = re.sub(r"(<br\s*/?>\s*){2,}", r"<br/>", html)

    return html


def _apply_theme_styles(html: str, theme: dict[str, str]) -> str:
    """Apply theme inline styles based on configuration."""
    # Container style
    container_style = (
        f"max-width: {theme['max_width']}; "
        "font-size: 1rem; "
        "color: black; "
        "line-height: 1.6; "
        "word-spacing: 0; "
        "letter-spacing: 0; "
        'font-family: Optima-Regular, Optima, PingFangSC-light, PingFangTC-light, "PingFang SC", Cambria, Cochin, Georgia, Times, "Times New Roman", serif; '
        "padding: 10px;"
    )

    styled_html = f'<div style="{container_style}">'

    # Paragraphs
    para_margin = theme.get("paragraph_margin", "0.5em")
    html = re.sub(
        r"<p(?:\s+[^>]*)?>",
        f'<p style="margin: {para_margin} 0; line-height: 1.6; color: black;">',
        html,
    )

    # H1
    h1_margin = theme.get("h1_margin", "1em")
    html = re.sub(
        r"<h1(?:\s+[^>]*)?>",
        f'<h1 style="font-size: 1.5rem; margin: {h1_margin} 0 0.6em; padding: 0; font-weight: bold; color: black;">',
        html,
    )

    # H2 - with optional background
    h2_margin = theme.get("h2_margin", "1em")
    h2_bg = theme.get("h2_background", "transparent")
    h2_color = theme.get("h2_color", "black")
    h2_style = (
        f"font-size: 1.3rem; "
        f"margin: {h2_margin} 0 0.6em; "
        "padding: 8px 15px; "
        "font-weight: bold; "
        f"background: {h2_bg}; "
        f"color: {h2_color}; "
        f"border-bottom: 2px solid {theme['primary_color']}; "
        "border-radius: 3px; "
        "display: block;"
    )
    html = re.sub(r"<h2(?:\s+[^>]*)?>", f'<h2 style="{h2_style}">', html)

    # H3
    h3_margin = theme.get("h3_margin", "0.9em")
    html = re.sub(
        r"<h3(?:\s+[^>]*)?>",
        f'<h3 style="font-size: 1.3rem; margin: {h3_margin} 0 0.5em; padding: 0; font-weight: bold; color: {theme["primary_color"]};">',
        html,
    )

    # H4
    h4_margin = theme.get("h4_margin", "0.8em")
    html = re.sub(
        r"<h4(?:\s+[^>]*)?>",
        f'<h4 style="font-size: 1.2rem; margin: {h4_margin} 0 0.5em; padding: 0; font-weight: bold; color: {theme["primary_color"]};">',
        html,
    )

    # Blockquote
    blockquote_style = (
        "display: block; "
        "font-size: 0.9em; "
        f"margin: {theme.get('list_margin', '0.8em')} 0; "
        "padding: 10px 10px 10px 20px; "
        f"border-left: 4px solid {theme['blockquote_border']}; "
        f"background: {theme['blockquote_background']}; "
        "color: #6a737d; "
        "overflow: auto;"
    )
    html = re.sub(
        r"<blockquote(?:\s+[^>]*)?>", f'<blockquote style="{blockquote_style}">', html
    )

    # Links
    link_color = theme.get("link_color", "rgb(239, 112, 96)")
    html = re.sub(
        r"<a\s+",
        f'<a style="text-decoration: none; word-wrap: break-word; font-weight: bold; color: {link_color}; border-bottom: 1px solid {link_color};" ',
        html,
    )

    # Code
    code_style = (
        "font-size: 0.9rem; "
        "word-wrap: break-word; "
        "padding: 2px 4px; "
        "border-radius: 4px; "
        "margin: 0 2px; "
        f"color: {theme['code_color']}; "
        f"background-color: {theme['code_background']}; "
        "font-family: Operator Mono, Consolas, Monaco, Menlo, monospace; "
        "word-break: break-all;"
    )
    html = re.sub(r"<code(?:\s+[^>]*)?>", f'<code style="{code_style}">', html)

    # Bold
    html = re.sub(
        r"<b(?:\s+[^>]*)?>",
        f'<b style="font-weight: bold; color: {theme["primary_color"]};">',
        html,
    )
    html = re.sub(
        r"<strong(?:\s+[^>]*)?>",
        f'<strong style="font-weight: bold; color: {theme["primary_color"]};">',
        html,
    )

    # Lists
    list_margin = theme.get("list_margin", "0.8em")
    ul_style = f"margin: {list_margin} 0; padding-left: 25px; color: black; list-style-type: disc;"
    ol_style = f"margin: {list_margin} 0; padding-left: 25px; color: black; list-style-type: decimal;"
    html = re.sub(r"<ul(?:\s+[^>]*)?>", f'<ul style="{ul_style}">', html)
    html = re.sub(r"<ol(?:\s+[^>]*)?>", f'<ol style="{ol_style}">', html)

    # List items
    li_margin = theme.get("list_item_margin", "0.2em")
    html = re.sub(
        r"<li(?:\s+[^>]*)?>",
        f'<li style="margin: {li_margin} 0; line-height: 1.6; color: rgb(1,1,1);">',
        html,
    )

    # HR
    html = re.sub(
        r"<hr(?:\s+[^>]*)?/?>",
        '<hr style="margin: 1em 0; border: 0; border-top: 1px solid #e0e0e0;"/>',
        html,
    )

    # Tables
    html = re.sub(
        r"<table(?:\s+[^>]*)?>",
        f'<table style="display: table; text-align: left; border-collapse: collapse; margin: {list_margin} 0;">',
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
