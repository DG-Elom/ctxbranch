"""Strategy ABC : contract that every merge-back strategy must honor."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from ctxbranch.core.state_manager import Branch


class Strategy(ABC):
    """A merge-back strategy bound to a specific Intent.

    Each concrete strategy provides :
    - a prompt the headless Claude call uses to produce the merge payload
    - a JSON schema that constrains the payload (None = free text)
    - a renderer that turns the payload into the markdown block injected in the parent
    """

    #: JSON schema that constrains the headless call's output. None means free text.
    schema: ClassVar[dict[str, Any] | None] = None

    @abstractmethod
    def prompt(self, branch: Branch) -> str:
        """Prompt handed to the headless Claude call run against the branch."""

    @abstractmethod
    def render(
        self,
        branch: Branch,
        payload: dict[str, Any] | None = None,
        raw_text: str | None = None,
    ) -> str:
        """Render the final markdown block to inject into the parent session.

        Either `payload` (schema-valid) or `raw_text` (fallback) is provided.
        """
