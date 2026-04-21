"""Tests for `ctxbranch merge` — the first end-to-end loop."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from ctxbranch.cli import main
from ctxbranch.core.claude_invoker import HeadlessResult
from ctxbranch.core.state_manager import BranchStatus, Intent, StateManager


def _seed_branch(project_root: Path, intent: Intent = Intent.DIGRESSION) -> None:
    sm = StateManager(project_root)
    sm.load()
    sm.add_branch("main", "sess-main", None, None, None)
    sm.add_branch("d-1", "sess-d-1", "main", intent, "check stuff")
    sm.switch_branch("d-1")


class TestMergeCommand:
    def test_merge_produces_artifact_in_merges_dir(self, project_root: Path, mocker):
        _seed_branch(project_root)
        mocker.patch(
            "ctxbranch.cli.headless_call",
            return_value=HeadlessResult(
                parsed={"summary": "Brief summary of the digression finding."},
                raw_text=None,
            ),
        )

        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "merge", "d-1"])
        assert result.exit_code == 0, result.output

        merges_dir = project_root / "ctxbranch" / "merges"
        artifacts = list(merges_dir.glob("*.json"))
        assert len(artifacts) == 1
        data = json.loads(artifacts[0].read_text())
        assert data["branch"] == "d-1"
        assert data["intent"] == "digression"
        assert data["payload"]["summary"] == "Brief summary of the digression finding."

    def test_merge_updates_state_to_merged(self, project_root: Path, mocker):
        _seed_branch(project_root)
        mocker.patch(
            "ctxbranch.cli.headless_call",
            return_value=HeadlessResult(parsed={"summary": "ok"}, raw_text=None),
        )

        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "merge", "d-1"])
        assert result.exit_code == 0, result.output

        state = StateManager(project_root).load()
        assert state.branches["d-1"].status == BranchStatus.MERGED
        assert state.branches["d-1"].merge_id is not None
        assert state.branches["d-1"].merged_at is not None

    def test_merge_switches_current_branch_to_parent(self, project_root: Path, mocker):
        _seed_branch(project_root)
        mocker.patch(
            "ctxbranch.cli.headless_call",
            return_value=HeadlessResult(parsed={"summary": "ok"}, raw_text=None),
        )
        runner = CliRunner()
        runner.invoke(main, ["--project-root", str(project_root), "merge", "d-1"])
        state = StateManager(project_root).load()
        assert state.current_branch == "main"

    def test_merge_falls_back_to_text_on_schema_failure(self, project_root: Path, mocker):
        _seed_branch(project_root)
        from ctxbranch.core.claude_invoker import ClaudeInvokerError

        # First call (schema mode) fails ; second call (text mode) succeeds.
        mocker.patch(
            "ctxbranch.cli.headless_call",
            side_effect=[
                ClaudeInvokerError("result is not valid JSON (schema mode)"),
                HeadlessResult(parsed=None, raw_text="plain free-form summary"),
            ],
        )

        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "merge", "d-1"])
        assert result.exit_code == 0, result.output
        merges = list((project_root / "ctxbranch" / "merges").glob("*.json"))
        assert len(merges) == 1
        data = json.loads(merges[0].read_text())
        assert data["fallback"] == "text"
        assert "plain free-form summary" in data["raw_text"]

    def test_merge_idempotent_errors_on_already_merged(self, project_root: Path, mocker):
        _seed_branch(project_root)
        mocker.patch(
            "ctxbranch.cli.headless_call",
            return_value=HeadlessResult(parsed={"summary": "ok"}, raw_text=None),
        )
        runner = CliRunner()
        runner.invoke(main, ["--project-root", str(project_root), "merge", "d-1"])

        # Second attempt on the already-merged branch
        result = runner.invoke(main, ["--project-root", str(project_root), "merge", "d-1"])
        assert result.exit_code != 0
        assert "already merged" in result.output.lower()

    def test_merge_uses_current_branch_by_default(self, project_root: Path, mocker):
        _seed_branch(project_root)
        mocker.patch(
            "ctxbranch.cli.headless_call",
            return_value=HeadlessResult(parsed={"summary": "ok"}, raw_text=None),
        )

        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "merge"])
        assert result.exit_code == 0, result.output
        state = StateManager(project_root).load()
        assert state.branches["d-1"].status == BranchStatus.MERGED

    def test_merge_cannot_merge_main_root(self, project_root: Path):
        sm = StateManager(project_root)
        sm.load()
        sm.add_branch("main", "s-m", None, None, None)  # no parent

        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "merge", "main"])
        assert result.exit_code != 0
        assert "root" in result.output.lower() or "parent" in result.output.lower()

    def test_merge_prints_rendered_block(self, project_root: Path, mocker):
        _seed_branch(project_root)
        mocker.patch(
            "ctxbranch.cli.headless_call",
            return_value=HeadlessResult(parsed={"summary": "Summary text here"}, raw_text=None),
        )
        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "merge", "d-1"])
        assert result.exit_code == 0, result.output
        assert "<ctxbranch:merge" in result.output
        assert "Summary text here" in result.output
