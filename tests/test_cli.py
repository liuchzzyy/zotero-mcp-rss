"""Tests for refactored CLI command tree."""

import json
import subprocess
import sys

from zotero_mcp.cli_app.commands.system import obfuscate_config_for_display


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


def test_workflow_scan_help_shows_multimodal_flag():
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp", "workflow", "scan", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--multimodal" in result.stdout
    assert "--no-multimodal" in result.stdout
    assert "--target-collection" in result.stdout


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
    ]:
        assert subcommand in result.stdout


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
