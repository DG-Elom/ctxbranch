"""State manager — persists the branch tree to <project>/ctxbranch/state.json."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

STATE_FILE = "state.json"
STATE_DIR = "ctxbranch"
DEFAULT_BRANCH_NAME = "main"


class Intent(str, Enum):
    DIGRESSION = "digression"
    HYPOTHESIS = "hypothesis"
    AB = "ab"
    CHECKPOINT = "checkpoint"


class BranchStatus(str, Enum):
    ACTIVE = "active"
    MERGED = "merged"
    THROWN = "thrown"


class Branch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    session_id: str
    parent: str | None
    intent: Intent | None
    description: str | None
    created_at: str = Field(default_factory=lambda: _utc_now_iso())
    status: BranchStatus = BranchStatus.ACTIVE
    children: list[str] = Field(default_factory=list)
    merged_at: str | None = None
    merge_id: str | None = None


class State(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    current_branch: str = DEFAULT_BRANCH_NAME
    branches: dict[str, Branch] = Field(default_factory=dict)


class StateManager:
    """Load, mutate and persist the branch state for a project."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.state_dir = self.project_root / STATE_DIR
        self.state_file = self.state_dir / STATE_FILE
        self._state: State | None = None

    def load(self) -> State:
        """Load state from disk ; return empty state if missing or corrupt."""
        if not self.state_file.is_file():
            self._state = State()
            return self._state

        raw = self.state_file.read_text()
        try:
            data = json.loads(raw)
            self._state = State.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            self._backup_corrupt()
            self._state = State()
        return self._state

    def save(self, state: State | None = None) -> None:
        """Write the in-memory state to disk."""
        if state is not None:
            self._state = state
        if self._state is None:
            raise RuntimeError("No state loaded — call load() first")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(self._state.model_dump_json(indent=2, exclude_none=False))

    def add_branch(
        self,
        name: str,
        session_id: str,
        parent: str | None,
        intent: Intent | None,
        description: str | None,
    ) -> Branch:
        state = self._ensure_loaded()
        if name in state.branches:
            raise ValueError(f"branch {name!r} already exists")
        if parent is not None and parent not in state.branches:
            raise ValueError(f"unknown parent branch {parent!r}")

        branch = Branch(
            name=name,
            session_id=session_id,
            parent=parent,
            intent=intent,
            description=description,
        )
        state.branches[name] = branch
        if parent is not None:
            state.branches[parent].children.append(name)
        self.save()
        return branch

    def merge_branch(self, name: str, merge_id: str) -> Branch:
        state = self._ensure_loaded()
        branch = self._get_branch(state, name)
        if branch.status == BranchStatus.MERGED:
            raise ValueError(f"branch {name!r} already merged")
        branch.status = BranchStatus.MERGED
        branch.merge_id = merge_id
        branch.merged_at = _utc_now_iso()
        self.save()
        return branch

    def throw_branch(self, name: str) -> Branch:
        state = self._ensure_loaded()
        branch = self._get_branch(state, name)
        branch.status = BranchStatus.THROWN
        self.save()
        return branch

    def switch_branch(self, name: str) -> None:
        state = self._ensure_loaded()
        if name not in state.branches:
            raise ValueError(f"unknown branch {name!r}")
        state.current_branch = name
        self.save()

    def _ensure_loaded(self) -> State:
        if self._state is None:
            return self.load()
        return self._state

    def _get_branch(self, state: State, name: str) -> Branch:
        if name not in state.branches:
            raise ValueError(f"unknown branch {name!r}")
        return state.branches[name]

    def _backup_corrupt(self) -> None:
        ts = int(time.time())
        backup = self.state_dir / f"state.json.bak-{ts}"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(self.state_file.read_bytes())


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
