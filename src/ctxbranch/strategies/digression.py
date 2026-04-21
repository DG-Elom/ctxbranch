"""Digression strategy : short free-text summary wrapped in a merge block."""

from __future__ import annotations

from typing import Any, ClassVar

from ctxbranch.core.state_manager import Branch

from .base import Strategy

_SUMMARY_MIN = 80
_SUMMARY_MAX = 2000


class DigressionStrategy(Strategy):
    """For orthogonal digressions the user launched mid-task.

    Goal : give the parent session a compact briefing (3-5 sentences) on what was
    learned/decided during the digression, without dragging the whole transcript.
    """

    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "minLength": _SUMMARY_MIN,
                "maxLength": _SUMMARY_MAX,
            },
        },
        "required": ["summary"],
        "additionalProperties": False,
    }

    def prompt(self, branch: Branch) -> str:
        desc = branch.description or "(no description provided)"
        return (
            f'You were working on a digression: "{desc}".\n\n'
            "Write a compact briefing (3-5 sentences) of what was discovered or "
            "decided during this digression, formatted for the parent session that "
            "will resume without you. Markdown only — no preamble, no meta-commentary.\n\n"
            "Output JSON matching the provided schema."
        )

    def render(
        self,
        branch: Branch,
        payload: dict[str, Any] | None = None,
        raw_text: str | None = None,
    ) -> str:
        summary = ""
        if payload is not None:
            summary = str(payload.get("summary", "")).strip()
        elif raw_text is not None:
            summary = raw_text.strip()

        return (
            f'<ctxbranch:merge intent="digression" branch="{branch.name}">\n'
            f"{summary}\n"
            "</ctxbranch:merge>"
        )
