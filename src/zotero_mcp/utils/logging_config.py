"""
Logging configuration and management for Zotero MCP.

Provides centralized logging configuration with:
- Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- File and console handlers
- Log rotation and archival
- Structured logging for GitHub Actions
- Performance monitoring
- Context-sensitive logging
"""

from datetime import datetime
import logging
import logging.handlers
import os
from pathlib import Path
import sys
from typing import Any

# -------------------- Configuration --------------------


# Log directory
LOG_DIR = Path.home() / ".cache" / "zotero-mcp" / "logs"

# Log retention
LOG_RETENTION_DAYS = 3

# Log format strings
CONSOLE_FORMAT = "%(name)s %(levelname)s: %(message)s"
FILE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
GITHUB_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"

# Date format for logs
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# -------------------- Global State --------------------


_loggers_configured = set()


# -------------------- Utility Functions --------------------


def get_log_level() -> int:
    """
    Get the current log level from environment configuration.

    Checks LOG_LEVEL environment variable first, then DEBUG flag.

    Returns:
        Logging level constant (logging.DEBUG, logging.INFO, etc.)
    """
    level_str = os.getenv("LOG_LEVEL", "").upper()

    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    if level_str in level_map:
        return level_map[level_str]

    # Fall back to DEBUG env var
    if os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
        return logging.DEBUG

    return logging.INFO


def is_github_actions() -> bool:
    """Check if running in GitHub Actions environment."""
    return os.getenv("GITHUB_ACTIONS") == "true"


def get_log_file_path() -> Path:
    """
    Get the path to the current log file.

    Creates log directory if it doesn't exist.

    Returns:
        Path to the log file for today
    """
    log_dir = LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    # Use date-based log files
    today = datetime.now().strftime("%Y-%m-%d")
    return log_dir / f"zotero-mcp-{today}.log"


def cleanup_old_logs() -> None:
    """
    Remove log files older than LOG_RETENTION_DAYS.

    This should be called periodically to prevent log files
    from accumulating and consuming disk space.
    """
    log_dir = LOG_DIR

    if not log_dir.exists():
        return

    try:
        import time

        now = time.time()
        cutoff = now - (LOG_RETENTION_DAYS * 24 * 60 * 60)

        for log_file in log_dir.glob("zotero-mcp-*.log"):
            if log_file.stat().st_mtime < cutoff:
                log_file.unlink()
                logging.getLogger(__name__).info(f"Removed old log file: {log_file}")

    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to cleanup old logs: {e}")


# -------------------- Formatter Classes --------------------


class GitHubActionsFormatter(logging.Formatter):
    """
    Custom formatter for GitHub Actions with workflow metadata.

    Adds task context, timing information, and structured output
    for better GitHub Actions log display.
    """

    def __init__(self) -> None:
        super().__init__(fmt=GITHUB_FORMAT, datefmt=DATE_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with GitHub Actions metadata.

        Adds workflow annotations for errors and warnings.
        """
        formatted = super().format(record)

        # Add GitHub Actions workflow commands for errors and warnings
        if record.levelno >= logging.ERROR:
            formatted = f"::error::{formatted}"
        elif record.levelno >= logging.WARNING:
            formatted = f"::warning::{formatted}"

        return formatted


# -------------------- Setup Functions --------------------


def setup_logging(
    name: str,
    level: int | None = None,
    console: bool = True,
    file: bool = True,
    github_format: bool = False,
) -> logging.Logger:
    """
    Setup logging for a module with consistent formatting.

    Args:
        name: Logger name (usually __name__)
        level: Log level (defaults to get_log_level())
        console: Add console handler
        file: Add file handler
        github_format: Use GitHub Actions formatting

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logging(__name__)
        >>> logger.info("Starting processing")
    """
    # Avoid configuring the same logger twice
    if name in _loggers_configured:
        return logging.getLogger(name)

    logger = logging.getLogger(name)
    logger.setLevel(level or get_log_level())
    logger.handlers.clear()
    logger.propagate = False

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logger.level)

        if github_format and is_github_actions():
            console_handler.setFormatter(GitHubActionsFormatter())
        else:
            console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))

        logger.addHandler(console_handler)

    # File handler with rotation
    if file:
        log_file = get_log_file_path()
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logger.level)
        file_handler.setFormatter(logging.Formatter(FILE_FORMAT, DATE_FORMAT))
        logger.addHandler(file_handler)

    _loggers_configured.add(name)

    return logger


def setup_task_logger(
    task_name: str,
    level: int | None = None,
) -> logging.Logger:
    """
    Setup logging for a background task (RSS, Gmail, Workflow).

    Adds task-specific context and automatic cleanup.

    Args:
        task_name: Name of the task (e.g., "RSS Ingestion", "Global Analysis")
        level: Log level (defaults to get_log_level())

    Returns:
        Configured logger with task context

    Example:
        >>> logger = setup_task_logger("RSS Ingestion")
        >>> logger.info("Starting task")
    """
    logger = setup_logging(f"zotero_mcp.tasks.{task_name}", level=level)

    # Add task context filter
    task_filter = TaskContextFilter(task_name)
    for handler in logger.handlers:
        handler.addFilter(task_filter)

    return logger


# -------------------- Filter Classes --------------------


class TaskContextFilter(logging.Filter):
    """
    Logging filter that adds task context to log records.

    Adds custom attributes to log records for better traceability:
    - task_name: Name of the current task
    - start_time: Task start timestamp
    - items_processed: Number of items processed
    """

    def __init__(self, task_name: str) -> None:
        super().__init__()
        self.task_name = task_name
        self.start_time = datetime.now()
        self.items_processed = 0

    def filter(self, record: logging.LogRecord) -> bool:
        """Add task context to log record."""
        record.task_name = self.task_name
        record.task_elapsed = (datetime.now() - self.start_time).total_seconds()
        record.items_processed = self.items_processed
        return True

    def increment_items(self, count: int = 1) -> None:
        """Increment the processed items counter."""
        self.items_processed += count


# -------------------- Monitoring Functions --------------------


def log_task_start(logger: logging.Logger, task_name: str, **metadata: Any) -> None:
    """
    Log task start with structured metadata.

    Args:
        logger: Logger instance
        task_name: Name of the task
        **metadata: Additional task metadata
    """
    logger.info("=" * 60)
    logger.info(f"Task Started: {task_name}")
    logger.info(f"Start Time: {datetime.now().strftime(DATE_FORMAT)}")

    if metadata:
        logger.info("Task Metadata:")
        for key, value in metadata.items():
            logger.info(f"  {key}: {value}")

    logger.info("=" * 60)


def log_task_end(
    logger: logging.Logger,
    task_name: str,
    items_processed: int = 0,
    errors: list[str] | None = None,
    **metadata: Any,
) -> None:
    """
    Log task completion with summary statistics.

    Args:
        logger: Logger instance
        task_name: Name of the task
        items_processed: Number of items processed
        errors: List of error messages
        **metadata: Additional task metadata
    """
    logger.info("=" * 60)
    logger.info(f"Task Completed: {task_name}")
    logger.info(f"End Time: {datetime.now().strftime(DATE_FORMAT)}")
    logger.info(f"Items Processed: {items_processed}")

    if errors:
        logger.warning(f"Errors Encountered: {len(errors)}")
        for i, error in enumerate(errors[:10], 1):  # Show first 10 errors
            logger.warning(f"  {i}. {error}")
        if len(errors) > 10:
            logger.warning(f"  ... and {len(errors) - 10} more errors")

    if metadata:
        logger.info("Final Metadata:")
        for key, value in metadata.items():
            logger.info(f"  {key}: {value}")

    logger.info("=" * 60)


def log_operation(
    logger: logging.Logger,
    operation: str,
    item_key: str,
    status: str,
    **details: Any,
) -> None:
    """
    Log individual operation with consistent format.

    Args:
        logger: Logger instance
        operation: Operation type (e.g., "analyze", "fetch", "save")
        item_key: Zotero item key
        status: Operation status (success, error, skipped)
        **details: Additional operation details
    """
    msg = f"[{operation.upper()}] {item_key} - {status}"

    if details:
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        msg = f"{msg} ({detail_str})"

    if status == "success":
        logger.info(msg)
    elif status == "error":
        logger.error(msg)
    else:
        logger.debug(msg)


# -------------------- Performance Monitoring --------------------


class PerformanceMonitor:
    """
    Context manager for monitoring operation performance.

    Logs execution time and optional metadata.

    Example:
        >>> with PerformanceMonitor(logger, "API Call"):
        ...     result = api_call()
    """

    def __init__(
        self,
        logger: logging.Logger,
        operation_name: str,
        log_level: int = logging.DEBUG,
        **metadata: Any,
    ) -> None:
        """
        Initialize performance monitor.

        Args:
            logger: Logger instance
            operation_name: Name of the operation being monitored
            log_level: Log level for timing info
            **metadata: Additional metadata to log
        """
        self.logger = logger
        self.operation_name = operation_name
        self.log_level = log_level
        self.metadata = metadata
        self.start_time: datetime | None = None

    def __enter__(self) -> "PerformanceMonitor":
        """Start timing."""
        self.start_time = datetime.now()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Log timing information."""
        if self.start_time is None:
            return

        elapsed = (datetime.now() - self.start_time).total_seconds()

        msg = f"{self.operation_name} completed in {elapsed:.2f}s"

        if self.metadata:
            metadata_str = ", ".join(f"{k}={v}" for k, v in self.metadata.items())
            msg = f"{msg} ({metadata_str})"

        self.logger.log(self.log_level, msg)


# -------------------- Convenience Functions --------------------


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with standard configuration.

    This is a convenience function that should be used in all modules.

    Args:
        name: Logger name (use __name__)

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Message")
    """
    if name not in _loggers_configured:
        return setup_logging(name)
    return logging.getLogger(name)


def enable_debug_logging() -> None:
    """Enable debug logging for all loggers."""
    logging.basicConfig(level=logging.DEBUG, format=CONSOLE_FORMAT)

    # Update all configured loggers
    for logger_name in _loggers_configured:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)


def disable_logging() -> None:
    """Disable all logging output."""
    logging.disable(logging.CRITICAL)


# -------------------- Initialization --------------------


def initialize_logging() -> None:
    """
    Initialize logging system for the application.

    Sets up root logger and performs initial cleanup.
    Should be called once at application startup.
    """
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(get_log_level())

    # Clear existing handlers
    root_logger.handlers.clear()

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(get_log_level())

    if is_github_actions():
        console_handler.setFormatter(GitHubActionsFormatter())
    else:
        console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))

    root_logger.addHandler(console_handler)

    # Cleanup old logs
    cleanup_old_logs()

    # Log initialization
    logger = get_logger(__name__)
    logger.info(f"Logging initialized. Level: {logging.getLevelName(get_log_level())}")
    logger.info(f"Log directory: {LOG_DIR}")
