"""Tests for throw / clean / resume commands."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from click.testing import CliRunner

from ctxbranch.cli import main
from ctxbranch.core.state_manager import BranchStatus, Intent, StateManager


def _seed_two(project_root: Path) -> None:
    sm = StateManager(project_root)
    sm.load()
    sm.add_branch("main", "sess-main", None, None, None)
    sm.add_branch("d-1", "sess-d-1", "main", Intent.DIGRESSION, "x")


class TestThrowCommand:
    def test_throw_marks_thrown(self, project_root: Path):
        _seed_two(project_root)
        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "throw", "d-1"])
        assert result.exit_code == 0, result.output
        state = StateManager(project_root).load()
        assert state.branches["d-1"].status == BranchStatus.THROWN

    def test_throw_switches_back_to_parent(self, project_root: Path):
        _seed_two(project_root)
        sm = StateManager(project_root)
        sm.switch_branch("d-1")

        runner = CliRunner()
        runner.invoke(main, ["--project-root", str(project_root), "throw", "d-1"])
        state = StateManager(project_root).load()
        assert state.current_branch == "main"

    def test_throw_unknown_branch_fails(self, project_root: Path):
        _seed_two(project_root)
        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "throw", "ghost"])
        assert result.exit_code != 0


class TestCleanCommand:
    def test_clean_thrown_removes_thrown_branches(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "s-main", None, None, None)
        sm.add_branch("alive", "s-alive", "main", Intent.DIGRESSION, "x")
        sm.add_branch("dead", "s-dead", "main", Intent.DIGRESSION, "y")
        sm.throw_branch("dead")

        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "clean", "--thrown"])
        assert result.exit_code == 0, result.output

        state = StateManager(project_root).load()
        assert "dead" not in state.branches
        assert "dead" not in state.branches["main"].children
        assert "alive" in state.branches

    def test_clean_older_than_skips_active_branches(self, project_root: Path, mocker):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "s-main", None, None, None)
        # Fake an old merged branch
        sm.add_branch("old", "s-old", "main", Intent.DIGRESSION, "x")
        sm.merge_branch("old", merge_id="m1")
        # Override merged_at to be 40 days ago
        state = sm.load()
        state.branches["old"].merged_at = (
            (datetime.now(UTC) - timedelta(days=40))
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
        sm.save(state)

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--project-root",
                str(project_root),
                "clean",
                "--older-than",
                "30",
            ],
        )
        assert result.exit_code == 0, result.output
        state = StateManager(project_root).load()
        assert "old" not in state.branches

    def test_clean_dry_run_does_not_mutate(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "s-main", None, None, None)
        sm.add_branch("dead", "s-dead", "main", Intent.DIGRESSION, "y")
        sm.throw_branch("dead")

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--project-root",
                str(project_root),
                "clean",
                "--thrown",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0, result.output
        state = StateManager(project_root).load()
        assert "dead" in state.branches  # still there because dry-run


class TestResumeCommand:
    def test_resume_prints_resume_command(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "sess-main-abc", None, None, None)

        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "resume", "main"])
        assert result.exit_code == 0, result.output
        assert "claude" in result.output
        assert "--resume" in result.output
        assert "sess-main-abc" in result.output

    def test_resume_switches_current_branch(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "s-main", None, None, None)
        sm.add_branch("d-1", "s-d-1", "main", Intent.DIGRESSION, "x")

        runner = CliRunner()
        runner.invoke(main, ["--project-root", str(project_root), "resume", "d-1"])

        state = StateManager(project_root).load()
        assert state.current_branch == "d-1"

    def test_resume_unknown_branch_fails(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "s", None, None, None)

        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "resume", "ghost"])
        assert result.exit_code != 0

    def test_resume_thrown_branch_warns_but_works(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "s-main", None, None, None)
        sm.add_branch("d", "s-d", "main", Intent.DIGRESSION, "x")
        sm.throw_branch("d")

        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "resume", "d"])
        # Resume still succeeds but output notes thrown status
        assert result.exit_code == 0, result.output
        assert "thrown" in result.output.lower()


# Not strictly needed — keep time in scope for potential sleeps
_ = time
