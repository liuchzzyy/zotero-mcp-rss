"""Tests for refactored CLI command tree."""

import argparse
import asyncio
import json
import subprocess
import sys

import pytest

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


def test_workflow_item_analysis_help_hides_multimodal_flag():
    result = subprocess.run(
        [sys.executable, "-m", "zotero_mcp", "workflow", "item-analysis", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--multimodal" not in result.stdout
    assert "--no-multimodal" not in result.stdout
    assert "--target-collection" in result.stdout
    assert "--template" in result.stdout


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
        "purge",
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
        "relate",
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
        ["tags", "delete", "--item-key", "ABC123", "--all"],
        ["tags", "purge", "--tags", "AI分析"],
        ["tags", "rename", "--old-name", "old", "--new-name", "new"],
        ["collections", "delete-empty"],
        ["notes", "relate", "--note-key", "ABC12345", "--collection", "all"],
    ]

    for argv in scenarios:
        args = parser.parse_args(argv)
        assert args.dry_run is False, f"Expected dry_run=False for: {' '.join(argv)}"


def test_item_analysis_template_accepts_auto_alias():
    parser = build_parser()
    args = parser.parse_args(
        [
            "workflow",
            "item-analysis",
            "--target-collection",
            "01_SHORTTERMS",
            "--template",
            "auto",
        ]
    )
    assert args.template == "auto"


def test_item_analysis_template_accepts_book_alias():
    parser = build_parser()
    args = parser.parse_args(
        [
            "workflow",
            "item-analysis",
            "--target-collection",
            "01_SHORTTERMS",
            "--template",
            "book",
        ]
    )
    assert args.template == "book"


def test_item_analysis_template_defaults_to_auto():
    parser = build_parser()
    args = parser.parse_args(
        [
            "workflow",
            "item-analysis",
            "--target-collection",
            "01_SHORTTERMS",
        ]
    )
    assert args.template == "auto"


def test_tags_delete_accepts_all_mode():
    parser = build_parser()
    args = parser.parse_args(["tags", "delete", "--item-key", "ABC123", "--all"])
    assert args.subcommand == "delete"
    assert args.item_key == "ABC123"
    assert args.all is True


def test_tags_delete_accepts_specific_tags():
    parser = build_parser()
    args = parser.parse_args(
        ["tags", "delete", "--item-key", "ABC123", "--tags", "t1", "t2"]
    )
    assert args.subcommand == "delete"
    assert args.all is False
    assert args.tags == ["t1", "t2"]


def test_tags_purge_supports_collection_name():
    parser = build_parser()
    args = parser.parse_args(
        ["tags", "purge", "--tags", "AI分析", "--collection", "01_SHORTTERMS"]
    )
    assert args.subcommand == "purge"
    assert args.collection == "01_SHORTTERMS"


def test_notes_relate_accepts_collection_name_scope():
    parser = build_parser()
    args = parser.parse_args(
        ["notes", "relate", "--note-key", "ABC12345", "--collection", "My Collection"]
    )
    assert args.subcommand == "relate"
    assert args.collection == "My Collection"


def test_notes_search_accepts_collection_name_scope():
    parser = build_parser()
    args = parser.parse_args(
        ["notes", "search", "--query", "matched", "--collection", "My Collection"]
    )
    assert args.subcommand == "search"
    assert args.collection == "My Collection"


def test_item_analysis_rejects_unimplemented_llm_provider_openai():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "workflow",
                "item-analysis",
                "--target-collection",
                "01_SHORTTERMS",
                "--llm-provider",
                "openai",
            ]
        )


def test_item_analysis_accepts_auto_llm_provider():
    parser = build_parser()
    args = parser.parse_args(
        [
            "workflow",
            "item-analysis",
            "--target-collection",
            "01_SHORTTERMS",
            "--llm-provider",
            "auto",
        ]
    )
    assert args.llm_provider == "auto"


def test_workflow_treated_limit_rejects_zero():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "workflow",
                "deduplicate",
                "--treated-limit",
                "0",
            ]
        )


def test_all_flag_is_exposed_for_treated_limit_commands():
    parser = build_parser()
    workflow_item_args = parser.parse_args(
        ["workflow", "item-analysis", "--target-collection", "DONE", "--all"]
    )
    workflow_meta_args = parser.parse_args(["workflow", "metadata-update", "--all"])
    workflow_dedup_args = parser.parse_args(["workflow", "deduplicate", "--all"])
    semantic_args = parser.parse_args(["semantic", "db-update", "--all"])

    assert workflow_item_args.all is True
    assert workflow_meta_args.all is True
    assert workflow_dedup_args.all is True
    assert semantic_args.all is True


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


def test_semantic_db_update_defaults_to_local_mode():
    parser = build_parser()
    args = parser.parse_args(["semantic", "db-update"])
    assert args.local is True


def test_semantic_db_update_supports_no_local():
    parser = build_parser()
    args = parser.parse_args(["semantic", "db-update", "--no-local"])
    assert args.local is False


def test_semantic_db_update_returns_nonzero_on_error(monkeypatch):
    from zotero_mcp.cli_app.commands import semantic

    class _FakeSearch:
        def update_database(self, **_kwargs):
            return {"error": "boom"}

    monkeypatch.setattr(semantic, "load_config", lambda: None)
    monkeypatch.setattr(semantic, "emit", lambda *_args, **_kwargs: None)

    # Patch module-level import path used inside run()
    import zotero_mcp.services.zotero.semantic_search as semantic_search_module

    monkeypatch.setattr(
        semantic_search_module,
        "create_semantic_search",
        lambda *_args, **_kwargs: _FakeSearch(),
    )

    args = argparse.Namespace(
        subcommand="db-update",
        local=True,
        config_path=None,
        db_path=None,
        force_rebuild=False,
        scan_limit=10,
        treated_limit=5,
        all=False,
        no_fulltext=False,
        output="json",
    )
    code = semantic.run(args)
    assert code == 1


def test_workflow_metadata_update_rejects_item_key_with_all():
    from zotero_mcp.cli_app.commands import workflow

    args = argparse.Namespace(
        item_key="ABC123",
        collection=None,
        scan_limit=50,
        treated_limit=20,
        all=True,
        dry_run=False,
        include_unfiled=True,
    )
    result = asyncio.run(workflow._run_metadata_update(args))

    assert result["success"] is False
    assert result["error"] == "--item-key cannot be combined with --all"


def test_workflow_metadata_update_rejects_empty_collection():
    from zotero_mcp.cli_app.commands import workflow

    args = argparse.Namespace(
        item_key=None,
        collection="   ",
        scan_limit=50,
        treated_limit=20,
        all=True,
        dry_run=False,
        include_unfiled=True,
    )
    result = asyncio.run(workflow._run_metadata_update(args))

    assert result["success"] is False
    assert result["error"] == "--collection cannot be empty"


def test_workflow_deduplicate_rejects_empty_collection():
    from zotero_mcp.cli_app.commands import workflow

    args = argparse.Namespace(
        collection=" ",
        scan_limit=50,
        treated_limit=20,
        all=True,
        dry_run=True,
    )
    result = asyncio.run(workflow._run_deduplicate(args))

    assert result["success"] is False
    assert result["error"] == "--collection cannot be empty"


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
