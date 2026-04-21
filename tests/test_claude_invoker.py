"""Tests for ctxbranch.core.claude_invoker."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock

import pytest

from ctxbranch.core.claude_invoker import (
    ClaudeInvokerError,
    ClaudeNotFoundError,
    HeadlessResult,
    build_fork_command,
    build_headless_command,
    fork_interactive,
    headless_call,
    version,
)


class TestBuildForkCommand:
    def test_includes_resume_fork_and_session_id(self):
        cmd = build_fork_command(
            parent_session_id="abc-123",
            new_session_id="def-456",
            branch_name="digression-x",
        )
        assert "claude" in cmd
        assert "--resume" in cmd
        assert "abc-123" in cmd
        assert "--fork-session" in cmd
        assert "--session-id" in cmd
        assert "def-456" in cmd
        assert "-n" in cmd
        assert "digression-x" in cmd

    def test_no_branch_name_omits_name_flag(self):
        cmd = build_fork_command(
            parent_session_id="abc-123",
            new_session_id="def-456",
            branch_name=None,
        )
        assert "-n" not in cmd


class TestBuildHeadlessCommand:
    def test_includes_print_and_output_format_json(self):
        cmd = build_headless_command(
            session_id="abc",
            prompt="summarize this",
            system_prompt="you are a summarizer",
            json_schema=None,
        )
        assert "claude" in cmd
        assert "--resume" in cmd
        assert "abc" in cmd
        assert "--print" in cmd
        assert "--output-format" in cmd
        assert "json" in cmd
        assert "summarize this" in cmd

    def test_schema_triggers_json_schema_flag(self):
        schema = {"type": "object", "properties": {"summary": {"type": "string"}}}
        cmd = build_headless_command(
            session_id="abc",
            prompt="x",
            system_prompt=None,
            json_schema=schema,
        )
        assert "--json-schema" in cmd
        idx = cmd.index("--json-schema")
        assert json.loads(cmd[idx + 1]) == schema

    def test_system_prompt_triggers_append_flag(self):
        cmd = build_headless_command(
            session_id="abc",
            prompt="x",
            system_prompt="be terse",
            json_schema=None,
        )
        assert "--append-system-prompt" in cmd
        idx = cmd.index("--append-system-prompt")
        assert cmd[idx + 1] == "be terse"


class TestForkInteractive:
    def test_returns_popen_object(self, mocker):
        popen_mock = MagicMock(spec=subprocess.Popen)
        mocker.patch("subprocess.Popen", return_value=popen_mock)

        proc = fork_interactive(
            parent_session_id="a",
            new_session_id="b",
            branch_name="br",
            cwd="/tmp",
        )
        assert proc is popen_mock
        subprocess.Popen.assert_called_once()

    def test_raises_when_claude_not_on_path(self, mocker):
        mocker.patch("subprocess.Popen", side_effect=FileNotFoundError)
        with pytest.raises(ClaudeNotFoundError):
            fork_interactive("a", "b", "br", "/tmp")


class TestHeadlessCall:
    def test_returns_structured_result_on_success(self, mocker):
        response_json = json.dumps(
            {
                "type": "result",
                "result": json.dumps({"summary": "hello"}),
                "subtype": "success",
            }
        )
        completed = subprocess.CompletedProcess(
            args=["claude"], returncode=0, stdout=response_json, stderr=""
        )
        mocker.patch("subprocess.run", return_value=completed)

        res = headless_call(
            session_id="abc",
            prompt="x",
            system_prompt=None,
            json_schema={"type": "object"},
            timeout=30,
        )
        assert isinstance(res, HeadlessResult)
        assert res.parsed == {"summary": "hello"}
        assert res.raw_text is None

    def test_returns_text_when_no_schema(self, mocker):
        response_json = json.dumps(
            {
                "type": "result",
                "result": "plain text summary",
                "subtype": "success",
            }
        )
        completed = subprocess.CompletedProcess(
            args=["claude"], returncode=0, stdout=response_json, stderr=""
        )
        mocker.patch("subprocess.run", return_value=completed)

        res = headless_call(
            session_id="abc",
            prompt="x",
            system_prompt=None,
            json_schema=None,
            timeout=30,
        )
        assert res.parsed is None
        assert res.raw_text == "plain text summary"

    def test_raises_on_nonzero_exit(self, mocker):
        completed = subprocess.CompletedProcess(
            args=["claude"], returncode=1, stdout="", stderr="boom"
        )
        mocker.patch("subprocess.run", return_value=completed)
        with pytest.raises(ClaudeInvokerError, match="exited with code 1"):
            headless_call("abc", "x", None, None, 30)

    def test_raises_on_timeout(self, mocker):
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=30),
        )
        with pytest.raises(ClaudeInvokerError, match="timeout"):
            headless_call("abc", "x", None, None, 30)

    def test_raises_when_claude_not_on_path(self, mocker):
        mocker.patch("subprocess.run", side_effect=FileNotFoundError)
        with pytest.raises(ClaudeNotFoundError):
            headless_call("abc", "x", None, None, 30)


class TestVersion:
    def test_returns_version_string(self, mocker):
        completed = subprocess.CompletedProcess(
            args=["claude", "--version"],
            returncode=0,
            stdout="2.1.116 (Claude Code)\n",
            stderr="",
        )
        mocker.patch("subprocess.run", return_value=completed)
        assert version() == "2.1.116 (Claude Code)"

    def test_raises_when_claude_missing(self, mocker):
        mocker.patch("subprocess.run", side_effect=FileNotFoundError)
        with pytest.raises(ClaudeNotFoundError):
            version()
