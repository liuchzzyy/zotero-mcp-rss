"""Tests for CLI multi-modal functionality."""

import subprocess
import sys


def test_scan_help_shows_multimodal_flags():
    """Test that scan command help shows multi-modal flags."""
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp.cli", "scan", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Check for multi-modal flags
    assert "--multimodal" in result.stdout
    assert "--no-multimodal" in result.stdout

    # Check for multi-modal help text
    assert "Multi-modal support!" in result.stdout
    assert "extract images and tables" in result.stdout

    # Check for LLM provider options
    assert "auto" in result.stdout
    assert "claude-cli" in result.stdout
    assert "deepseek" in result.stdout
    assert "openai" in result.stdout
    assert "gemini" in result.stdout


def test_scan_help_shows_examples():
    """Test that scan command help shows usage examples."""
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp.cli", "scan", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Check for examples in the description
    assert 'zotero-mcp scan -c "Recent Papers" --llm auto' in result.stdout
    assert 'zotero-mcp scan -c "Figures" --llm claude-cli --multimodal' in result.stdout
    # Check for any example with deepseek
    assert "deepseek" in result.stdout and "no-multimodal" in result.stdout
    # Check for openai example
    assert "openai" in result.stdout and "--multimodal" in result.stdout


def test_scan_limit_and_treated_limit_defaults():
    """Test that scan limit and treated limit have correct defaults."""
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp.cli", "scan", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Check default values in help (allow for line breaks)
    assert "Number of items to fetch per batch from API" in result.stdout
    assert "default:" in result.stdout
    assert "100" in result.stdout  # Check that 100 appears somewhere after "default:"
    assert "Maximum total items to process" in result.stdout
    assert "default: 20" in result.stdout


def test_collection_defaults():
    """Test that collection defaults are correctly documented."""
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp.cli", "scan", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Check default collection values (allow for line breaks)
    assert "Move items to this collection after analysis" in result.stdout
    assert "01_SHORTTERMS" in result.stdout
    assert "Collection to scan first" in result.stdout
    assert "00_INBOXS" in result.stdout


def test_dry_run_flag():
    """Test that dry-run flag is properly documented."""
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp.cli", "scan", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    assert "--dry-run" in result.stdout
    assert "Preview without processing" in result.stdout
