from unittest.mock import patch

from zotero_mcp.utils.system.updater import _compare_versions, update_zotero_mcp


def test_compare_versions_handles_semver_and_v_prefix():
    assert _compare_versions("2.5.0", "v2.2.0") == 1
    assert _compare_versions("2.2.0", "2.5.0") == -1
    assert _compare_versions("v2.5.0", "2.5.0") == 0


def test_update_check_only_marks_no_update_when_current_is_newer():
    with (
        patch("zotero_mcp.utils.system.updater.get_current_version", return_value="2.5.0"),
        patch("zotero_mcp.utils.system.updater.get_latest_version", return_value="2.2.0"),
    ):
        result = update_zotero_mcp(check_only=True)

    assert result["success"] is True
    assert result["needs_update"] is False
    assert "newer than latest release" in result["message"]


def test_update_check_only_marks_update_when_latest_is_newer():
    with (
        patch("zotero_mcp.utils.system.updater.get_current_version", return_value="2.2.0"),
        patch("zotero_mcp.utils.system.updater.get_latest_version", return_value="2.5.0"),
    ):
        result = update_zotero_mcp(check_only=True)

    assert result["success"] is True
    assert result["needs_update"] is True
    assert "Update available: 2.2.0 → 2.5.0" == result["message"]
