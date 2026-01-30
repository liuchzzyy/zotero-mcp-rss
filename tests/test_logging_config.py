"""Tests for logging configuration module."""

import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from zotero_mcp.utils.logging_config import (
    LOG_DIR,
    LOG_RETENTION_DAYS,
    PerformanceMonitor,
    TaskContextFilter,
    _loggers_configured,
    cleanup_old_logs,
    get_log_level,
    get_logger,
    initialize_logging,
    is_github_actions,
    log_operation,
    log_task_end,
    log_task_start,
    setup_logging,
    setup_task_logger,
)


@pytest.fixture(autouse=True)
def reset_logging_state():
    """Reset logging state before each test."""
    _loggers_configured.clear()
    yield
    _loggers_configured.clear()


def test_get_log_level():
    """Test log level detection from environment."""
    # Default level
    with patch.dict(os.environ, {}, clear=True):
        level = get_log_level()
        assert level == logging.INFO

    # DEBUG env var
    with patch.dict(os.environ, {"DEBUG": "true"}):
        level = get_log_level()
        assert level == logging.DEBUG

    with patch.dict(os.environ, {"DEBUG": "1"}):
        level = get_log_level()
        assert level == logging.DEBUG

    # LOG_LEVEL env var
    with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
        level = get_log_level()
        assert level == logging.DEBUG

    with patch.dict(os.environ, {"LOG_LEVEL": "ERROR"}):
        level = get_log_level()
        assert level == logging.ERROR


def test_is_github_actions():
    """Test GitHub Actions environment detection."""
    # Not in GitHub Actions
    with patch.dict(os.environ, {}, clear=True):
        assert is_github_actions() is False

    # In GitHub Actions
    with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
        assert is_github_actions() is True


def test_setup_logging():
    """Test basic logger setup."""
    logger = setup_logging("test_logger", level=logging.DEBUG)

    assert logger.name == "test_logger"
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) > 0
    assert "test_logger" in _loggers_configured


def test_setup_logging_no_duplicates():
    """Test that duplicate setup calls don't add duplicate handlers."""
    logger1 = setup_logging("test_unique_logger")
    handlers_count_1 = len(logger1.handlers)

    logger2 = setup_logging("test_unique_logger")
    handlers_count_2 = len(logger2.handlers)

    assert logger1 is logger2
    assert handlers_count_1 == handlers_count_2


def test_get_logger():
    """Test get_logger convenience function."""
    logger = get_logger("test_convenience")

    assert logger.name == "test_convenience"
    assert "test_convenience" in _loggers_configured


def test_task_logger_with_filter():
    """Test task logger with context filter."""
    logger = setup_task_logger("TestTask")

    assert logger.name == "zotero_mcp.tasks.TestTask"

    # Check that TaskContextFilter is added
    for handler in logger.handlers:
        for f in handler.filters:
            if isinstance(f, TaskContextFilter):
                assert f.task_name == "TestTask"
                return

    pytest.fail("TaskContextFilter not found in handlers")


def test_log_task_operations():
    """Test task logging functions."""

    # Create a custom handler to capture log records
    class TestHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []

        def emit(self, record):
            self.records.append(record)

    logger = setup_logging("test_task_ops", level=logging.INFO)
    test_handler = TestHandler()
    logger.addHandler(test_handler)

    # Test log_task_start
    log_task_start(logger, "Test Task", items=100)

    assert any(
        "Task Started: Test Task" in record.getMessage()
        for record in test_handler.records
    )
    assert any("Start Time:" in record.getMessage() for record in test_handler.records)

    # Test log_task_end
    test_handler.records.clear()
    log_task_end(
        logger,
        "Test Task",
        items_processed=95,
        errors=["Error 1", "Error 2"],
        skipped=5,
    )

    assert any(
        "Task Completed: Test Task" in record.getMessage()
        for record in test_handler.records
    )
    assert any(
        "Items Processed: 95" in record.getMessage() for record in test_handler.records
    )
    assert any(
        "Errors Encountered: 2" in record.getMessage()
        for record in test_handler.records
    )

    # Test log_operation
    test_handler.records.clear()
    log_operation(logger, "analyze", "ABCD123", "success", duration=1.5)

    assert any("[ANALYZE]" in record.getMessage() for record in test_handler.records)
    assert any("ABCD123" in record.getMessage() for record in test_handler.records)


def test_performance_monitor():
    """Test PerformanceMonitor context manager."""

    # Create a custom handler to capture log records
    class TestHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []

        def emit(self, record):
            self.records.append(record)

    logger = setup_logging("test_perf", level=logging.DEBUG)
    test_handler = TestHandler()
    logger.addHandler(test_handler)

    import time

    with PerformanceMonitor(logger, "Test Operation"):
        time.sleep(0.01)

    assert any("completed in" in record.getMessage() for record in test_handler.records)
    assert any(
        "Test Operation" in record.getMessage() for record in test_handler.records
    )


def test_cleanup_old_logs(tmp_path):
    """Test old log cleanup functionality."""
    # Use temporary directory for testing
    with patch("zotero_mcp.utils.logging_config.LOG_DIR", tmp_path):
        # Create some test log files
        (tmp_path / "zotero-mcp-2024-01-01.log").touch()
        (tmp_path / "zotero-mcp-2024-01-02.log").touch()
        (tmp_path / "zotero-mcp-today.log").touch()

        # Mock time to simulate old files
        import time

        now = time.time()
        old_time = now - (10 * 24 * 60 * 60)  # 10 days ago

        for log_file in tmp_path.glob("zotero-mcp-*.log"):
            if "2024" in log_file.name:
                os.utime(log_file, (old_time, old_time))

        # Run cleanup
        cleanup_old_logs()

        # Check that old files are removed
        assert not (tmp_path / "zotero-mcp-2024-01-01.log").exists()
        assert not (tmp_path / "zotero-mcp-2024-01-02.log").exists()
        assert (tmp_path / "zotero-mcp-today.log").exists()


def test_initialize_logging():
    """Test logging system initialization."""
    initialize_logging()

    # Check that root logger is configured
    root_logger = logging.getLogger()
    assert len(root_logger.handlers) > 0


def test_log_retention_constant():
    """Test that log retention is set to 3 days."""
    assert LOG_RETENTION_DAYS == 3


def test_log_dir_constant():
    """Test that log directory is properly set."""
    assert LOG_DIR == Path.home() / ".cache" / "zotero-mcp" / "logs"
