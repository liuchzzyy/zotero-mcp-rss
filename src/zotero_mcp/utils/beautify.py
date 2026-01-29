"""
Typora Orange Heart theme beautification for AI-generated notes.

Auto-applies when notes are created via workflow.
"""

import re


def beautify_ai_note(html: str) -> str:
    """
    Apply Typora Orange Heart theme to AI-generated note HTML.

    Reduces spacing, cleans redundant tags, and applies consistent styling.

    Args:
        html: Raw HTML from markdown_to_html conversion

    Returns:
        Beautified HTML with Typora Orange Heart styles
    """
    # Step 1: Deep clean HTML (remove paragraph pollution)
    html = _deep_clean_html(html)

    # Step 2: Apply inline styles with reduced spacing
    html = _apply_typora_styles(html)

    return html


def _deep_clean_html(html: str) -> str:
    """Remove redundant tags that cause spacing issues."""
    # Remove <p> wrappers around block elements
    html = re.sub(
        r"<p>\s*(<h[1-6][^>]*>.*?</h[1-6]>)\s*</p>", r"\1", html, flags=re.DOTALL
    )
    html = re.sub(r"<p>\s*(<ul[^>]*>.*?</ul>)\s*</p>", r"\1", html, flags=re.DOTALL)
    html = re.sub(r"<p>\s*(<ol[^>]*>.*?</ol>)\s*</p>", r"\1", html, flags=re.DOTALL)
    html = re.sub(r"<p>\s*(<hr\s*/?>\s*)</p>", r"\1", html)
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


def _apply_typora_styles(html: str) -> str:
    """Apply Typora Orange Heart inline styles with reduced spacing."""
    # Container style
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

    # Paragraphs - REDUCED spacing (0.5em instead of 0.8em)
    html = re.sub(
        r"<p(?:\s+[^>]*)?>",
        '<p style="margin: 0.5em 0; line-height: 1.6; color: black;">',
        html,
    )

    # H1 - REDUCED spacing (1em instead of 1.8em)
    html = re.sub(
        r"<h1(?:\s+[^>]*)?>",
        '<h1 style="font-size: 1.5rem; margin: 1em 0 0.6em; padding: 0; font-weight: bold; color: black;">',
        html,
    )

    # H2 - Orange background, REDUCED spacing
    h2_style = (
        "font-size: 1.3rem; "
        "margin: 1em 0 0.6em; "  # Reduced from 1.5em
        "padding: 8px 15px; "
        "font-weight: bold; "
        "background: rgb(239, 112, 96); "
        "color: #ffffff; "
        "border-bottom: 2px solid rgb(239, 112, 96); "
        "border-radius: 3px; "
        "display: block;"
    )
    html = re.sub(r"<h2(?:\s+[^>]*)?>", f'<h2 style="{h2_style}">', html)

    # H3 - REDUCED spacing
    html = re.sub(
        r"<h3(?:\s+[^>]*)?>",
        '<h3 style="font-size: 1.3rem; margin: 0.9em 0 0.5em; padding: 0; font-weight: bold; color: rgb(239, 112, 96);">',
        html,
    )

    # H4 - REDUCED spacing
    html = re.sub(
        r"<h4(?:\s+[^>]*)?>",
        '<h4 style="font-size: 1.2rem; margin: 0.8em 0 0.5em; padding: 0; font-weight: bold; color: rgb(239, 112, 96);">',
        html,
    )

    # Blockquote
    blockquote_style = (
        "display: block; "
        "font-size: 0.9em; "
        "margin: 0.8em 0; "  # Reduced from 1.2em
        "padding: 10px 10px 10px 20px; "
        "border-left: 4px solid rgb(239, 112, 96); "
        "background: #fff9f9; "
        "color: #6a737d; "
        "overflow: auto;"
    )
    html = re.sub(
        r"<blockquote(?:\s+[^>]*)?>", f'<blockquote style="{blockquote_style}">', html
    )

    # Links
    html = re.sub(
        r"<a\s+",
        '<a style="text-decoration: none; word-wrap: break-word; font-weight: bold; color: rgb(239, 112, 96); border-bottom: 1px solid rgb(239, 112, 96);" ',
        html,
    )

    # Code
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

    # Lists - REDUCED spacing
    ul_style = "margin: 0.8em 0; padding-left: 25px; color: black; list-style-type: disc;"  # Reduced from 1.2em
    ol_style = (
        "margin: 0.8em 0; padding-left: 25px; color: black; list-style-type: decimal;"
    )
    html = re.sub(r"<ul(?:\s+[^>]*)?>", f'<ul style="{ul_style}">', html)
    html = re.sub(r"<ol(?:\s+[^>]*)?>", f'<ol style="{ol_style}">', html)

    # List items - REDUCED spacing
    html = re.sub(
        r"<li(?:\s+[^>]*)?>",
        '<li style="margin: 0.2em 0; line-height: 1.6; color: rgb(1,1,1);">',  # Reduced from 0.4em
        html,
    )

    # HR
    html = re.sub(
        r"<hr(?:\s+[^>]*)?/?>",
        '<hr style="margin: 1em 0; border: 0; border-top: 1px solid #e0e0e0;"/>',  # Reduced from 1.5em
        html,
    )

    # Tables
    html = re.sub(
        r"<table(?:\s+[^>]*)?>",
        '<table style="display: table; text-align: left; border-collapse: collapse; margin: 0.8em 0;">',
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
