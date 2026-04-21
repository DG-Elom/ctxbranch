"""Tests for the `ctxbranch pause` command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from ctxbranch.cli import main
from ctxbranch.core.claude_invoker import HeadlessResult
from ctxbranch.core.scheduler import AtNotAvailableError
from ctxbranch.core.state_manager import StateManager


def _seed(project_root: Path) -> None:
    sm = StateManager(project_root)
    sm.load()
    sm.add_branch("main", "sess-main-00", None, None, None)


def _checkpoint_payload() -> dict:
    return {
        "goal": "Ship ctxbranch v0.1",
        "completed": ["scaffold", "core"],
        "in_progress": "pause command",
        "next_steps": ["hypothesis strategy tests"],
    }


class TestPauseCommand:
    def test_pause_produces_checkpoint_artifact(self, project_root: Path, mocker):
        _seed(project_root)
        mocker.patch(
            "ctxbranch.cli.headless_call",
            return_value=HeadlessResult(parsed=_checkpoint_payload(), raw_text=None),
        )
        mocker.patch("ctxbranch.cli.schedule_at", return_value="42")

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--project-root", str(project_root), "pause", "--until", "22:59"],
        )
        assert result.exit_code == 0, result.output

        pauses_dir = project_root / "ctxbranch" / "pauses"
        artifacts = list(pauses_dir.glob("*.json"))
        assert len(artifacts) == 1
        data = json.loads(artifacts[0].read_text())
        assert data["branch"] == "main"
        assert data["payload"]["goal"] == "Ship ctxbranch v0.1"
        assert data["at_job_id"] == "42"
        assert data["when"] == "22:59"

    def test_pause_writes_resume_script(self, project_root: Path, mocker):
        _seed(project_root)
        mocker.patch(
            "ctxbranch.cli.headless_call",
            return_value=HeadlessResult(parsed=_checkpoint_payload(), raw_text=None),
        )
        schedule_mock = mocker.patch("ctxbranch.cli.schedule_at", return_value="42")

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--project-root", str(project_root), "pause", "--until", "22:59"],
        )
        assert result.exit_code == 0, result.output

        # schedule_at should have been called with a script path that exists on disk.
        script_path = schedule_mock.call_args.args[0]
        assert Path(script_path).exists()
        contents = Path(script_path).read_text()
        assert "claude --resume sess-main-00" in contents
        assert "--append-system-prompt" in contents

    def test_pause_increments_resume_count(self, project_root: Path, mocker):
        _seed(project_root)
        mocker.patch(
            "ctxbranch.cli.headless_call",
            return_value=HeadlessResult(parsed=_checkpoint_payload(), raw_text=None),
        )
        mocker.patch("ctxbranch.cli.schedule_at", return_value="42")

        runner = CliRunner()
        runner.invoke(
            main,
            ["--project-root", str(project_root), "pause", "--until", "22:59"],
        )

        state = StateManager(project_root).load()
        assert state.branches["main"].resume_count == 1
        assert state.branches["main"].last_pause_id is not None

    def test_pause_aborts_if_at_missing(self, project_root: Path, mocker):
        _seed(project_root)
        mocker.patch(
            "ctxbranch.cli.headless_call",
            return_value=HeadlessResult(parsed=_checkpoint_payload(), raw_text=None),
        )
        mocker.patch(
            "ctxbranch.cli.schedule_at",
            side_effect=AtNotAvailableError("at not installed"),
        )

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--project-root", str(project_root), "pause", "--until", "22:59"],
        )
        assert result.exit_code != 0
        assert "at" in result.output.lower()

    def test_pause_aborts_after_too_many_resumes(self, project_root: Path, mocker):
        _seed(project_root)
        sm = StateManager(project_root)
        state = sm.load()
        state.branches["main"].resume_count = 3  # already at threshold
        sm.save(state)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--project-root", str(project_root), "pause", "--until", "22:59"],
        )
        assert result.exit_code != 0
        assert "3" in result.output or "limit" in result.output.lower()
