"""Checkpoint data model for batch processing."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CheckpointData(BaseModel):
    """Checkpoint for resume-capable batch operations."""

    task_id: str = Field(..., description="Task ID")
    started_at: datetime = Field(..., description="Start time")
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update time"
    )

    # Progress
    total_items: int = Field(..., description="Total items to process")
    completed_items: int = Field(default=0, description="Completed count")
    failed_items: int = Field(default=0, description="Failed count")
    skipped_items: int = Field(default=0, description="Skipped count")

    # Status
    status: str = Field(
        default="running",
        description="Status: running, paused, completed, failed",
    )

    # Detailed records
    completed: list[str] = Field(default_factory=list, description="Completed item IDs")
    failed: dict[str, str] = Field(
        default_factory=dict, description="Failed item ID -> error"
    )
    skipped: list[str] = Field(default_factory=list, description="Skipped item IDs")

    # Config snapshot
    config: dict[str, Any] = Field(
        default_factory=dict, description="Task config snapshot"
    )

    @property
    def progress_percentage(self) -> float:
        if self.total_items == 0:
            return 0.0
        return (self.completed_items / self.total_items) * 100

    @property
    def is_completed(self) -> bool:
        processed = self.completed_items + self.failed_items + self.skipped_items
        return processed >= self.total_items
