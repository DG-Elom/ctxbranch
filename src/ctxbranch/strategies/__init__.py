"""Merge-back strategies : digression, hypothesis, ab, checkpoint."""

from __future__ import annotations

from ctxbranch.core.state_manager import Intent

from .base import Strategy
from .digression import DigressionStrategy

__all__ = [
    "DigressionStrategy",
    "Strategy",
    "get_strategy",
]

_REGISTRY: dict[Intent, type[Strategy]] = {
    Intent.DIGRESSION: DigressionStrategy,
}


def get_strategy(intent: Intent | str) -> Strategy:
    """Resolve a strategy from an Intent or its string value."""
    if isinstance(intent, str):
        try:
            intent = Intent(intent)
        except ValueError as exc:
            raise ValueError(f"no strategy for intent {intent!r}") from exc
    if intent not in _REGISTRY:
        raise ValueError(f"no strategy for intent {intent!r}")
    return _REGISTRY[intent]()
