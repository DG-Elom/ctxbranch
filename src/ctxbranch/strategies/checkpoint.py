"""Checkpoint strategy : exhaustive pre-compact / pre-pause snapshot."""

from __future__ import annotations

from typing import Any, ClassVar

from ctxbranch.core.state_manager import Branch

from .base import Strategy


class CheckpointStrategy(Strategy):
    """Largest payload — captures full working state so a fresh session can resume."""

    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "goal": {"type": "string", "minLength": 10},
            "completed": {"type": "array", "items": {"type": "string"}},
            "in_progress": {"type": "string"},
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "choice": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["topic", "choice"],
                    "additionalProperties": False,
                },
            },
            "artifacts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "role": {"type": "string"},
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            "next_steps": {"type": "array", "items": {"type": "string"}},
            "open_questions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["goal", "in_progress", "next_steps"],
        "additionalProperties": False,
    }

    def prompt(self, branch: Branch) -> str:
        desc = branch.description or "(no description provided)"
        return (
            f'You are producing a checkpoint before context reset: "{desc}".\n\n'
            "Produce a full snapshot in JSON so a fresh Claude session can resume without loss. "
            "Fields :\n"
            "  - goal : the active goal of this session (>=10 chars)\n"
            "  - completed : list of finished steps\n"
            "  - in_progress : the task currently being worked on\n"
            "  - decisions : list of {topic, choice, rationale} for non-trivial calls\n"
            "  - artifacts : list of {path, role} for files that matter\n"
            "  - next_steps : ordered remaining work\n"
            "  - open_questions : unresolved things the resumer must investigate\n\n"
            "Be specific enough that a resumer can act without re-reading the transcript."
        )

    def render(
        self,
        branch: Branch,
        payload: dict[str, Any] | None = None,
        raw_text: str | None = None,
    ) -> str:
        lines = [f'<ctxbranch:merge intent="checkpoint" branch="{branch.name}">']
        if payload is not None:
            lines.append(f"**Goal** : {payload.get('goal', '?')}")
            lines.append("")
            lines.append(f"**In progress** : {payload.get('in_progress', '?')}")

            for section_key, heading in [
                ("completed", "Completed"),
                ("next_steps", "Next steps"),
                ("open_questions", "Open questions"),
            ]:
                items = payload.get(section_key) or []
                if items:
                    lines.append("")
                    lines.append(f"**{heading} :**")
                    for item in items:
                        lines.append(f"- {item}")

            decisions = payload.get("decisions") or []
            if decisions:
                lines.append("")
                lines.append("**Decisions :**")
                for d in decisions:
                    base = f"- **{d.get('topic', '?')}** → {d.get('choice', '?')}"
                    if d.get("rationale"):
                        base += f" _({d['rationale']})_"
                    lines.append(base)

            artifacts = payload.get("artifacts") or []
            if artifacts:
                lines.append("")
                lines.append("**Artifacts :**")
                for a in artifacts:
                    role = f" — {a['role']}" if a.get("role") else ""
                    lines.append(f"- `{a['path']}`{role}")
        elif raw_text is not None:
            lines.append(raw_text.strip())
        lines.append("</ctxbranch:merge>")
        return "\n".join(lines)
