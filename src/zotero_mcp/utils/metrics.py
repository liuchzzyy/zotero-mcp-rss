"""
Performance monitoring metrics.
"""

from dataclasses import dataclass
from datetime import datetime
from functools import wraps
import time
from typing import Any


@dataclass
class ToolMetrics:
    """Metrics for a single tool."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration_ms: float = 0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0
    last_called: datetime | None = None


class MetricsCollector:
    """Collect and report tool usage metrics."""

    def __init__(self):
        self._metrics: dict[str, ToolMetrics] = {}

    def record_call(self, tool_name: str, duration_ms: float, success: bool) -> None:
        """Record a tool call."""
        if tool_name not in self._metrics:
            self._metrics[tool_name] = ToolMetrics()

        metrics = self._metrics[tool_name]
        metrics.total_calls += 1

        if success:
            metrics.successful_calls += 1
        else:
            metrics.failed_calls += 1

        metrics.total_duration_ms += duration_ms
        metrics.min_duration_ms = min(metrics.min_duration_ms, duration_ms)
        metrics.max_duration_ms = max(metrics.max_duration_ms, duration_ms)
        metrics.last_called = datetime.now()

    def get_report(self) -> dict[str, Any]:
        """Generate metrics report."""
        report = {}

        for tool_name, metrics in self._metrics.items():
            avg_duration = (
                metrics.total_duration_ms / metrics.total_calls
                if metrics.total_calls > 0
                else 0
            )

            report[tool_name] = {
                "total_calls": metrics.total_calls,
                "successful": metrics.successful_calls,
                "failed": metrics.failed_calls,
                "success_rate": (
                    metrics.successful_calls / metrics.total_calls * 100
                    if metrics.total_calls > 0
                    else 0
                ),
                "avg_duration_ms": round(avg_duration, 2),
                "min_duration_ms": round(metrics.min_duration_ms, 2),
                "max_duration_ms": round(metrics.max_duration_ms, 2),
                "last_called": (
                    metrics.last_called.isoformat() if metrics.last_called else None
                ),
            }

        return report


# Global metrics collector
_metrics_collector = MetricsCollector()


def monitored_tool(func):
    """Decorator to monitor tool performance."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        success = False

        try:
            result = await func(*args, **kwargs)
            # Check for 'success' attribute or dict key
            if hasattr(result, "success"):
                success = result.success
            elif isinstance(result, dict):
                success = result.get("success", True)
            else:
                success = True
            return result
        except Exception:
            success = False
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            _metrics_collector.record_call(func.__name__, duration_ms, success)

    return wrapper


def get_metrics_report() -> dict:
    """Get current metrics report."""
    return _metrics_collector.get_report()
