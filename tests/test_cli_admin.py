"""Tests for init / doctor / install commands."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from ctxbranch.cli import main
from ctxbranch.core.state_manager import StateManager


class TestInitCommand:
    def test_init_creates_main_branch(self, project_root: Path):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--project-root",
                str(project_root),
                "init",
                "--session-id",
                "my-session-uuid",
            ],
        )
        assert result.exit_code == 0, result.output

        state = StateManager(project_root).load()
        assert "main" in state.branches
        assert state.branches["main"].session_id == "my-session-uuid"
        assert state.current_branch == "main"

    def test_init_uses_env_session_id_when_not_passed(self, project_root: Path, monkeypatch):
        monkeypatch.setenv("CLAUDE_SESSION_ID", "env-sess-uuid")
        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "init"])
        assert result.exit_code == 0, result.output
        state = StateManager(project_root).load()
        assert state.branches["main"].session_id == "env-sess-uuid"

    def test_init_fails_when_no_session_source(self, project_root: Path, monkeypatch):
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "init"])
        assert result.exit_code != 0
        assert "session" in result.output.lower()

    def test_init_is_idempotent(self, project_root: Path):
        runner = CliRunner()
        args = [
            "--project-root",
            str(project_root),
            "init",
            "--session-id",
            "s1",
        ]
        r1 = runner.invoke(main, args)
        assert r1.exit_code == 0
        r2 = runner.invoke(main, args)
        # Second call is a no-op (not an error)
        assert r2.exit_code == 0
        assert "already initialized" in r2.output.lower()


class TestDoctorCommand:
    def test_doctor_reports_claude_and_at(self, project_root: Path, mocker):
        mocker.patch("ctxbranch.cli.claude_version", return_value="2.1.116 (Claude Code)")
        mocker.patch("ctxbranch.cli.is_at_available", return_value=True)

        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "doctor"])
        assert result.exit_code == 0, result.output
        assert "claude" in result.output.lower()
        assert "2.1.116" in result.output
        assert "at" in result.output.lower()

    def test_doctor_flags_missing_claude(self, project_root: Path, mocker):
        from ctxbranch.core.claude_invoker import ClaudeNotFoundError

        mocker.patch(
            "ctxbranch.cli.claude_version",
            side_effect=ClaudeNotFoundError("missing"),
        )
        mocker.patch("ctxbranch.cli.is_at_available", return_value=True)

        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "doctor"])
        assert result.exit_code != 0
        assert "claude" in result.output.lower()

    def test_doctor_flags_missing_at(self, project_root: Path, mocker):
        mocker.patch("ctxbranch.cli.claude_version", return_value="2.1")
        mocker.patch("ctxbranch.cli.is_at_available", return_value=False)

        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "doctor"])
        # doctor exits non-zero when anything is missing
        assert result.exit_code != 0
        assert "at" in result.output.lower()


class TestInstallCommand:
    def test_install_copies_slash_commands_to_target(
        self, project_root: Path, tmp_path: Path, mocker
    ):
        # Fake $HOME/.claude/commands target
        target = tmp_path / "commands"
        mocker.patch("ctxbranch.cli._slash_commands_target", return_value=target)

        runner = CliRunner()
        result = runner.invoke(main, ["--project-root", str(project_root), "install"])
        assert result.exit_code == 0, result.output
        # At minimum the four core slash-commands should exist
        names = {p.name for p in target.glob("*.md")}
        assert {"fork.md", "merge.md", "throw.md", "tree.md"}.issubset(names)

    def test_install_is_idempotent(self, project_root: Path, tmp_path: Path, mocker):
        target = tmp_path / "commands"
        mocker.patch("ctxbranch.cli._slash_commands_target", return_value=target)

        runner = CliRunner()
        runner.invoke(main, ["--project-root", str(project_root), "install"])
        r2 = runner.invoke(main, ["--project-root", str(project_root), "install"])
        assert r2.exit_code == 0
