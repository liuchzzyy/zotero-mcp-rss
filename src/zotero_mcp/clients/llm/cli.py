"""
CLI-based LLM client for Zotero MCP.

Provides Claude CLI integration for analyzing research papers.
Launches claude command as subprocess, streams output to terminal,
and captures the full result for saving as Zotero notes.

Features:
- File-based prompt passing (avoids stdin size limits)
- Real-time streaming output to terminal
- Configurable CLI command and timeout
"""

import asyncio
import logging
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from zotero_mcp.utils.data.templates import (
    format_multimodal_section,
    get_analysis_template,
)

logger = logging.getLogger(__name__)

# -------------------- Configuration --------------------

CLI_LLM_COMMAND = os.getenv("CLI_LLM_COMMAND", "claude")
CLI_LLM_TIMEOUT = int(os.getenv("CLI_LLM_TIMEOUT", "300"))


# -------------------- CLI LLM Client --------------------


class CLILLMClient:
    """
    Claude CLI-based LLM client for paper analysis.

    Uses the local `claude` command (Claude Code CLI) to analyze papers.
    Writes prompt content to a temporary file, then invokes the CLI
    with --allowedTools "Read" so it can read the file.

    Output is streamed to terminal in real-time and captured for
    subsequent saving as a Zotero note.
    """

    def __init__(
        self,
        cli_command: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ):
        """
        Initialize CLI LLM client.

        Args:
            cli_command: CLI executable name (default: "claude")
            model: Model to use (passed via --model flag if set)
            timeout: Subprocess timeout in seconds (default: 300)
        """
        self.cli_command = cli_command or CLI_LLM_COMMAND
        self.model = model
        self.timeout = timeout or CLI_LLM_TIMEOUT
        self.provider = "claude-cli"

        # Verify CLI is available
        if not shutil.which(self.cli_command):
            logger.warning(
                f"CLI command '{self.cli_command}' not found in PATH. "
                f"Analysis will fail unless it becomes available."
            )

        logger.info(
            f"Initialized CLI LLM client: "
            f"command={self.cli_command}, timeout={self.timeout}s"
        )

    async def analyze_paper(
        self,
        title: str,
        authors: str | None,
        journal: str | None,
        date: str | None,
        doi: str | None,
        fulltext: str,
        annotations: list[dict[str, Any]] | None = None,
        template: str | None = None,
        images: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Analyze a research paper using Claude CLI.

        Writes the paper content and analysis template to a temporary file,
        then invokes the CLI to read and analyze it.

        Args:
            title: Paper title
            authors: Authors
            journal: Journal name
            date: Publication date
            doi: DOI
            fulltext: Full text content
            annotations: PDF annotations
            template: Custom analysis template/instruction
            images: PDF images (base64 format) - embedded in prompt

        Returns:
            Markdown-formatted analysis
        """
        # Build annotations section
        annotations_section = ""
        if annotations:
            annotations_section = "\n## PDF 批注\n\n"
            for i, ann in enumerate(annotations, 1):
                ann_type = ann.get("type", "note")
                text = ann.get("text", "")
                comment = ann.get("comment", "")
                page = ann.get("page", "")

                annotations_section += f"**批注 {i}** ({ann_type})"
                if page:
                    annotations_section += f", 第{page}页"
                annotations_section += ":\n"

                if text:
                    annotations_section += f"> {text}\n"
                if comment:
                    annotations_section += f"*评论*: {comment}\n"
                annotations_section += "\n"

        # Build images section
        images_section = ""
        if images:
            images_section = "\n## Images\n\n"
            for i, img in enumerate(images, 1):
                page_num = img.get("page", "?")
                images_section += f"### Image {i} (Page {page_num})\n"
                if img.get("format") == "base64":
                    # For Claude CLI, embed base64 as markdown image
                    images_section += (
                        f"![Image](data:image/png;base64,{img['content']})\n"
                    )
                images_section += f"*Figure {i}*\n\n"

        # Build prompt content for the file
        if template:
            file_content = f"""你是一位专业的科研文献分析助手。请仔细阅读以下论文内容，并按照提供的模板结构进行分析。

## 论文基本信息

- **标题**: {title or "未知"}
- **作者**: {authors or "未知"}
- **期刊**: {journal or "未知"}
- **发表日期**: {date or "未知"}
- **DOI**: {doi or "未知"}

## 论文全文

{fulltext[:50000]}

{annotations_section}
{images_section}

---

## 分析要求

请阅读上述内容，并严格按照以下模板格式生成分析报告：

{template}

**注意事项**:
1. 请保持客观、专业的分析风格
2. 使用中文撰写分析内容
3. 如果模板中有占位符(如 ${{...}})，请替换为实际分析内容
4. 尽量提取具体的数据、方法和结论
"""
        else:
            # Use default template from configuration
            analysis_template = get_analysis_template()

            # Prepare multi-modal sections if template supports them
            multimodal_section = ""
            figure_analysis_section = "### 🖼️ 图片/图表分析\n\n本文档无图片。\n\n"
            table_analysis_section = "### 📋 表格数据分析\n\n本文档无表格。\n\n"

            # Check if template expects multi-modal sections
            if (
                "{multimodal_section}" in analysis_template
                or "{figure_analysis_section}" in analysis_template
            ):
                # Extract tables from images (tables are embedded in images list)
                tables = [img for img in (images or []) if img.get("type") == "table"]
                figures = [img for img in (images or []) if img.get("type") != "table"]

                # Format multi-modal content section
                multimodal_section = format_multimodal_section(figures, tables)

                # Format figure analysis placeholder
                if figures:
                    figure_analysis_section = (
                        "### 🖼️ 图片/图表分析\n\n"
                        f"本文档包含 {len(figures)} 个图片。"
                        f"请分析每个图片的内容、作用和关键信息。\n\n"
                    )

                # Format table analysis placeholder
                if tables:
                    table_analysis_section = (
                        "### 📋 表格数据分析\n\n"
                        f"本文档包含 {len(tables)} 个表格。"
                        f"请分析每个表格的数据、趋势和关键结论。\n\n"
                    )

            file_content = analysis_template.format(
                title=title or "未知",
                authors=authors or "未知",
                journal=journal or "未知",
                date=date or "未知",
                doi=doi or "未知",
                fulltext=fulltext[:50000],
                annotations_section=annotations_section,
                images_section=images_section,
                multimodal_section=multimodal_section,
                figure_analysis_section=figure_analysis_section,
                table_analysis_section=table_analysis_section,
            )

        # Write to temporary file and run CLI
        return await self._run_cli_with_file(file_content)

    async def _run_cli_with_file(self, file_content: str) -> str:
        """
        Write content to a temporary file and run CLI to analyze it.

        Args:
            file_content: The full prompt content to write to file

        Returns:
            CLI output text

        Raises:
            FileNotFoundError: If CLI command is not found
            RuntimeError: If CLI execution fails
            TimeoutError: If CLI execution exceeds timeout
        """
        # Verify CLI exists before creating temp file
        if not shutil.which(self.cli_command):
            raise FileNotFoundError(
                f"CLI command '{self.cli_command}' not found in PATH. "
                f"Please install Claude Code CLI: npm install -g @anthropic-ai/claude-code"
            )

        # Write content to temporary file
        temp_dir = Path(tempfile.gettempdir()) / "zotero-mcp-cli"
        temp_dir.mkdir(parents=True, exist_ok=True)

        temp_file = temp_dir / f"analysis_{os.getpid()}_{id(file_content)}.md"
        try:
            temp_file.write_text(file_content, encoding="utf-8")
            logger.debug(
                f"Wrote prompt to temp file: {temp_file} ({len(file_content)} chars)"
            )

            # Build CLI command
            prompt = (
                f"请阅读文件 {temp_file} 中的内容，"
                f"按照其中的分析模板对论文进行详细分析。"
                f"直接输出 Markdown 格式的分析结果，不要输出其他内容。"
            )

            cmd = [self.cli_command, "-p", prompt, "--allowedTools", "Read"]

            # Add model flag if specified
            if self.model:
                cmd.extend(["--model", self.model])

            # Add output format and turn limit
            cmd.extend(["--output-format", "text", "--max-turns", "3"])

            logger.info(f"Running CLI: {' '.join(cmd[:6])}...")

            # Execute subprocess
            result = await self._execute_subprocess(cmd)
            return result

        finally:
            # Clean up temp file
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    logger.debug(f"Cleaned up temp file: {temp_file}")
            except OSError as e:
                logger.warning(f"Failed to clean up temp file {temp_file}: {e}")

    async def _execute_subprocess(self, cmd: list[str]) -> str:
        """
        Execute CLI subprocess with streaming output and timeout.

        Args:
            cmd: Command and arguments to execute

        Returns:
            Complete CLI output

        Raises:
            RuntimeError: If CLI returns non-zero exit code
            TimeoutError: If execution exceeds timeout
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Read stdout line by line for streaming output
            output_lines: list[str] = []

            async def read_stream():
                assert process.stdout is not None
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace")
                    # Stream to terminal in real-time
                    print(decoded, end="", flush=True)
                    output_lines.append(decoded)

            try:
                await asyncio.wait_for(read_stream(), timeout=self.timeout)
                # Wait for process to finish
                await asyncio.wait_for(process.wait(), timeout=30)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                partial = "".join(output_lines)
                if partial.strip():
                    logger.warning(
                        f"CLI timed out after {self.timeout}s, returning partial output"
                    )
                    return partial.strip()
                raise TimeoutError(
                    f"CLI command timed out after {self.timeout} seconds with no output"
                ) from None

            # Collect stderr
            stderr_data = b""
            if process.stderr:
                stderr_data = await process.stderr.read()

            full_output = "".join(output_lines).strip()

            if process.returncode != 0:
                stderr_text = stderr_data.decode("utf-8", errors="replace").strip()
                error_msg = f"CLI exited with code {process.returncode}"
                if stderr_text:
                    error_msg += f": {stderr_text}"
                if full_output:
                    # If there's output despite error code, return it with warning
                    logger.warning(f"{error_msg}, but output was produced")
                    return full_output
                raise RuntimeError(error_msg)

            if not full_output:
                raise RuntimeError(
                    "CLI returned empty output. "
                    "This may indicate the prompt file was too large or "
                    "the CLI encountered an internal error."
                )

            logger.info(f"CLI analysis complete: {len(full_output)} chars output")
            return full_output

        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"CLI command '{self.cli_command}' not found. "
                f"Please install Claude Code CLI."
            ) from e


# -------------------- Helper Functions --------------------


def is_cli_llm_available() -> bool:
    """Check if CLI LLM command is available in PATH."""
    return shutil.which(CLI_LLM_COMMAND) is not None
