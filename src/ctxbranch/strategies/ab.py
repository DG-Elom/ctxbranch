"""A/B strategy : single branch produces a structured one-sided summary.

Comparing two branches A and B is the responsibility of a higher-level `compare`
command — each side produces its payload via this strategy.
"""

from __future__ import annotations

from typing import Any, ClassVar

from ctxbranch.core.state_manager import Branch

from .base import Strategy


class AbStrategy(Strategy):
    """Produces one side of an A/B comparison : summary, pros, cons, metrics."""

    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "approach_name": {"type": "string", "minLength": 1},
            "summary": {"type": "string", "minLength": 50, "maxLength": 1500},
            "pros": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "cons": {
                "type": "array",
                "items": {"type": "string"},
            },
            "metrics": {
                "type": "object",
                "properties": {
                    "loc": {"type": "integer", "minimum": 0},
                    "complexity": {"type": "string", "enum": ["low", "med", "high"]},
                    "files_touched": {"type": "integer", "minimum": 0},
                },
                "additionalProperties": True,
            },
        },
        "required": ["approach_name", "summary", "pros"],
        "additionalProperties": False,
    }

    def prompt(self, branch: Branch) -> str:
        desc = branch.description or "(no description provided)"
        return (
            f'You implemented one side of an A/B comparison: "{desc}".\n\n'
            "Report in JSON :\n"
            "  - approach_name : short label for this approach\n"
            "  - summary : 50-1500 chars explaining what you built and how\n"
            "  - pros : upsides vs the other approach\n"
            "  - cons : downsides\n"
            "  - metrics : {loc, complexity (low|med|high), files_touched}\n\n"
            "Output JSON only, matching the provided schema."
        )

    def render(
        self,
        branch: Branch,
        payload: dict[str, Any] | None = None,
        raw_text: str | None = None,
    ) -> str:
        lines = [f'<ctxbranch:merge intent="ab" branch="{branch.name}">']
        if payload is not None:
            lines.append(f"**Approach** : {payload.get('approach_name', '?')}")
            lines.append("")
            lines.append(str(payload.get("summary", "")).strip())

            pros = payload.get("pros") or []
            if pros:
                lines.append("")
                lines.append("**Pros :**")
                for p in pros:
                    lines.append(f"- {p}")

            cons = payload.get("cons") or []
            if cons:
                lines.append("")
                lines.append("**Cons :**")
                for c in cons:
                    lines.append(f"- {c}")

            metrics = payload.get("metrics") or {}
            if metrics:
                lines.append("")
                lines.append("**Metrics :**")
                for k, v in metrics.items():
                    lines.append(f"- {k} : {v}")
        elif raw_text is not None:
            lines.append(raw_text.strip())
        lines.append("</ctxbranch:merge>")
        return "\n".join(lines)
