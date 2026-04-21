"""Subprocess wrapper around the `claude` CLI.

Builds commands, invokes them, parses outputs. No retry/fallback logic here —
that belongs to higher layers.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any

CLAUDE_BIN = "claude"

__all__ = [
    "CLAUDE_BIN",
    "ClaudeInvokerError",
    "ClaudeNotFoundError",
    "HeadlessResult",
    "build_fork_command",
    "build_headless_command",
    "fork_interactive",
    "headless_call",
    "version",
]


class ClaudeInvokerError(RuntimeError):
    """Raised when the `claude` CLI fails or misbehaves."""


class ClaudeNotFoundError(ClaudeInvokerError):
    """Raised when the `claude` CLI is not on PATH."""


@dataclass(frozen=True, slots=True)
class HeadlessResult:
    """Parsed result from a headless claude call."""

    parsed: dict[str, Any] | list[Any] | None
    raw_text: str | None
    session_id: str | None = None


def build_fork_command(
    parent_session_id: str,
    new_session_id: str,
    branch_name: str | None,
) -> list[str]:
    cmd: list[str] = [
        CLAUDE_BIN,
        "--resume",
        parent_session_id,
        "--fork-session",
        "--session-id",
        new_session_id,
    ]
    if branch_name:
        cmd.extend(["-n", branch_name])
    return cmd


def build_headless_command(
    session_id: str,
    prompt: str,
    system_prompt: str | None,
    json_schema: dict[str, Any] | None,
) -> list[str]:
    cmd: list[str] = [
        CLAUDE_BIN,
        "--resume",
        session_id,
        "--print",
        "--output-format",
        "json",
    ]
    if system_prompt:
        cmd.extend(["--append-system-prompt", system_prompt])
    if json_schema is not None:
        cmd.extend(["--json-schema", json.dumps(json_schema)])
    cmd.append(prompt)
    return cmd


def fork_interactive(
    parent_session_id: str,
    new_session_id: str,
    branch_name: str | None,
    cwd: str,
) -> subprocess.Popen[bytes]:
    """Spawn an interactive Claude Code session forked from the parent.

    Returns the Popen handle so the caller can wait/pipe.
    """
    cmd = build_fork_command(parent_session_id, new_session_id, branch_name)
    try:
        return subprocess.Popen(cmd, cwd=cwd)
    except FileNotFoundError as exc:
        raise ClaudeNotFoundError(
            "claude CLI not found on PATH — install via `npm i -g @anthropic-ai/claude-code`"
        ) from exc


def headless_call(
    session_id: str,
    prompt: str,
    system_prompt: str | None,
    json_schema: dict[str, Any] | None,
    timeout: int = 120,
) -> HeadlessResult:
    """Run a non-interactive `claude --print` call against a session.

    When a json_schema is provided, the CLI output's `result` field is parsed as JSON.
    Otherwise it is returned as raw text.
    """
    cmd = build_headless_command(session_id, prompt, system_prompt, json_schema)
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ClaudeNotFoundError(
            "claude CLI not found on PATH — install via `npm i -g @anthropic-ai/claude-code`"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ClaudeInvokerError(f"claude headless call timeout after {timeout}s") from exc

    if completed.returncode != 0:
        raise ClaudeInvokerError(
            f"claude exited with code {completed.returncode}: {completed.stderr.strip()}"
        )

    return _parse_headless_output(completed.stdout, want_json=json_schema is not None)


def version() -> str:
    try:
        completed = subprocess.run(
            [CLAUDE_BIN, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ClaudeNotFoundError("claude CLI not found on PATH") from exc
    if completed.returncode != 0:
        raise ClaudeInvokerError(f"claude --version failed: {completed.stderr}")
    return completed.stdout.strip()


def _parse_headless_output(stdout: str, *, want_json: bool) -> HeadlessResult:
    """Parse `claude --print --output-format json` output.

    Expected shape: {"type": "result", "result": <string>, "subtype": "success"}
    When want_json is True, `result` itself is JSON-parsed.
    """
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ClaudeInvokerError(f"claude output is not valid JSON: {stdout[:200]}") from exc

    if envelope.get("subtype") and envelope["subtype"] != "success":
        raise ClaudeInvokerError(
            f"claude reported non-success: {envelope.get('subtype')} — {envelope.get('result', '')[:200]}"
        )

    result = envelope.get("result", "")
    session_id = envelope.get("session_id")

    if not want_json:
        return HeadlessResult(parsed=None, raw_text=result, session_id=session_id)

    try:
        parsed = json.loads(result) if isinstance(result, str) else result
    except json.JSONDecodeError as exc:
        raise ClaudeInvokerError(
            f"claude result is not valid JSON (schema mode): {result[:200]}"
        ) from exc
    return HeadlessResult(parsed=parsed, raw_text=None, session_id=session_id)
