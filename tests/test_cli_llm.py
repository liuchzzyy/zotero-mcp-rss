"""Tests for CLI LLM client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zotero_mcp.clients.cli_llm import CLILLMClient, is_cli_llm_available


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

    @patch("zotero_mcp.clients.cli_llm.CLI_LLM_COMMAND", "my-cli")
    @patch("zotero_mcp.clients.cli_llm.CLI_LLM_TIMEOUT", 120)
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

    @patch("zotero_mcp.clients.cli_llm.shutil.which", return_value="/usr/bin/claude")
    async def test_analyze_paper_builds_prompt(self, mock_which, client):
        """Test that analyze_paper writes correct content to temp file."""
        written_content = None

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

    @patch("zotero_mcp.clients.cli_llm.shutil.which", return_value="/usr/bin/claude")
    async def test_analyze_with_custom_template(self, mock_which, client):
        """Test custom template is included in prompt."""
        written_content = None

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

    @patch("zotero_mcp.clients.cli_llm.shutil.which", return_value="/usr/bin/claude")
    async def test_analyze_with_annotations(self, mock_which, client):
        """Test annotations are included in prompt."""
        written_content = None

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

    @patch("zotero_mcp.clients.cli_llm.shutil.which", return_value=None)
    async def test_cli_not_found(self, mock_which, client):
        """Test error when CLI command is not found."""
        with pytest.raises(FileNotFoundError, match="not found in PATH"):
            await client._run_cli_with_file("test content")

    @patch("zotero_mcp.clients.cli_llm.shutil.which", return_value="/usr/bin/claude")
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

    @patch("zotero_mcp.clients.cli_llm.shutil.which", return_value="/usr/bin/claude")
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

    @patch("zotero_mcp.clients.cli_llm.shutil.which", return_value="/usr/bin/claude")
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

    @patch("zotero_mcp.clients.cli_llm.shutil.which", return_value="/usr/bin/claude")
    def test_is_cli_available_true(self, mock_which):
        assert is_cli_llm_available() is True

    @patch("zotero_mcp.clients.cli_llm.shutil.which", return_value=None)
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
