"""Tests for ctxbranch.core.scheduler."""

from __future__ import annotations

import subprocess

import pytest

from ctxbranch.core.scheduler import (
    AtNotAvailableError,
    SchedulerError,
    _extract_job_id,
    is_at_available,
    remove_at_job,
    schedule_at,
)


class TestIsAtAvailable:
    def test_returns_bool(self, mocker):
        mocker.patch("shutil.which", return_value="/usr/bin/at")
        assert is_at_available() is True
        mocker.patch("shutil.which", return_value=None)
        assert is_at_available() is False


class TestScheduleAt:
    def test_success_returns_job_id(self, mocker):
        mocker.patch("ctxbranch.core.scheduler.is_at_available", return_value=True)
        completed = subprocess.CompletedProcess(
            args=["at"],
            returncode=0,
            stdout="",
            stderr="job 42 at Wed Apr 21 22:59:00 2026\n",
        )
        mocker.patch("subprocess.run", return_value=completed)

        job_id = schedule_at("/tmp/x.sh", "22:59")
        assert job_id == "42"

    def test_uses_log_redirection_when_log_path_given(self, mocker):
        mocker.patch("ctxbranch.core.scheduler.is_at_available", return_value=True)
        completed = subprocess.CompletedProcess(
            args=["at"], returncode=0, stdout="", stderr="job 7 at x\n"
        )
        run = mocker.patch("subprocess.run", return_value=completed)

        schedule_at("/tmp/x.sh", "now + 1 minute", log_path="/tmp/x.log")
        call = run.call_args
        assert "bash /tmp/x.sh >> /tmp/x.log 2>&1" in call.kwargs["input"]

    def test_raises_when_at_missing(self, mocker):
        mocker.patch("ctxbranch.core.scheduler.is_at_available", return_value=False)
        with pytest.raises(AtNotAvailableError):
            schedule_at("/tmp/x.sh", "22:59")

    def test_raises_on_nonzero_exit(self, mocker):
        mocker.patch("ctxbranch.core.scheduler.is_at_available", return_value=True)
        completed = subprocess.CompletedProcess(
            args=["at"], returncode=1, stdout="", stderr="bad time"
        )
        mocker.patch("subprocess.run", return_value=completed)
        with pytest.raises(SchedulerError, match="exit 1"):
            schedule_at("/tmp/x.sh", "yesterday")

    def test_raises_when_job_id_not_parseable(self, mocker):
        mocker.patch("ctxbranch.core.scheduler.is_at_available", return_value=True)
        completed = subprocess.CompletedProcess(
            args=["at"], returncode=0, stdout="", stderr="weird output"
        )
        mocker.patch("subprocess.run", return_value=completed)
        with pytest.raises(SchedulerError, match="could not parse"):
            schedule_at("/tmp/x.sh", "22:59")


class TestRemoveAtJob:
    def test_calls_atrm(self, mocker):
        mocker.patch("ctxbranch.core.scheduler.is_at_available", return_value=True)
        run = mocker.patch("subprocess.run")
        remove_at_job("42")
        args = run.call_args.args[0]
        assert args == ["atrm", "42"]

    def test_raises_when_at_missing(self, mocker):
        mocker.patch("ctxbranch.core.scheduler.is_at_available", return_value=False)
        with pytest.raises(AtNotAvailableError):
            remove_at_job("42")


class TestExtractJobId:
    def test_parses_standard_at_output(self):
        assert _extract_job_id("job 42 at Wed Apr 21 22:59:00 2026") == "42"

    def test_returns_none_on_garbage(self):
        assert _extract_job_id("nothing here") is None
