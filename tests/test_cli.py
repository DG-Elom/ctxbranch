"""Tests for the ctxbranch CLI (fork, tree first)."""

from __future__ import annotations

import re
from pathlib import Path

from click.testing import CliRunner

from ctxbranch.cli import main
from ctxbranch.core.state_manager import BranchStatus, Intent, StateManager


class TestForkCommand:
    def test_fork_creates_branch_in_state(self, project_root: Path):
        # Seed : an existing main branch
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "sess-main-0001", None, None, None)

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--project-root",
                str(project_root),
                "fork",
                "digression-foo",
                "digression",
                "check something",
            ],
        )
        assert result.exit_code == 0, result.output

        state = StateManager(project_root).load()
        assert "digression-foo" in state.branches
        b = state.branches["digression-foo"]
        assert b.parent == "main"
        assert b.intent == Intent.DIGRESSION
        assert b.description == "check something"
        assert b.status == BranchStatus.ACTIVE
        assert state.current_branch == "digression-foo"

    def test_fork_emits_resume_command(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "sess-main-0001", None, None, None)

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--project-root",
                str(project_root),
                "fork",
                "h-1",
                "hypothesis",
                "try JWT",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "claude --resume sess-main-0001" in result.output
        assert "--fork-session" in result.output
        assert "--session-id" in result.output

    def test_fork_without_prior_main_fails(self, project_root: Path):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--project-root",
                str(project_root),
                "fork",
                "x",
                "digression",
                "hi",
            ],
        )
        assert result.exit_code != 0
        assert "no branches yet" in result.output.lower() or "main" in result.output.lower()

    def test_fork_rejects_invalid_intent(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "sess-main", None, None, None)

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--project-root",
                str(project_root),
                "fork",
                "x",
                "not-a-real-intent",
                "desc",
            ],
        )
        assert result.exit_code != 0

    def test_fork_explicit_parent_overrides_current(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "sess-main", None, None, None)
        sm.add_branch("other", "sess-other", "main", Intent.DIGRESSION, "x")
        sm.switch_branch("other")  # current is "other"

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--project-root",
                str(project_root),
                "fork",
                "child-of-main",
                "checkpoint",
                "pre-compact",
                "--parent",
                "main",
            ],
        )
        assert result.exit_code == 0, result.output
        state = StateManager(project_root).load()
        assert state.branches["child-of-main"].parent == "main"


class TestTreeCommand:
    def test_tree_on_empty_state_is_informational(self, project_root: Path):
        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "tree"])
        assert result.exit_code == 0
        assert "no branches" in result.output.lower() or "empty" in result.output.lower()

    def test_tree_renders_branches_with_current_marker(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "s-main", None, None, None)
        sm.add_branch("d-1", "s-d-1", "main", Intent.DIGRESSION, "x")
        sm.add_branch("h-1", "s-h-1", "main", Intent.HYPOTHESIS, "y")
        sm.merge_branch("d-1", merge_id="m1")
        sm.switch_branch("h-1")

        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "tree"])
        assert result.exit_code == 0
        out = result.output

        assert "main" in out
        assert "d-1" in out
        assert "h-1" in out
        # Current branch highlighted somehow (marker, arrow, star, or highlight)
        assert re.search(r"(current|\*|>|◀|●).*h-1|h-1.*(current|\*|>|◀|●)", out)
