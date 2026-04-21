"""Tests for ctxbranch.core.state_manager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctxbranch.core.state_manager import (
    Branch,
    BranchStatus,
    Intent,
    State,
    StateManager,
)


class TestStateManagerLoad:
    def test_load_missing_file_returns_empty_state_with_main(self, project_root: Path):
        sm = StateManager(project_root)
        state = sm.load()
        assert state.version == 1
        assert state.current_branch == "main"
        assert list(state.branches) == []

    def test_load_existing_state_roundtrip(self, project_root: Path):
        sm = StateManager(project_root)
        state = sm.load()
        sm.add_branch(
            name="main",
            session_id="s-main",
            parent=None,
            intent=None,
            description=None,
        )
        sm.save(state)

        # Reload with a fresh manager
        sm2 = StateManager(project_root)
        state2 = sm2.load()
        assert "main" in state2.branches
        assert state2.branches["main"].session_id == "s-main"

    def test_load_corrupt_file_backs_up_and_returns_empty(
        self, project_root: Path, ctxbranch_dir: Path
    ):
        ctxbranch_dir.mkdir()
        (ctxbranch_dir / "state.json").write_text("{ not json")

        sm = StateManager(project_root)
        state = sm.load()

        assert state.current_branch == "main"
        assert list(state.branches) == []
        # Backup file was created
        backups = list(ctxbranch_dir.glob("state.json.bak-*"))
        assert len(backups) == 1


class TestStateManagerAddBranch:
    def test_add_branch_creates_entry_with_timestamp(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        branch = sm.add_branch(
            name="main",
            session_id="s-1",
            parent=None,
            intent=None,
            description=None,
        )
        assert branch.name == "main"
        assert branch.session_id == "s-1"
        assert branch.parent is None
        assert branch.status == BranchStatus.ACTIVE
        assert branch.created_at is not None

    def test_add_child_branch_updates_parent_children(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "s-main", None, None, None)
        sm.add_branch(
            "digression-x",
            "s-x",
            parent="main",
            intent=Intent.DIGRESSION,
            description="check jwt",
        )
        state = sm.load()
        assert "digression-x" in state.branches["main"].children
        assert state.branches["digression-x"].parent == "main"
        assert state.branches["digression-x"].intent == Intent.DIGRESSION

    def test_add_duplicate_branch_raises(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "s-main", None, None, None)
        with pytest.raises(ValueError, match="already exists"):
            sm.add_branch("main", "s-other", None, None, None)

    def test_add_child_with_unknown_parent_raises(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        with pytest.raises(ValueError, match="unknown parent"):
            sm.add_branch(
                "child",
                "s-c",
                parent="ghost",
                intent=Intent.DIGRESSION,
                description="",
            )


class TestStateManagerMerge:
    def test_merge_branch_marks_merged_with_id(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "s-main", None, None, None)
        sm.add_branch("d-1", "s-d", "main", Intent.DIGRESSION, "x")

        sm.merge_branch("d-1", merge_id="merge-abc")

        state = sm.load()
        branch = state.branches["d-1"]
        assert branch.status == BranchStatus.MERGED
        assert branch.merge_id == "merge-abc"
        assert branch.merged_at is not None

    def test_merge_already_merged_raises(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "s-main", None, None, None)
        sm.add_branch("d-1", "s-d", "main", Intent.DIGRESSION, "x")
        sm.merge_branch("d-1", merge_id="m1")
        with pytest.raises(ValueError, match="already merged"):
            sm.merge_branch("d-1", merge_id="m2")


class TestStateManagerThrow:
    def test_throw_marks_thrown(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "s-main", None, None, None)
        sm.add_branch("h-1", "s-h", "main", Intent.HYPOTHESIS, "y")

        sm.throw_branch("h-1")

        state = sm.load()
        assert state.branches["h-1"].status == BranchStatus.THROWN


class TestStateManagerSwitchBranch:
    def test_switch_current_branch(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "s-m", None, None, None)
        sm.add_branch("d", "s-d", "main", Intent.DIGRESSION, "x")

        sm.switch_branch("d")
        assert sm.load().current_branch == "d"

    def test_switch_to_unknown_raises(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        with pytest.raises(ValueError, match="unknown branch"):
            sm.switch_branch("ghost")


class TestStateFileLocation:
    def test_state_file_path_is_ctxbranch_subdir(self, project_root: Path, ctxbranch_dir: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "s-m", None, None, None)
        assert (ctxbranch_dir / "state.json").is_file()
        data = json.loads((ctxbranch_dir / "state.json").read_text())
        assert data["version"] == 1
        assert "main" in data["branches"]


class TestStateModel:
    def test_state_version_is_int(self):
        s = State(version=1, current_branch="main", branches={})
        assert s.version == 1

    def test_branch_defaults(self):
        b = Branch(
            name="main",
            session_id="s",
            parent=None,
            intent=None,
            description=None,
        )
        assert b.status == BranchStatus.ACTIVE
        assert b.children == []
        assert b.merged_at is None
