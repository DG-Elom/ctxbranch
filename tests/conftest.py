"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    """Temp directory acting as the per-project root where ctxbranch/ lives."""
    return tmp_path


@pytest.fixture()
def ctxbranch_dir(project_root: Path) -> Path:
    """The ctxbranch/ subdirectory (not created by the fixture — let SUT create it)."""
    return project_root / "ctxbranch"
