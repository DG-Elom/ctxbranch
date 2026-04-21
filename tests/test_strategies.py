"""Tests for merge-back strategies."""

from __future__ import annotations

import pytest

from ctxbranch.core.state_manager import Branch, Intent
from ctxbranch.strategies import get_strategy
from ctxbranch.strategies.base import Strategy
from ctxbranch.strategies.digression import DigressionStrategy


@pytest.fixture()
def digression_branch() -> Branch:
    return Branch(
        name="digression-jwt-1776808900",
        session_id="abcd-1234",
        parent="main",
        intent=Intent.DIGRESSION,
        description="check refresh token TTL",
    )


class TestStrategyRegistry:
    def test_get_digression_returns_digression_strategy(self):
        strat = get_strategy(Intent.DIGRESSION)
        assert isinstance(strat, DigressionStrategy)

    def test_get_unknown_intent_raises(self):
        with pytest.raises(ValueError, match="no strategy"):
            get_strategy("unknown-intent")


class TestDigressionStrategy:
    def test_is_a_strategy(self):
        assert isinstance(DigressionStrategy(), Strategy)

    def test_prompt_contains_description(self, digression_branch: Branch):
        strat = DigressionStrategy()
        prompt = strat.prompt(digression_branch)
        assert "check refresh token TTL" in prompt
        assert "digression" in prompt.lower()

    def test_schema_requires_summary_field(self):
        strat = DigressionStrategy()
        schema = strat.schema
        assert schema["type"] == "object"
        assert "summary" in schema["properties"]
        assert "summary" in schema["required"]

    def test_schema_enforces_summary_length(self):
        strat = DigressionStrategy()
        schema = strat.schema["properties"]["summary"]
        # summary should have min/max constraints to force ~3-5 sentences
        assert schema.get("minLength", 0) > 0
        assert schema.get("maxLength", 0) > schema.get("minLength", 0)

    def test_render_wraps_summary_in_merge_block(self, digression_branch: Branch):
        strat = DigressionStrategy()
        rendered = strat.render(
            branch=digression_branch, payload={"summary": "Refresh TTL is 3600s, confirmed OK."}
        )
        assert "<ctxbranch:merge" in rendered
        assert 'intent="digression"' in rendered
        assert 'branch="digression-jwt-1776808900"' in rendered
        assert "Refresh TTL is 3600s, confirmed OK." in rendered
        assert "</ctxbranch:merge>" in rendered

    def test_render_from_raw_text_fallback(self, digression_branch: Branch):
        """When schema-mode fails, we fall back to free text — render should accept it."""
        strat = DigressionStrategy()
        rendered = strat.render(branch=digression_branch, raw_text="quick free form summary")
        assert "quick free form summary" in rendered
        assert "<ctxbranch:merge" in rendered
