"""Shared response envelope for long-running service operations."""

from typing import Any


def operation_success(
    operation: str,
    metrics: dict[str, int],
    *,
    message: str | None = None,
    dry_run: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standardized success response."""
    payload: dict[str, Any] = {
        "success": True,
        "operation": operation,
        "status": "dry_run" if dry_run else "completed",
        "message": message,
        "metrics": metrics,
    }
    if extra:
        payload.update(extra)
    return payload


def operation_error(
    operation: str,
    error: str,
    metrics: dict[str, int] | None = None,
    *,
    details: Any = None,
    status: str = "failed",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standardized error response."""
    payload: dict[str, Any] = {
        "success": False,
        "operation": operation,
        "status": status,
        "error": error,
        "metrics": metrics
        or {
            "scanned": 0,
            "candidates": 0,
            "processed": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "removed": 0,
        },
    }
    if details is not None:
        payload["details"] = details
    if extra:
        payload.update(extra)
    return payload
