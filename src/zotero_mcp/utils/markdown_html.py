"""
Markdown to HTML conversion utilities for Zotero MCP.

Provides bidirectional conversion between Markdown and HTML,
specifically optimized for Zotero notes.
"""

import re


def markdown_to_html(markdown: str) -> str:
    """
    Convert Markdown to HTML suitable for Zotero notes.

    Supports:
    - Headers (h1-h6)
    - Bold, italic, code
    - Lists (ordered and unordered)
    - Blockquotes
    - Tables
    - Links
    - Horizontal rules
    - Line breaks

    Args:
        markdown: Markdown text

    Returns:
        HTML string suitable for Zotero notes
    """
    if not markdown:
        return ""

    html = markdown

    # Headers (h1-h6)
    for level in range(6, 0, -1):
        pattern = r"^" + "#" * level + r"\s+(.+)$"
        replacement = f"<h{level}>\\1</h{level}>"
        html = re.sub(pattern, replacement, html, flags=re.MULTILINE)

    # Horizontal rules
    html = re.sub(r"^---+$", "<hr/>", html, flags=re.MULTILINE)
    html = re.sub(r"^\*\*\*+$", "<hr/>", html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", html)  # Bold+italic
    html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html)  # Bold
    html = re.sub(r"\*(.+?)\*", r"<i>\1</i>", html)  # Italic
    html = re.sub(r"__(.+?)__", r"<b>\1</b>", html)  # Bold alternative
    html = re.sub(r"_(.+?)_", r"<i>\1</i>", html)  # Italic alternative

    # Inline code
    html = re.sub(r"`(.+?)`", r"<code>\1</code>", html)

    # Links
    html = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', html)

    # Unordered lists
    html = _convert_unordered_lists(html)

    # Ordered lists
    html = _convert_ordered_lists(html)

    # Blockquotes
    html = _convert_blockquotes(html)

    # Tables
    html = _convert_tables(html)

    # Paragraphs (wrap non-tagged content)
    html = _wrap_paragraphs(html)

    # Line breaks
    html = html.replace("\n\n", "</p><p>")
    html = html.replace("\n", "<br/>")

    return html


def html_to_markdown(html: str) -> str:
    """
    Convert HTML to Markdown.

    Useful for extracting text from Zotero notes.

    Args:
        html: HTML string

    Returns:
        Markdown text
    """
    if not html:
        return ""

    md = html

    # Remove HTML comments
    md = re.sub(r"<!--.*?-->", "", md, flags=re.DOTALL)

    # Headers
    for level in range(1, 7):
        md = re.sub(
            rf"<h{level}[^>]*>(.*?)</h{level}>",
            lambda m, level=level: "#" * level + " " + m.group(1),
            md,
            flags=re.IGNORECASE | re.DOTALL,
        )

    # Bold and italic
    md = re.sub(r"<b>(.*?)</b>", r"**\1**", md, flags=re.IGNORECASE | re.DOTALL)
    md = re.sub(
        r"<strong>(.*?)</strong>", r"**\1**", md, flags=re.IGNORECASE | re.DOTALL
    )
    md = re.sub(r"<i>(.*?)</i>", r"*\1*", md, flags=re.IGNORECASE | re.DOTALL)
    md = re.sub(r"<em>(.*?)</em>", r"*\1*", md, flags=re.IGNORECASE | re.DOTALL)

    # Code
    md = re.sub(r"<code>(.*?)</code>", r"`\1`", md, flags=re.IGNORECASE | re.DOTALL)

    # Links
    md = re.sub(
        r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>',
        r"[\2](\1)",
        md,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Lists
    md = re.sub(
        r"<ul[^>]*>(.*?)</ul>", _html_ul_to_md, md, flags=re.IGNORECASE | re.DOTALL
    )
    md = re.sub(
        r"<ol[^>]*>(.*?)</ol>", _html_ol_to_md, md, flags=re.IGNORECASE | re.DOTALL
    )

    # Blockquotes
    md = re.sub(
        r"<blockquote[^>]*>(.*?)</blockquote>",
        lambda m: "\n".join("> " + line for line in m.group(1).strip().split("\n")),
        md,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Horizontal rules
    md = re.sub(r"<hr\s*/?>", "\n---\n", md, flags=re.IGNORECASE)

    # Paragraphs and line breaks
    md = re.sub(r"<p[^>]*>", "\n", md, flags=re.IGNORECASE)
    md = re.sub(r"</p>", "\n", md, flags=re.IGNORECASE)
    md = re.sub(r"<br\s*/?>", "\n", md, flags=re.IGNORECASE)

    # Remove remaining HTML tags
    md = re.sub(r"<[^>]+>", "", md)

    # Clean up whitespace
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = md.strip()

    return md


# -------------------- Helper Functions --------------------


def _convert_unordered_lists(text: str) -> str:
    """Convert Markdown unordered lists to HTML."""
    lines = text.split("\n")
    result = []
    in_list = False

    for line in lines:
        if re.match(r"^[\s]*[-*+]\s+", line):
            if not in_list:
                result.append("<ul>")
                in_list = True
            item = re.sub(r"^[\s]*[-*+]\s+", "", line)
            result.append(f"<li>{item}</li>")
        else:
            if in_list:
                result.append("</ul>")
                in_list = False
            result.append(line)

    if in_list:
        result.append("</ul>")

    return "\n".join(result)


def _convert_ordered_lists(text: str) -> str:
    """Convert Markdown ordered lists to HTML."""
    lines = text.split("\n")
    result = []
    in_list = False

    for line in lines:
        if re.match(r"^[\s]*\d+\.\s+", line):
            if not in_list:
                result.append("<ol>")
                in_list = True
            item = re.sub(r"^[\s]*\d+\.\s+", "", line)
            result.append(f"<li>{item}</li>")
        else:
            if in_list:
                result.append("</ol>")
                in_list = False
            result.append(line)

    if in_list:
        result.append("</ol>")

    return "\n".join(result)


def _convert_blockquotes(text: str) -> str:
    """Convert Markdown blockquotes to HTML."""
    lines = text.split("\n")
    result = []
    in_quote = False
    quote_lines = []

    for line in lines:
        if line.strip().startswith(">"):
            if not in_quote:
                in_quote = True
            quote_lines.append(line.strip()[1:].strip())
        else:
            if in_quote:
                result.append(f"<blockquote>{'<br/>'.join(quote_lines)}</blockquote>")
                quote_lines = []
                in_quote = False
            result.append(line)

    if in_quote:
        result.append(f"<blockquote>{'<br/>'.join(quote_lines)}</blockquote>")

    return "\n".join(result)


def _convert_tables(text: str) -> str:
    """Convert Markdown tables to HTML."""
    lines = text.split("\n")
    result = []
    in_table = False
    table_lines = []

    for line in lines:
        if "|" in line:
            if not in_table:
                in_table = True
            table_lines.append(line)
        else:
            if in_table:
                result.append(_build_html_table(table_lines))
                table_lines = []
                in_table = False
            result.append(line)

    if in_table:
        result.append(_build_html_table(table_lines))

    return "\n".join(result)


def _build_html_table(lines: list[str]) -> str:
    """Build HTML table from Markdown table lines."""
    if not lines:
        return ""

    html = ["<table border='1'>"]

    for i, line in enumerate(lines):
        # Skip separator line (e.g., |---|---|)
        if re.match(r"^\s*\|[\s\-:]+\|\s*$", line):
            continue

        cells = [cell.strip() for cell in line.split("|") if cell.strip()]

        # First line is header
        if i == 0:
            html.append("<tr>")
            for cell in cells:
                html.append(f"<th>{cell}</th>")
            html.append("</tr>")
        else:
            html.append("<tr>")
            for cell in cells:
                html.append(f"<td>{cell}</td>")
            html.append("</tr>")

    html.append("</table>")
    return "".join(html)


def _wrap_paragraphs(text: str) -> str:
    """Wrap plain text lines in paragraph tags."""
    lines = text.split("\n")
    result = []
    in_tag = False

    for line in lines:
        stripped = line.strip()

        # Check if line is already in a tag
        if stripped.startswith("<") or in_tag:
            result.append(line)
            # Track if we're in a multi-line tag
            if stripped.startswith("<") and not stripped.endswith(">"):
                in_tag = True
            elif stripped.endswith(">"):
                in_tag = False
        elif stripped:  # Non-empty line not in tag
            result.append(f"<p>{line}</p>")
        else:
            result.append(line)

    return "\n".join(result)


def _html_ul_to_md(match: re.Match) -> str:
    """Convert HTML unordered list to Markdown."""
    content = match.group(1)
    items = re.findall(r"<li[^>]*>(.*?)</li>", content, re.IGNORECASE | re.DOTALL)
    return "\n" + "\n".join(f"- {item.strip()}" for item in items) + "\n"


def _html_ol_to_md(match: re.Match) -> str:
    """Convert HTML ordered list to Markdown."""
    content = match.group(1)
    items = re.findall(r"<li[^>]*>(.*?)</li>", content, re.IGNORECASE | re.DOTALL)
    return (
        "\n"
        + "\n".join(f"{i + 1}. {item.strip()}" for i, item in enumerate(items))
        + "\n"
    )
