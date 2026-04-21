"""Tests for hypothesis, ab, checkpoint strategies."""

from __future__ import annotations

import pytest

from ctxbranch.core.state_manager import Branch, Intent
from ctxbranch.strategies import get_strategy
from ctxbranch.strategies.ab import AbStrategy
from ctxbranch.strategies.checkpoint import CheckpointStrategy
from ctxbranch.strategies.hypothesis import HypothesisStrategy


def _branch(name: str, intent: Intent, desc: str) -> Branch:
    return Branch(
        name=name,
        session_id=f"sess-{name}",
        parent="main",
        intent=intent,
        description=desc,
    )


class TestRegistryCoverage:
    @pytest.mark.parametrize(
        "intent,cls",
        [
            (Intent.HYPOTHESIS, HypothesisStrategy),
            (Intent.AB, AbStrategy),
            (Intent.CHECKPOINT, CheckpointStrategy),
        ],
    )
    def test_registry_resolves_all_intents(self, intent, cls):
        assert isinstance(get_strategy(intent), cls)


class TestHypothesisStrategy:
    def test_prompt_contains_description(self):
        s = HypothesisStrategy()
        b = _branch("h-1", Intent.HYPOTHESIS, "swap auth to JWT")
        assert "swap auth to JWT" in s.prompt(b)
        assert "verdict" in s.prompt(b)

    def test_schema_enum_verdict(self):
        enum = HypothesisStrategy().schema["properties"]["verdict"]["enum"]
        assert set(enum) == {"worked", "partial", "failed"}

    def test_render_structured_payload(self):
        s = HypothesisStrategy()
        b = _branch("h-1", Intent.HYPOTHESIS, "x")
        out = s.render(
            branch=b,
            payload={
                "verdict": "worked",
                "diff_summary": [{"file": "src/auth.py", "change": "use JWT"}],
                "key_findings": ["TTL OK", "Refresh works"],
                "next_steps": [],
            },
        )
        assert "worked" in out
        assert "src/auth.py" in out
        assert "TTL OK" in out
        assert "<ctxbranch:merge" in out
        assert 'intent="hypothesis"' in out

    def test_render_fallback_raw(self):
        s = HypothesisStrategy()
        b = _branch("h-1", Intent.HYPOTHESIS, "x")
        out = s.render(branch=b, raw_text="quick note")
        assert "quick note" in out
        assert "<ctxbranch:merge" in out


class TestAbStrategy:
    def test_schema_requires_approach_name_and_summary(self):
        schema = AbStrategy().schema
        assert "approach_name" in schema["required"]
        assert "summary" in schema["required"]
        assert "pros" in schema["required"]

    def test_render_includes_pros_cons_metrics(self):
        s = AbStrategy()
        b = _branch("ab-a", Intent.AB, "approach A")
        out = s.render(
            branch=b,
            payload={
                "approach_name": "Middleware",
                "summary": "We implemented a centralized middleware for auth and logging.",
                "pros": ["Central", "Easy"],
                "cons": ["Less flexible"],
                "metrics": {"loc": 120, "complexity": "low", "files_touched": 3},
            },
        )
        assert "Middleware" in out
        assert "Central" in out
        assert "Less flexible" in out
        assert "loc" in out


class TestCheckpointStrategy:
    def test_schema_requires_goal_and_next_steps(self):
        req = CheckpointStrategy().schema["required"]
        assert "goal" in req
        assert "in_progress" in req
        assert "next_steps" in req

    def test_render_all_sections(self):
        s = CheckpointStrategy()
        b = _branch("cp-1", Intent.CHECKPOINT, "pre-compact")
        out = s.render(
            branch=b,
            payload={
                "goal": "Ship ctxbranch v0.1",
                "completed": ["scaffold", "state_manager"],
                "in_progress": "merge command",
                "decisions": [
                    {
                        "topic": "language",
                        "choice": "Python",
                        "rationale": "matches ecosystem",
                    }
                ],
                "artifacts": [{"path": "src/ctxbranch/cli.py", "role": "entry point"}],
                "next_steps": ["add hypothesis strategy"],
                "open_questions": ["bundle slash-commands how?"],
            },
        )
        assert "Ship ctxbranch v0.1" in out
        assert "scaffold" in out
        assert "merge command" in out
        assert "language" in out and "Python" in out
        assert "src/ctxbranch/cli.py" in out
        assert "bundle slash-commands how?" in out
