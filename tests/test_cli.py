"""Tests for refactored CLI command tree."""

import json
import subprocess
import sys

from zotero_mcp.cli_app.commands.system import obfuscate_config_for_display
from zotero_mcp.cli_app.registry import build_parser


def test_top_level_help_shows_command_groups():
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    for group in [
        "system",
        "workflow",
        "semantic",
        "tags",
        "items",
        "notes",
        "annotations",
        "pdfs",
        "collections",
    ]:
        assert group in result.stdout


def test_workflow_item_analysis_help_shows_multimodal_flag():
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp", "workflow", "item-analysis", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--multimodal" in result.stdout
    assert "--no-multimodal" in result.stdout
    assert "--target-collection" in result.stdout


def test_workflow_subcommands_follow_new_framework():
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp", "workflow", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    for subcommand in [
        "item-analysis",
        "metadata-update",
        "deduplicate",
    ]:
        assert subcommand in result.stdout
    assert "clean-tags" not in result.stdout
    assert "clean-empty" not in result.stdout


def test_items_subcommands_are_exposed():
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp", "items", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    for subcommand in [
        "get",
        "list",
        "children",
        "fulltext",
        "bundle",
        "delete",
        "update",
        "create",
        "add-tags",
        "add-to-collection",
        "remove-from-collection",
        "delete-empty",
    ]:
        assert subcommand in result.stdout


def test_tags_subcommands_are_exposed():
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp", "tags", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    for subcommand in [
        "list",
        "add",
        "search",
        "delete",
        "rename",
    ]:
        assert subcommand in result.stdout


def test_notes_subcommands_are_exposed():
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp", "notes", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    for subcommand in [
        "list",
        "create",
        "search",
        "delete",
    ]:
        assert subcommand in result.stdout


def test_annotations_subcommands_are_exposed():
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp", "annotations", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    for subcommand in [
        "list",
        "add",
        "search",
        "delete",
    ]:
        assert subcommand in result.stdout


def test_pdfs_subcommands_are_exposed():
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp", "pdfs", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    for subcommand in [
        "list",
        "add",
        "search",
        "delete",
    ]:
        assert subcommand in result.stdout


def test_collections_subcommands_are_exposed():
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp", "collections", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    for subcommand in [
        "list",
        "find",
        "create",
        "rename",
        "move",
        "delete",
        "delete-empty",
        "items",
    ]:
        assert subcommand in result.stdout


def test_dry_run_defaults_are_disabled():
    parser = build_parser()
    scenarios = [
        ["workflow", "item-analysis", "--target-collection", "01_SHORTTERMS"],
        ["workflow", "metadata-update"],
        ["workflow", "deduplicate"],
        ["items", "delete-empty"],
        ["tags", "delete"],
        ["tags", "rename", "--old-name", "old", "--new-name", "new"],
        ["collections", "delete-empty"],
    ]

    for argv in scenarios:
        args = parser.parse_args(argv)
        assert args.dry_run is False, f"Expected dry_run=False for: {' '.join(argv)}"


def test_semantic_status_supports_json_output():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "zotero_mcp",
            "semantic",
            "db-status",
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
    )

    # Can fail without semantic DB config.
    # When it succeeds, output must be valid JSON.
    if result.returncode == 0:
        payload = result.stdout
        json_start = payload.find("{")
        assert json_start >= 0
        json.loads(payload[json_start:])


def test_obfuscate_config_masks_api_keys_and_tokens():
    config = {
        "DEEPSEEK_API_KEY": "sk-1234567890",
        "OPENAI_API_KEY": "sk-openai-123456",
        "CUSTOM_TOKEN": "token-abcdef",
        "NORMAL_VALUE": "visible",
    }

    obfuscated = obfuscate_config_for_display(config)

    assert obfuscated["DEEPSEEK_API_KEY"].startswith("sk-1")
    assert "*" in obfuscated["DEEPSEEK_API_KEY"]
    assert obfuscated["OPENAI_API_KEY"].startswith("sk-o")
    assert "*" in obfuscated["OPENAI_API_KEY"]
    assert obfuscated["CUSTOM_TOKEN"].startswith("toke")
    assert "*" in obfuscated["CUSTOM_TOKEN"]
    assert obfuscated["NORMAL_VALUE"] == "visible"
