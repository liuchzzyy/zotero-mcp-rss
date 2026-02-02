"""
Tests for LLM client image support (Task 5).

Tests for both DeepSeek (text-only) and Claude CLI (multi-modal) clients
handling image parameters in analyze_paper().
"""

from unittest.mock import patch

from zotero_mcp.clients.llm.base import LLMClient
from zotero_mcp.clients.llm.cli import CLILLMClient


class TestDeepSeekImageSupport:
    """Tests for DeepSeek client image handling (text-only)."""

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"})
    def test_init_deepseek_client(self):
        """Test DeepSeek client initialization."""
        client = LLMClient()
        assert client.provider == "deepseek"

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"})
    @patch("zotero_mcp.clients.llm.base.LLMClient._call_deepseek_api")
    async def test_analyze_paper_without_images(self, mock_api):
        """Test analyze_paper with no images (backward compatibility)."""
        mock_api.return_value = "# Analysis\nNo images test"

        client = LLMClient()
        result = await client.analyze_paper(
            title="Test Paper",
            authors="Author A",
            journal="Nature",
            date="2024-01-01",
            doi="10.1234/test",
            fulltext="This is the full text.",
            images=None,
        )

        assert "No images test" in result
        # Verify images section is not mentioned
        prompt_arg = mock_api.call_args[0][0]
        assert "Images" not in prompt_arg

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"})
    @patch("zotero_mcp.clients.llm.base.LLMClient._call_deepseek_api")
    async def test_analyze_paper_with_images_adds_placeholder(self, mock_api):
        """Test that DeepSeek adds placeholder when images are provided."""
        mock_api.return_value = "# Analysis\nWith images placeholder"

        client = LLMClient()

        images = [
            {
                "page": 1,
                "format": "base64",
                "content": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            },
            {
                "page": 3,
                "format": "base64",
                "content": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            },
        ]

        result = await client.analyze_paper(
            title="Test Paper",
            authors="Author A",
            journal="Nature",
            date="2024-01-01",
            doi="10.1234/test",
            fulltext="This is the full text.",
            images=images,
        )

        assert "With images placeholder" in result

        # Verify placeholder was added to prompt
        prompt_arg = mock_api.call_args[0][0]
        assert "## Images" in prompt_arg
        assert "contains 2 image(s)" in prompt_arg
        assert "cannot analyze images" in prompt_arg
        assert "Claude CLI" in prompt_arg

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"})
    @patch("zotero_mcp.clients.llm.base.LLMClient._call_deepseek_api")
    async def test_analyze_paper_with_empty_images_list(self, mock_api):
        """Test that empty images list is handled gracefully."""
        mock_api.return_value = "# Analysis\nEmpty images"

        client = LLMClient()
        result = await client.analyze_paper(
            title="Test Paper",
            authors="Author A",
            journal="Nature",
            date="2024-01-01",
            doi="10.1234/test",
            fulltext="This is the full text.",
            images=[],
        )

        assert "Empty images" in result
        # Empty list should not add images section
        prompt_arg = mock_api.call_args[0][0]
        # Check that images section is either not present or has 0 images
        if "## Images" in prompt_arg:
            assert "0 image(s)" in prompt_arg

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"})
    @patch("zotero_mcp.clients.llm.base.LLMClient._call_deepseek_api")
    async def test_analyze_paper_with_annotations_and_images(self, mock_api):
        """Test that both annotations and images are included."""
        mock_api.return_value = "# Analysis\nWith both"

        client = LLMClient()

        annotations = [{"type": "highlight", "text": "Important finding", "page": "5"}]
        images = [
            {
                "page": 1,
                "format": "base64",
                "content": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            }
        ]

        result = await client.analyze_paper(
            title="Test Paper",
            authors="Author A",
            journal="Nature",
            date="2024-01-01",
            doi="10.1234/test",
            fulltext="This is the full text.",
            annotations=annotations,
            images=images,
        )

        assert "With both" in result

        # Verify both sections are in prompt
        prompt_arg = mock_api.call_args[0][0]
        assert "## PDF 批注" in prompt_arg
        assert "Important finding" in prompt_arg
        assert "## Images" in prompt_arg


class TestClaudeCLIImageSupport:
    """Tests for Claude CLI client image handling (multi-modal)."""

    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value="/usr/bin/claude")
    async def test_analyze_paper_without_images(self, mock_which):
        """Test analyze_paper with no images (backward compatibility)."""
        client = CLILLMClient()

        written_content = ""

        async def mock_run_cli(content: str) -> str:
            nonlocal written_content
            written_content = content
            return "# Analysis\nNo images test"

        client._run_cli_with_file = mock_run_cli  # type: ignore[assignment]

        result = await client.analyze_paper(
            title="Test Paper",
            authors="Author A",
            journal="Nature",
            date="2024-01-01",
            doi="10.1234/test",
            fulltext="This is the full text.",
            images=None,
        )

        assert "No images test" in result
        # Verify images section is not in prompt
        assert "## Images" not in written_content

    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value="/usr/bin/claude")
    async def test_analyze_paper_with_images_embeds_base64(self, mock_which):
        """Test that Claude CLI embeds base64 images in prompt."""
        client = CLILLMClient()

        written_content = ""

        async def mock_run_cli(content: str) -> str:
            nonlocal written_content
            written_content = content
            return "# Analysis\nWith embedded images"

        client._run_cli_with_file = mock_run_cli  # type: ignore[assignment]

        images = [
            {
                "page": 1,
                "format": "base64",
                "content": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            },
            {
                "page": 3,
                "format": "base64",
                "content": "iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAYAAADkInGQAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            },
        ]

        result = await client.analyze_paper(
            title="Test Paper",
            authors="Author A",
            journal="Nature",
            date="2024-01-01",
            doi="10.1234/test",
            fulltext="This is the full text.",
            images=images,
        )

        assert "With embedded images" in result

        # Verify images are embedded
        assert "## Images" in written_content
        assert "### Image 1 (Page 1)" in written_content
        assert "### Image 2 (Page 3)" in written_content
        # Check base64 data URI format
        assert "data:image/png;base64,iVBORw0KGgo" in written_content
        assert "*Figure 1*" in written_content
        assert "*Figure 2*" in written_content

    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value="/usr/bin/claude")
    async def test_analyze_paper_with_empty_images_list(self, mock_which):
        """Test that empty images list is handled gracefully."""
        client = CLILLMClient()

        written_content = ""

        async def mock_run_cli(content: str) -> str:
            nonlocal written_content
            written_content = content
            return "# Analysis\nEmpty images"

        client._run_cli_with_file = mock_run_cli  # type: ignore[assignment]

        result = await client.analyze_paper(
            title="Test Paper",
            authors="Author A",
            journal="Nature",
            date="2024-01-01",
            doi="10.1234/test",
            fulltext="This is the full text.",
            images=[],
        )

        assert "Empty images" in result
        # Empty list should not add images section
        assert "## Images" not in written_content

    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value="/usr/bin/claude")
    async def test_analyze_paper_with_annotations_and_images(self, mock_which):
        """Test that both annotations and images are included."""
        client = CLILLMClient()

        written_content = ""

        async def mock_run_cli(content: str) -> str:
            nonlocal written_content
            written_content = content
            return "# Analysis\nWith both"

        client._run_cli_with_file = mock_run_cli  # type: ignore[assignment]

        annotations = [{"type": "highlight", "text": "Important finding", "page": "5"}]
        images = [
            {
                "page": 1,
                "format": "base64",
                "content": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            }
        ]

        result = await client.analyze_paper(
            title="Test Paper",
            authors="Author A",
            journal="Nature",
            date="2024-01-01",
            doi="10.1234/test",
            fulltext="This is the full text.",
            annotations=annotations,
            images=images,
        )

        assert "With both" in result

        # Verify both sections are in prompt
        assert "## PDF 批注" in written_content
        assert "Important finding" in written_content
        assert "## Images" in written_content

    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value="/usr/bin/claude")
    async def test_analyze_paper_image_without_page_number(self, mock_which):
        """Test handling images without page numbers."""
        client = CLILLMClient()

        written_content = ""

        async def mock_run_cli(content: str) -> str:
            nonlocal written_content
            written_content = content
            return "# Analysis\nImage without page"

        client._run_cli_with_file = mock_run_cli  # type: ignore[assignment]

        images = [
            {
                "format": "base64",
                "content": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            }
        ]

        result = await client.analyze_paper(
            title="Test Paper",
            authors="Author A",
            journal="Nature",
            date="2024-01-01",
            doi="10.1234/test",
            fulltext="This is the full text.",
            images=images,
        )

        assert "Image without page" in result
        # Should use '?' for missing page
        assert "### Image 1 (Page ?)" in written_content


class TestBackwardCompatibility:
    """Tests for backward compatibility when images parameter is not provided."""

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"})
    @patch("zotero_mcp.clients.llm.base.LLMClient._call_deepseek_api")
    async def test_deepseek_backward_compatible(self, mock_api):
        """Test DeepSeek works without images parameter (old code)."""
        mock_api.return_value = "# Analysis\nBackward compatible"

        client = LLMClient()
        # Call without images parameter (old way)
        result = await client.analyze_paper(
            title="Test Paper",
            authors="Author A",
            journal="Nature",
            date="2024-01-01",
            doi="10.1234/test",
            fulltext="This is the full text.",
        )

        assert "Backward compatible" in result

    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value="/usr/bin/claude")
    async def test_claude_cli_backward_compatible(self, mock_which):
        """Test Claude CLI works without images parameter (old code)."""
        client = CLILLMClient()

        written_content = ""

        async def mock_run_cli(content: str) -> str:
            nonlocal written_content
            written_content = content
            return "# Analysis\nBackward compatible"

        client._run_cli_with_file = mock_run_cli  # type: ignore[assignment]

        # Call without images parameter (old way)
        result = await client.analyze_paper(
            title="Test Paper",
            authors="Author A",
            journal="Nature",
            date="2024-01-01",
            doi="10.1234/test",
            fulltext="This is the full text.",
        )

        assert "Backward compatible" in result
        assert "## Images" not in written_content
