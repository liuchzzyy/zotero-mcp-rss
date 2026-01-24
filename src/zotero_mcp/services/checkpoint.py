"""
Checkpoint manager for workflow state persistence.

Enables resuming interrupted batch analysis workflows.
"""

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)


# -------------------- Data Models --------------------


@dataclass
class WorkflowState:
    """State of a batch analysis workflow."""

    workflow_id: str
    source_type: Literal["collection", "recent"]
    source_identifier: str  # Collection key or "recent"
    total_items: int
    processed_keys: list[str] = field(default_factory=list)
    failed_keys: dict[str, str] = field(default_factory=dict)  # {key: error}
    skipped_keys: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: Literal["running", "paused", "completed", "failed"] = "running"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowState":
        """Create from dictionary."""
        return cls(**data)

    def mark_processed(self, item_key: str) -> None:
        """Mark an item as successfully processed."""
        if item_key not in self.processed_keys:
            self.processed_keys.append(item_key)
        self.updated_at = datetime.now().isoformat()

    def mark_failed(self, item_key: str, error: str) -> None:
        """Mark an item as failed."""
        self.failed_keys[item_key] = error
        self.updated_at = datetime.now().isoformat()

    def mark_skipped(self, item_key: str) -> None:
        """Mark an item as skipped."""
        if item_key not in self.skipped_keys:
            self.skipped_keys.append(item_key)
        self.updated_at = datetime.now().isoformat()

    def get_progress(self) -> tuple[int, int]:
        """Get progress as (completed, total)."""
        completed = (
            len(self.processed_keys) + len(self.failed_keys) + len(self.skipped_keys)
        )
        return completed, self.total_items

    def get_remaining_items(self, all_item_keys: list[str]) -> list[str]:
        """Get list of items not yet processed."""
        processed_set = set(self.processed_keys)
        failed_set = set(self.failed_keys.keys())
        skipped_set = set(self.skipped_keys)
        all_processed = processed_set | failed_set | skipped_set

        return [key for key in all_item_keys if key not in all_processed]


# -------------------- Checkpoint Manager --------------------


class CheckpointManager:
    """
    Manages workflow state persistence.

    Saves workflow state to disk to enable resuming interrupted workflows.
    """

    def __init__(self, state_dir: Path | str | None = None):
        """
        Initialize checkpoint manager.

        Args:
            state_dir: Directory for storing workflow state files.
                      Defaults to ~/.config/zotero-mcp/workflows/
        """
        if state_dir is None:
            config_dir = Path.home() / ".config" / "zotero-mcp"
            self.state_dir = config_dir / "workflows"
        else:
            self.state_dir = Path(state_dir)

        # Create directory if it doesn't exist
        self.state_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Checkpoint manager initialized: {self.state_dir}")

    def _get_state_file(self, workflow_id: str) -> Path:
        """Get path to state file for a workflow."""
        return self.state_dir / f"{workflow_id}.json"

    def create_workflow(
        self,
        source_type: Literal["collection", "recent"],
        source_identifier: str,
        total_items: int,
        metadata: dict | None = None,
    ) -> WorkflowState:
        """
        Create a new workflow state.

        Args:
            source_type: Type of source (collection or recent)
            source_identifier: Collection key or "recent"
            total_items: Total number of items to process
            metadata: Optional metadata

        Returns:
            New WorkflowState
        """
        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"

        state = WorkflowState(
            workflow_id=workflow_id,
            source_type=source_type,
            source_identifier=source_identifier,
            total_items=total_items,
            metadata=metadata or {},
        )

        self.save_state(state)

        logger.info(
            f"Created workflow {workflow_id}: "
            f"{source_type}={source_identifier}, items={total_items}"
        )

        return state

    def save_state(self, state: WorkflowState) -> None:
        """
        Save workflow state to disk.

        Args:
            state: Workflow state to save
        """
        state.updated_at = datetime.now().isoformat()
        state_file = self._get_state_file(state.workflow_id)

        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)

        logger.debug(f"Saved workflow state: {state.workflow_id}")

    def load_state(self, workflow_id: str) -> WorkflowState | None:
        """
        Load workflow state from disk.

        Args:
            workflow_id: Workflow ID

        Returns:
            WorkflowState if found, None otherwise
        """
        state_file = self._get_state_file(workflow_id)

        if not state_file.exists():
            logger.warning(f"Workflow state not found: {workflow_id}")
            return None

        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            state = WorkflowState.from_dict(data)
            logger.info(f"Loaded workflow state: {workflow_id}")
            return state

        except Exception as e:
            logger.error(f"Failed to load workflow state {workflow_id}: {e}")
            return None

    def list_workflows(
        self,
        status_filter: Literal[
            "running", "paused", "completed", "failed", "all"
        ] = "all",
    ) -> list[WorkflowState]:
        """
        List all workflows.

        Args:
            status_filter: Filter by status

        Returns:
            List of workflow states
        """
        workflows = []

        for state_file in self.state_dir.glob("wf_*.json"):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                state = WorkflowState.from_dict(data)

                # Apply filter
                if status_filter == "all" or state.status == status_filter:
                    workflows.append(state)

            except Exception as e:
                logger.error(f"Failed to load workflow from {state_file}: {e}")

        # Sort by updated_at (most recent first)
        workflows.sort(key=lambda w: w.updated_at, reverse=True)

        return workflows

    def delete_workflow(self, workflow_id: str) -> bool:
        """
        Delete a workflow state.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if deleted, False if not found
        """
        state_file = self._get_state_file(workflow_id)

        if state_file.exists():
            state_file.unlink()
            logger.info(f"Deleted workflow: {workflow_id}")
            return True
        else:
            logger.warning(f"Workflow not found for deletion: {workflow_id}")
            return False

    def cleanup_old_workflows(self, days: int = 30) -> int:
        """
        Clean up old completed workflows.

        Args:
            days: Delete workflows older than this many days

        Returns:
            Number of workflows deleted
        """
        cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
        deleted_count = 0

        for state_file in self.state_dir.glob("wf_*.json"):
            try:
                # Check file modification time
                if state_file.stat().st_mtime < cutoff:
                    # Load to check status
                    with open(state_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    state = WorkflowState.from_dict(data)

                    # Only delete completed or failed workflows
                    if state.status in ("completed", "failed"):
                        state_file.unlink()
                        deleted_count += 1
                        logger.debug(f"Cleaned up old workflow: {state.workflow_id}")

            except Exception as e:
                logger.error(f"Error cleaning up {state_file}: {e}")

        logger.info(f"Cleaned up {deleted_count} old workflows")
        return deleted_count


# -------------------- Singleton Instance --------------------


_checkpoint_manager: CheckpointManager | None = None


def get_checkpoint_manager() -> CheckpointManager:
    """Get singleton checkpoint manager instance."""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
    return _checkpoint_manager
