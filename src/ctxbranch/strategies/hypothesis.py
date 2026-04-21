"""Hypothesis strategy : speculative attempt → verdict + diff + findings + next steps."""

from __future__ import annotations

from typing import Any, ClassVar

from ctxbranch.core.state_manager import Branch

from .base import Strategy


class HypothesisStrategy(Strategy):
    """For speculative debugging / solution attempts.

    The parent needs a verdict, a short diff summary, the key findings and what's
    left to do — not the full tool transcript.
    """

    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["worked", "partial", "failed"]},
            "diff_summary": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string"},
                        "change": {"type": "string"},
                    },
                    "required": ["file", "change"],
                    "additionalProperties": False,
                },
            },
            "key_findings": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 8,
            },
            "next_steps": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["verdict", "key_findings"],
        "additionalProperties": False,
    }

    def prompt(self, branch: Branch) -> str:
        desc = branch.description or "(no description provided)"
        return (
            f'You were testing this hypothesis: "{desc}".\n\n'
            "Report in JSON :\n"
            "  - verdict : 'worked', 'partial' or 'failed'\n"
            "  - diff_summary : array of {file, change} for every file you modified\n"
            "  - key_findings : 1-8 bullets capturing what matters most for the parent\n"
            "  - next_steps : what's left to try / verify (empty if verdict is 'worked')\n\n"
            "Output JSON matching the provided schema only. No preamble."
        )

    def render(
        self,
        branch: Branch,
        payload: dict[str, Any] | None = None,
        raw_text: str | None = None,
    ) -> str:
        lines = [
            f'<ctxbranch:merge intent="hypothesis" branch="{branch.name}">',
        ]
        if payload is not None:
            lines.append(f"**Verdict** : `{payload.get('verdict', '?')}`")
            diffs = payload.get("diff_summary") or []
            if diffs:
                lines.append("")
                lines.append("**Diff :**")
                for d in diffs:
                    lines.append(f"- `{d['file']}` — {d['change']}")
            findings = payload.get("key_findings") or []
            if findings:
                lines.append("")
                lines.append("**Key findings :**")
                for f in findings:
                    lines.append(f"- {f}")
            nexts = payload.get("next_steps") or []
            if nexts:
                lines.append("")
                lines.append("**Next steps :**")
                for n in nexts:
                    lines.append(f"- {n}")
        elif raw_text is not None:
            lines.append(raw_text.strip())
        lines.append("</ctxbranch:merge>")
        return "\n".join(lines)
