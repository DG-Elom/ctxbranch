"""Thin wrapper around the `at` one-shot scheduler.

`at` is used instead of cron because pauses are one-off : resume at a specific
wall-clock time and never again.
"""

from __future__ import annotations

import re
import shutil
import subprocess


class SchedulerError(RuntimeError):
    """Raised when the `at` scheduler fails."""


class AtNotAvailableError(SchedulerError):
    """Raised when `at` is not installed on the system."""


def is_at_available() -> bool:
    """True when `at` binary is reachable on PATH."""
    return shutil.which("at") is not None


def schedule_at(
    script_path: str,
    when: str,
    log_path: str | None = None,
) -> str:
    """Schedule `bash <script_path>` to run at the given time via `at`.

    Parameters
    ----------
    script_path:
        Absolute path to a bash script to execute.
    when:
        A time expression understood by `at` (e.g. "22:59", "22:59 today", "now + 4 hours").
    log_path:
        Optional path to redirect stdout+stderr to.

    Returns the `at` job id as a string. Raises AtNotAvailableError or SchedulerError.
    """
    if not is_at_available():
        raise AtNotAvailableError(
            "`at` is not installed — `sudo apt install at` (Debian) or equivalent."
        )

    command = f"bash {script_path} >> {log_path} 2>&1" if log_path else f"bash {script_path}"

    try:
        completed = subprocess.run(
            ["at", when],
            input=command,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except FileNotFoundError as exc:  # defensive — shouldn't hit after is_at_available
        raise AtNotAvailableError("`at` disappeared between check and run") from exc

    if completed.returncode != 0:
        raise SchedulerError(
            f"`at` failed (exit {completed.returncode}): {completed.stderr.strip()}"
        )

    # `at` writes job info to stderr: "job 42 at Wed Apr 21 22:59:00 2026"
    job_id = _extract_job_id(completed.stderr) or _extract_job_id(completed.stdout)
    if job_id is None:
        raise SchedulerError(
            f"could not parse `at` job id from output : {completed.stderr or completed.stdout}"
        )
    return job_id


def remove_at_job(job_id: str) -> None:
    """Cancel a scheduled `at` job via `atrm`."""
    if not is_at_available():
        raise AtNotAvailableError("`at` / `atrm` not installed")
    try:
        subprocess.run(
            ["atrm", job_id],
            check=False,
            capture_output=True,
            timeout=10,
        )
    except FileNotFoundError as exc:
        raise AtNotAvailableError("`atrm` not installed") from exc


_JOB_ID_RE = re.compile(r"job\s+(\d+)")


def _extract_job_id(text: str) -> str | None:
    match = _JOB_ID_RE.search(text)
    return match.group(1) if match else None
