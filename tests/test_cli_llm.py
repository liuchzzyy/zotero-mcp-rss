"""Tests for CLI LLM client and RSS CLI filtering."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zotero_mcp.clients.llm import CLILLMClient, is_cli_llm_available
from zotero_mcp.models.ingestion import RSSItem
from zotero_mcp.services.common import PaperFilter


class TestCLILLMClientInit:
    """Tests for CLILLMClient initialization."""

    def test_default_init(self):
        client = CLILLMClient()
        assert client.cli_command == "claude"
        assert client.model is None
        assert client.timeout == 300
        assert client.provider == "claude-cli"

    def test_custom_init(self):
        client = CLILLMClient(cli_command="opencode", model="opus", timeout=600)
        assert client.cli_command == "opencode"
        assert client.model == "opus"
        assert client.timeout == 600

    @patch("zotero_mcp.clients.llm.cli.CLI_LLM_COMMAND", "my-cli")
    @patch("zotero_mcp.clients.llm.cli.CLI_LLM_TIMEOUT", 120)
    def test_env_config(self):
        """Test that module-level defaults are used when no args provided."""
        client = CLILLMClient(cli_command="my-cli", timeout=120)
        assert client.cli_command == "my-cli"
        assert client.timeout == 120


class TestCLILLMClientAnalyze:
    """Tests for CLILLMClient.analyze_paper."""

    @pytest.fixture
    def client(self):
        return CLILLMClient(cli_command="claude")

    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value="/usr/bin/claude")
    async def test_analyze_paper_builds_prompt(self, mock_which, client):
        """Test that analyze_paper writes correct content to temp file."""
        written_content = ""

        async def mock_run_cli(content):
            nonlocal written_content
            written_content = content
            return "# Analysis Result\nTest output"

        client._run_cli_with_file = mock_run_cli

        result = await client.analyze_paper(
            title="Test Paper",
            authors="Author A, Author B",
            journal="Nature",
            date="2024-01-01",
            doi="10.1234/test",
            fulltext="This is the full text of the paper.",
        )

        assert result == "# Analysis Result\nTest output"
        assert written_content is not None
        assert "Test Paper" in written_content
        assert "Author A, Author B" in written_content
        assert "Nature" in written_content

    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value="/usr/bin/claude")
    async def test_analyze_with_custom_template(self, mock_which, client):
        """Test custom template is included in prompt."""
        written_content = ""

        async def mock_run_cli(content):
            nonlocal written_content
            written_content = content
            return "Custom analysis output"

        client._run_cli_with_file = mock_run_cli

        await client.analyze_paper(
            title="Test",
            authors=None,
            journal=None,
            date=None,
            doi=None,
            fulltext="Paper text",
            template="## Custom Template\nAnalyze this.",
        )

        assert "Custom Template" in written_content
        assert "Analyze this" in written_content

    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value="/usr/bin/claude")
    async def test_analyze_with_annotations(self, mock_which, client):
        """Test annotations are included in prompt."""
        written_content = ""

        async def mock_run_cli(content):
            nonlocal written_content
            written_content = content
            return "Analysis with annotations"

        client._run_cli_with_file = mock_run_cli

        annotations = [
            {"type": "highlight", "text": "Important finding", "page": "5"},
            {"type": "note", "comment": "Check this", "page": "10"},
        ]

        await client.analyze_paper(
            title="Test",
            authors=None,
            journal=None,
            date=None,
            doi=None,
            fulltext="Paper text",
            annotations=annotations,
        )

        assert "Important finding" in written_content
        assert "Check this" in written_content
        assert "批注 1" in written_content
        assert "批注 2" in written_content


class TestCLILLMClientSubprocess:
    """Tests for CLI subprocess execution."""

    @pytest.fixture
    def client(self):
        return CLILLMClient(cli_command="claude")

    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value=None)
    async def test_cli_not_found(self, mock_which, client):
        """Test error when CLI command is not found."""
        with pytest.raises(FileNotFoundError, match="not found in PATH"):
            await client._run_cli_with_file("test content")

    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value="/usr/bin/claude")
    @patch("asyncio.create_subprocess_exec")
    async def test_successful_execution(self, mock_exec, mock_which, client):
        """Test successful CLI execution."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")

        # Simulate stdout line-by-line reading
        output_lines = [b"# Analysis\n", b"Content here\n", b""]
        line_iter = iter(output_lines)

        async def mock_readline():
            return next(line_iter)

        mock_process.stdout = MagicMock()
        mock_process.stdout.readline = mock_readline
        mock_process.wait = AsyncMock(return_value=0)

        mock_exec.return_value = mock_process

        result = await client._execute_subprocess(["claude", "-p", "test"])
        assert "Analysis" in result
        assert "Content here" in result

    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value="/usr/bin/claude")
    @patch("asyncio.create_subprocess_exec")
    async def test_cli_returns_error_code(self, mock_exec, mock_which, client):
        """Test CLI returning non-zero exit code with no output."""
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"Error occurred")

        # Empty stdout
        async def mock_readline():
            return b""

        mock_process.stdout = MagicMock()
        mock_process.stdout.readline = mock_readline
        mock_process.wait = AsyncMock(return_value=1)

        mock_exec.return_value = mock_process

        with pytest.raises(RuntimeError, match="CLI exited with code 1"):
            await client._execute_subprocess(["claude", "-p", "test"])

    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value="/usr/bin/claude")
    @patch("asyncio.create_subprocess_exec")
    async def test_empty_output(self, mock_exec, mock_which, client):
        """Test CLI returning empty output."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")

        async def mock_readline():
            return b""

        mock_process.stdout = MagicMock()
        mock_process.stdout.readline = mock_readline
        mock_process.wait = AsyncMock(return_value=0)

        mock_exec.return_value = mock_process

        with pytest.raises(RuntimeError, match="empty output"):
            await client._execute_subprocess(["claude", "-p", "test"])


class TestHelpers:
    """Tests for helper functions."""

    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value="/usr/bin/claude")
    def test_is_cli_available_true(self, mock_which):
        assert is_cli_llm_available() is True

    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value=None)
    def test_is_cli_available_false(self, mock_which):
        assert is_cli_llm_available() is False


class TestGetLLMClient:
    """Tests for the updated get_llm_client factory."""

    def test_get_claude_cli_client(self):
        from zotero_mcp.clients.llm import get_llm_client

        client = get_llm_client(provider="claude-cli")
        assert isinstance(client, CLILLMClient)
        assert client.provider == "claude-cli"

    def test_get_claude_cli_client_with_model(self):
        from zotero_mcp.clients.llm import get_llm_client

        client = get_llm_client(provider="claude-cli", model="opus")
        assert isinstance(client, CLILLMClient)
        assert client.model == "opus"

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"})
    def test_get_default_client(self):
        from zotero_mcp.clients.llm import LLMClient, get_llm_client

        client = get_llm_client(provider="auto")
        assert isinstance(client, LLMClient)


# -------------------- RSS CLI Filtering Tests --------------------


def _make_item(title: str, description: str | None = None) -> RSSItem:
    """Helper to create a minimal RSSItem for testing."""
    return RSSItem(
        title=title, link=f"https://example.com/{title}", description=description
    )


class TestPaperFilterCLI:
    """Tests for PaperFilter.filter_with_cli and related methods."""

    @pytest.fixture
    def paper_filter(self):
        return PaperFilter()

    def test_build_papers_text(self, paper_filter):
        """Test that _build_papers_text formats papers correctly."""
        items = [
            _make_item("Paper A", "Abstract A"),
            _make_item("Paper B", None),
            _make_item("Paper C", "Abstract C"),
        ]
        text = paper_filter._build_papers_text(items)
        assert "### [0] Paper A" in text
        assert "Abstract A" in text
        assert "### [1] Paper B" in text
        assert "### [2] Paper C" in text

    def test_build_papers_text_truncates_long_abstract(self, paper_filter):
        """Test that long abstracts are truncated to 500 chars."""
        long_abstract = "x" * 600
        items = [_make_item("Long Paper", long_abstract)]
        text = paper_filter._build_papers_text(items)
        assert "..." in text
        # Should contain truncated version, not full 600 chars
        assert "x" * 501 not in text

    def test_parse_cli_filter_output_valid_json(self, paper_filter):
        """Test parsing valid JSON output."""
        output = '{"relevant": [0, 2, 4]}'
        result = paper_filter._parse_cli_filter_output(output, batch_size=5)
        assert result == {0, 2, 4}

    def test_parse_cli_filter_output_markdown_block(self, paper_filter):
        """Test parsing JSON inside markdown code block."""
        output = 'Some text\n```json\n{"relevant": [1, 3]}\n```\nMore text'
        result = paper_filter._parse_cli_filter_output(output, batch_size=5)
        assert result == {1, 3}

    def test_parse_cli_filter_output_embedded_json(self, paper_filter):
        """Test parsing JSON embedded in other text."""
        output = 'Based on analysis, {"relevant": [0, 5]} are related.'
        result = paper_filter._parse_cli_filter_output(output, batch_size=10)
        assert result == {0, 5}

    def test_parse_cli_filter_output_empty_relevant(self, paper_filter):
        """Test parsing empty relevant list."""
        output = '{"relevant": []}'
        result = paper_filter._parse_cli_filter_output(output, batch_size=5)
        assert result == set()

    def test_parse_cli_filter_output_invalid(self, paper_filter):
        """Test graceful handling of unparseable output."""
        output = "Sorry, I cannot process this request."
        result = paper_filter._parse_cli_filter_output(output, batch_size=5)
        assert result == set()

    def test_validate_indices_filters_out_of_range(self, paper_filter):
        """Test that out-of-range indices are filtered."""
        result = paper_filter._validate_indices([0, 2, 10, -1, 4], batch_size=5)
        assert result == {0, 2, 4}

    def test_validate_indices_handles_non_int(self, paper_filter):
        """Test that non-integer values are handled gracefully."""
        result = paper_filter._validate_indices([0, "abc", 2, None], batch_size=5)
        assert result == {0, 2}

    @patch.dict("os.environ", {"RSS_PROMPT": "I study batteries"})
    async def test_filter_with_cli_empty_items(self, paper_filter):
        """Test filter_with_cli with empty item list."""
        relevant, irrelevant, keywords = await paper_filter.filter_with_cli([])
        assert relevant == []
        assert irrelevant == []
        assert keywords == []

    @patch.dict("os.environ", {"RSS_PROMPT": "I study zinc batteries"})
    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value="/usr/bin/claude")
    @patch("asyncio.create_subprocess_exec")
    async def test_filter_with_cli_basic_flow(
        self, mock_exec, mock_which, paper_filter
    ):
        """Test basic filter_with_cli flow with mocked CLI."""
        items = [
            _make_item("Zinc battery research", "About zinc batteries"),
            _make_item("Machine learning intro", "About ML"),
            _make_item("Zinc anode design", "Novel zinc anode"),
        ]

        # Mock subprocess to return JSON
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")

        output_lines = [b'{"relevant": [0, 2]}\n', b""]
        line_iter = iter(output_lines)

        async def mock_readline():
            return next(line_iter)

        mock_process.stdout = MagicMock()
        mock_process.stdout.readline = mock_readline
        mock_process.wait = AsyncMock(return_value=0)
        mock_exec.return_value = mock_process

        relevant, irrelevant, keywords = await paper_filter.filter_with_cli(items)

        assert len(relevant) == 2
        assert relevant[0].title == "Zinc battery research"
        assert relevant[1].title == "Zinc anode design"
        assert len(irrelevant) == 1
        assert irrelevant[0].title == "Machine learning intro"
        assert keywords == []

    @patch.dict("os.environ", {"RSS_PROMPT": "I study batteries"})
    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value="/usr/bin/claude")
    @patch("asyncio.create_subprocess_exec")
    async def test_filter_with_cli_batching(self, mock_exec, mock_which, paper_filter):
        """Test that items are split into batches when exceeding BATCH_SIZE."""
        # Override batch size for testing
        paper_filter.BATCH_SIZE = 2

        items = [_make_item(f"Paper {i}", f"Abstract {i}") for i in range(5)]

        # We need to return results for 3 batches: [0,1], [2,3], [4]
        call_count = 0
        batch_outputs = [
            b'{"relevant": [0]}\n',  # batch 0: paper 0 relevant
            b'{"relevant": [1]}\n',  # batch 1: paper 3 relevant (index 1 in batch)
            b'{"relevant": [0]}\n',  # batch 2: paper 4 relevant (index 0 in batch)
        ]

        def make_mock_process():
            nonlocal call_count
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")

            output = (
                batch_outputs[call_count]
                if call_count < len(batch_outputs)
                else b'{"relevant": []}\n'
            )
            lines = [output, b""]
            line_iter = iter(lines)

            async def mock_readline():
                return next(line_iter)

            mock_process.stdout = MagicMock()
            mock_process.stdout.readline = mock_readline
            mock_process.wait = AsyncMock(return_value=0)
            call_count += 1
            return mock_process

        mock_exec.side_effect = lambda *args, **kwargs: make_mock_process()

        relevant, irrelevant, _ = await paper_filter.filter_with_cli(items)

        # Papers 0, 3, 4 should be relevant
        assert len(relevant) == 3
        assert relevant[0].title == "Paper 0"
        assert relevant[1].title == "Paper 3"
        assert relevant[2].title == "Paper 4"
        assert len(irrelevant) == 2

    @patch.dict("os.environ", {"RSS_PROMPT": "I study batteries"})
    @patch("zotero_mcp.clients.llm.cli.shutil.which", return_value=None)
    async def test_filter_with_cli_error_handling(self, mock_which, paper_filter):
        """Test that CLI errors are handled gracefully."""
        items = [_make_item("Paper A"), _make_item("Paper B")]

        # CLI not found → should return all as irrelevant
        relevant, irrelevant, _ = await paper_filter.filter_with_cli(items)
        assert len(relevant) == 0
        assert len(irrelevant) == 2
