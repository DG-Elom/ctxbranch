"""Command-line entry point for ctxbranch."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

import click
from rich.console import Console
from rich.tree import Tree

from ctxbranch import __version__
from ctxbranch.core.claude_invoker import (
    ClaudeInvokerError,
    ClaudeNotFoundError,
    build_fork_command,
    headless_call,
)
from ctxbranch.core.claude_invoker import (
    version as claude_version,
)
from ctxbranch.core.scheduler import (
    AtNotAvailableError,
    is_at_available,
    schedule_at,
)
from ctxbranch.core.state_manager import (
    Branch,
    BranchStatus,
    Intent,
    State,
    StateManager,
)
from ctxbranch.strategies import get_strategy
from ctxbranch.strategies.checkpoint import CheckpointStrategy

CONSOLE = Console()
MERGES_DIR = "merges"
PAUSES_DIR = "pauses"
MAX_RESUMES = 3
BUNDLED_SLASH_COMMANDS_DIR = Path(__file__).parent / "slash_commands"

_STATUS_MARK = {
    BranchStatus.ACTIVE: "",
    BranchStatus.MERGED: " [green](merged)[/green]",
    BranchStatus.THROWN: " [dim strike](thrown)[/]",
}


def _intent_choices() -> list[str]:
    return [i.value for i in Intent]


@click.group()
@click.version_option(__version__, prog_name="ctxbranch")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Project root (defaults to the current directory).",
)
@click.pass_context
def main(ctx: click.Context, project_root: Path | None) -> None:
    """Git-like branching for Claude Code conversations."""
    ctx.ensure_object(dict)
    ctx.obj["project_root"] = Path(project_root) if project_root else Path.cwd()


@main.command()
@click.option(
    "--session-id",
    default=None,
    help="Session UUID for the initial `main` branch. Falls back to $CLAUDE_SESSION_ID.",
)
@click.pass_context
def init(ctx: click.Context, session_id: str | None) -> None:
    """Initialize this project with a `main` branch."""
    project_root: Path = ctx.obj["project_root"]
    sm = StateManager(project_root)
    state = sm.load()

    sid = session_id or os.environ.get("CLAUDE_SESSION_ID")
    if not sid:
        raise click.ClickException(
            "No session id — pass --session-id <uuid> or set $CLAUDE_SESSION_ID."
        )

    if "main" in state.branches:
        CONSOLE.print("[dim]Already initialized — main branch exists.[/dim]")
        return

    sm.add_branch(
        name="main",
        session_id=sid,
        parent=None,
        intent=None,
        description=None,
    )
    CONSOLE.print(f"[green]✓[/green] Initialized — main branch tracks session [bold]{sid}[/bold].")


@main.command()
@click.argument("name")
@click.argument("intent", type=click.Choice(_intent_choices(), case_sensitive=False))
@click.argument("description")
@click.option(
    "--parent",
    default=None,
    help="Parent branch (defaults to the current branch).",
)
@click.option(
    "--session-id",
    default=None,
    help="Explicit UUID for the new session (default : auto-generated).",
)
@click.pass_context
def fork(
    ctx: click.Context,
    name: str,
    intent: str,
    description: str,
    parent: str | None,
    session_id: str | None,
) -> None:
    """Fork the current (or given) branch into a new one with a declared intent."""
    project_root: Path = ctx.obj["project_root"]
    sm = StateManager(project_root)
    state = sm.load()

    if not state.branches:
        raise click.ClickException(
            "No branches yet. Initialize with `ctxbranch init` first (coming soon) "
            "or add the first branch representing your current session."
        )

    parent_name = parent or state.current_branch
    if parent_name not in state.branches:
        raise click.ClickException(f"Unknown parent branch : {parent_name!r}.")

    parent_branch = state.branches[parent_name]
    new_session = session_id or str(uuid.uuid4())
    intent_enum = Intent(intent.lower())

    sm.add_branch(
        name=name,
        session_id=new_session,
        parent=parent_name,
        intent=intent_enum,
        description=description,
    )
    sm.switch_branch(name)

    cmd = build_fork_command(
        parent_session_id=parent_branch.session_id,
        new_session_id=new_session,
        branch_name=name,
    )

    CONSOLE.print(
        f"[green]✓[/green] Branch [bold]{name}[/bold] created from [bold]{parent_name}[/bold]."
    )
    CONSOLE.print(f"  intent: {intent_enum.value}")
    CONSOLE.print(f"  session: {new_session}")
    CONSOLE.print()
    CONSOLE.print("[dim]To start working in this branch, run :[/dim]")
    CONSOLE.print(f"  [cyan]{' '.join(cmd)}[/cyan]")


@main.command()
@click.argument("branch_name", required=False)
@click.option(
    "--into",
    default=None,
    help="Parent branch to merge into (defaults to the branch's own parent).",
)
@click.option(
    "--timeout",
    default=180,
    show_default=True,
    help="Timeout (seconds) for the headless summary call.",
)
@click.pass_context
def merge(
    ctx: click.Context,
    branch_name: str | None,
    into: str | None,
    timeout: int,
) -> None:
    """Merge a branch back into its parent via an intent-driven summary."""
    project_root: Path = ctx.obj["project_root"]
    sm = StateManager(project_root)
    state = sm.load()

    branch = _resolve_branch_for_merge(state, branch_name)
    parent_name = into or branch.parent
    if parent_name is None:
        raise click.ClickException(
            f"Branch {branch.name!r} has no parent — it is a root and cannot be merged."
        )
    if parent_name not in state.branches:
        raise click.ClickException(f"Parent branch {parent_name!r} does not exist.")
    if branch.status == BranchStatus.MERGED:
        raise click.ClickException(f"Branch {branch.name!r} is already merged.")
    if branch.intent is None:
        raise click.ClickException(
            f"Branch {branch.name!r} has no intent — cannot pick a merge strategy."
        )

    strategy = get_strategy(branch.intent)
    prompt = strategy.prompt(branch)

    payload, raw_text, fallback = _execute_merge_call(
        branch=branch, prompt=prompt, schema=strategy.schema, timeout=timeout
    )

    merge_id = f"merge-{uuid.uuid4().hex[:10]}"
    artifact = _write_merge_artifact(
        project_root=project_root,
        merge_id=merge_id,
        branch=branch,
        payload=payload,
        raw_text=raw_text,
        fallback=fallback,
    )

    sm.merge_branch(branch.name, merge_id=merge_id)
    sm.switch_branch(parent_name)

    CONSOLE.print(
        f"[green]✓[/green] Branch [bold]{branch.name}[/bold] merged into "
        f"[bold]{parent_name}[/bold] ([dim]{merge_id}[/dim])."
    )
    CONSOLE.print(f"  artifact: {artifact.relative_to(project_root)}")
    CONSOLE.print()
    CONSOLE.print(strategy.render(branch=branch, payload=payload, raw_text=raw_text))


@main.command()
@click.argument("branch_name")
@click.option(
    "--archive",
    is_flag=True,
    help="Keep the underlying .jsonl and branch entry — just mark thrown.",
)
@click.pass_context
def throw(ctx: click.Context, branch_name: str, archive: bool) -> None:
    """Discard a branch (mark it thrown)."""
    project_root: Path = ctx.obj["project_root"]
    sm = StateManager(project_root)
    state = sm.load()
    if branch_name not in state.branches:
        raise click.ClickException(f"Unknown branch {branch_name!r}.")

    branch = state.branches[branch_name]
    sm.throw_branch(branch_name)
    if state.current_branch == branch_name and branch.parent in state.branches:
        sm.switch_branch(branch.parent)

    CONSOLE.print(f"[yellow]✓[/yellow] Branch [bold]{branch_name}[/bold] thrown.")
    if archive:
        CONSOLE.print("[dim]  Archived — entry and .jsonl preserved for audit.[/dim]")


@main.command()
@click.option(
    "--thrown",
    "clean_thrown",
    is_flag=True,
    help="Remove all thrown branches from the tree.",
)
@click.option(
    "--older-than",
    "older_than_days",
    type=int,
    default=None,
    help="Remove merged branches older than N days.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be removed without mutating state.",
)
@click.pass_context
def clean(
    ctx: click.Context,
    clean_thrown: bool,
    older_than_days: int | None,
    dry_run: bool,
) -> None:
    """Garbage-collect thrown or old-merged branches from the tree."""
    if not clean_thrown and older_than_days is None:
        raise click.ClickException("Nothing to do — pass --thrown and/or --older-than <days>.")

    project_root: Path = ctx.obj["project_root"]
    sm = StateManager(project_root)
    state = sm.load()

    victims = _select_clean_victims(state, clean_thrown, older_than_days)

    if not victims:
        CONSOLE.print("[dim]Nothing to clean.[/dim]")
        return

    for name in victims:
        b = state.branches[name]
        CONSOLE.print(
            f"  [red]-[/red] {name} [dim]({b.status.value}, merged_at={b.merged_at or '-'})[/dim]"
        )

    if dry_run:
        CONSOLE.print("[dim]Dry run — nothing removed.[/dim]")
        return

    for name in victims:
        sm.remove_branch(name)

    CONSOLE.print(f"[green]✓[/green] Removed {len(victims)} branch(es) from the tree.")


@main.command()
@click.argument("branch_name")
@click.pass_context
def resume(ctx: click.Context, branch_name: str) -> None:
    """Emit the `claude --resume` command for a branch and set it as current."""
    project_root: Path = ctx.obj["project_root"]
    sm = StateManager(project_root)
    state = sm.load()
    if branch_name not in state.branches:
        raise click.ClickException(f"Unknown branch {branch_name!r}.")

    branch = state.branches[branch_name]
    sm.switch_branch(branch_name)

    if branch.status == BranchStatus.THROWN:
        CONSOLE.print(
            f"[yellow]⚠[/yellow] Branch [bold]{branch_name}[/bold] was thrown — resuming it anyway."
        )

    cmd = ["claude", "--resume", branch.session_id]
    CONSOLE.print(f"[green]✓[/green] Current branch set to [bold]{branch_name}[/bold].")
    CONSOLE.print("[dim]To resume interactively :[/dim]")
    CONSOLE.print(f"  [cyan]{' '.join(cmd)}[/cyan]")


@main.command()
@click.option(
    "--until",
    "until",
    required=True,
    help="Time expression understood by `at` (e.g. 22:59, 'now + 4 hours').",
)
@click.option(
    "--branch",
    "branch_name",
    default=None,
    help="Branch to pause (default : current).",
)
@click.option(
    "--timeout",
    default=180,
    show_default=True,
    help="Timeout for the checkpoint headless call.",
)
@click.pass_context
def pause(
    ctx: click.Context,
    until: str,
    branch_name: str | None,
    timeout: int,
) -> None:
    """Checkpoint a branch and schedule a `claude --resume` at the given time."""
    project_root: Path = ctx.obj["project_root"]
    sm = StateManager(project_root)
    state = sm.load()
    name = branch_name or state.current_branch
    if name not in state.branches:
        raise click.ClickException(f"Unknown branch {name!r}.")
    branch = state.branches[name]

    if branch.resume_count >= MAX_RESUMES:
        raise click.ClickException(
            f"Branch {name!r} has reached the resume limit ({MAX_RESUMES}) — "
            "intervene manually before scheduling another auto-resume."
        )

    strategy = CheckpointStrategy()
    prompt = strategy.prompt(branch)

    CONSOLE.print(f"[dim]Producing checkpoint for {name!r}…[/dim]")
    try:
        result = headless_call(
            session_id=branch.session_id,
            prompt=prompt,
            system_prompt=None,
            json_schema=strategy.schema,
            timeout=timeout,
        )
        payload = result.parsed
        raw_text = None
    except ClaudeInvokerError as exc:
        CONSOLE.print(
            f"[yellow]⚠[/yellow] Schema checkpoint failed ({exc}) — falling back to text."
        )
        result = headless_call(
            session_id=branch.session_id,
            prompt=prompt,
            system_prompt=None,
            json_schema=None,
            timeout=timeout,
        )
        payload = None
        raw_text = result.raw_text

    pause_id = f"pause-{uuid.uuid4().hex[:10]}"
    artifact, script_path, log_path = _write_pause_artifacts(
        project_root=project_root,
        pause_id=pause_id,
        branch=branch,
        payload=payload,
        raw_text=raw_text,
        when=until,
        strategy=strategy,
    )

    try:
        job_id = schedule_at(str(script_path), until, log_path=str(log_path))
    except AtNotAvailableError as exc:
        raise click.ClickException(
            f"Cannot schedule resume : {exc}. Checkpoint saved at "
            f"{artifact.relative_to(project_root)} — you can resume manually."
        ) from exc

    # Persist the at_job_id by re-writing the artifact (can't mutate Path in place).
    _update_pause_artifact_with_job(artifact, job_id)
    sm.record_pause(name, pause_id)

    CONSOLE.print(
        f"[green]✓[/green] Paused branch [bold]{name}[/bold] — "
        f"`at` job [bold]{job_id}[/bold] scheduled for [bold]{until}[/bold]."
    )
    CONSOLE.print(f"  checkpoint: {artifact.relative_to(project_root)}")
    CONSOLE.print(f"  resume script: {script_path}")
    CONSOLE.print(f"  log: {log_path}")
    CONSOLE.print(
        f"[dim]Cancel with : [cyan]atrm {job_id}[/cyan] ; attempts left : "
        f"{MAX_RESUMES - branch.resume_count - 1}[/dim]"
    )


@main.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:
    """Health check : claude CLI, at scheduler, state integrity."""
    project_root: Path = ctx.obj["project_root"]
    issues: list[str] = []

    try:
        v = claude_version()
        CONSOLE.print(f"[green]✓[/green] claude CLI : [bold]{v}[/bold]")
    except ClaudeNotFoundError as exc:
        issues.append(f"claude CLI missing ({exc})")
        CONSOLE.print(f"[red]✗[/red] claude CLI missing : {exc}")
    except ClaudeInvokerError as exc:
        issues.append(f"claude CLI errored ({exc})")
        CONSOLE.print(f"[red]✗[/red] claude CLI errored : {exc}")

    if is_at_available():
        CONSOLE.print("[green]✓[/green] `at` scheduler : present")
    else:
        issues.append("`at` scheduler missing")
        CONSOLE.print(
            "[red]✗[/red] `at` missing — `sudo apt install at` (or equivalent) to enable pause/resume"
        )

    sm = StateManager(project_root)
    try:
        state = sm.load()
        CONSOLE.print(
            f"[green]✓[/green] state : {len(state.branches)} branch(es), current=[bold]{state.current_branch}[/bold]"
        )
    except Exception as exc:  # pragma: no cover - defensive
        issues.append(f"state load failed : {exc}")
        CONSOLE.print(f"[red]✗[/red] state load failed : {exc}")

    if issues:
        raise click.ClickException(f"{len(issues)} issue(s) : {'; '.join(issues)}")


@main.command()
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing slash-command files without prompting.",
)
@click.pass_context
def install(ctx: click.Context, force: bool) -> None:
    """Install Claude Code slash-commands (/fork, /merge, /throw, /tree)."""
    target = _slash_commands_target()
    target.mkdir(parents=True, exist_ok=True)

    if not BUNDLED_SLASH_COMMANDS_DIR.is_dir():
        raise click.ClickException(
            f"bundled slash-commands directory missing : {BUNDLED_SLASH_COMMANDS_DIR} "
            "(packaging issue — please file a bug)"
        )

    copied = 0
    skipped = 0
    for src in BUNDLED_SLASH_COMMANDS_DIR.glob("*.md"):
        dst = target / src.name
        if dst.exists() and not force:
            skipped += 1
            continue
        shutil.copy2(src, dst)
        copied += 1

    CONSOLE.print(f"[green]✓[/green] Installed {copied} slash-command(s) to [bold]{target}[/bold].")
    if skipped:
        CONSOLE.print(f"[dim]{skipped} skipped (already present, use --force to overwrite).[/dim]")


def _slash_commands_target() -> Path:
    return Path.home() / ".claude" / "commands"


@main.command()
@click.pass_context
def tree(ctx: click.Context) -> None:
    """Render the branch tree for this project."""
    project_root: Path = ctx.obj["project_root"]
    sm = StateManager(project_root)
    state = sm.load()

    if not state.branches:
        CONSOLE.print("[dim]No branches yet — this project has an empty tree.[/dim]")
        return

    roots = [b for b in state.branches.values() if b.parent is None]
    if not roots:
        roots = list(state.branches.values())

    rich_tree = Tree(
        f"[bold]{project_root.name or project_root}[/bold]",
        guide_style="dim",
    )
    for root in roots:
        _attach(rich_tree, root.name, state, state.current_branch)

    CONSOLE.print(rich_tree)


def _write_pause_artifacts(
    project_root: Path,
    pause_id: str,
    branch: Branch,
    payload: dict | None,
    raw_text: str | None,
    when: str,
    strategy: CheckpointStrategy,
) -> tuple[Path, Path, Path]:
    """Write the pause JSON + the bash resume script + prepare the log path.

    Returns (artifact, script_path, log_path).
    """
    pauses_dir = project_root / "ctxbranch" / PAUSES_DIR
    pauses_dir.mkdir(parents=True, exist_ok=True)
    artifact = pauses_dir / f"{pause_id}.json"
    artifact.write_text(
        json.dumps(
            {
                "pause_id": pause_id,
                "branch": branch.name,
                "session_id": branch.session_id,
                "payload": payload,
                "raw_text": raw_text,
                "when": when,
                "at_job_id": None,
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    checkpoint_md = strategy.render(branch=branch, payload=payload, raw_text=raw_text)
    script_path = Path(f"/tmp/ctxbranch-resume-{pause_id}.sh")
    log_path = Path(f"/tmp/ctxbranch-resume-{pause_id}.log")

    # Escape single quotes in the checkpoint for safe embedding in the heredoc.
    checkpoint_escaped = checkpoint_md.replace("'", "'\\''")

    script = f"""#!/bin/bash
set -e
cd '{project_root}'
claude --resume {branch.session_id} \\
  --permission-mode auto \\
  --append-system-prompt '{checkpoint_escaped}' \\
  -p 'Resume the work captured in the checkpoint above. Continue autonomously.'
"""
    script_path.write_text(script)
    script_path.chmod(0o755)
    return artifact, script_path, log_path


def _update_pause_artifact_with_job(artifact: Path, job_id: str) -> None:
    data = json.loads(artifact.read_text())
    data["at_job_id"] = job_id
    artifact.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _select_clean_victims(
    state: State,
    clean_thrown: bool,
    older_than_days: int | None,
) -> list[str]:
    from datetime import UTC, datetime

    victims: list[str] = []
    now = datetime.now(UTC)
    for name, branch in state.branches.items():
        if clean_thrown and branch.status == BranchStatus.THROWN:
            victims.append(name)
            continue
        if older_than_days is not None and branch.status == BranchStatus.MERGED:
            if branch.merged_at is None:
                continue
            merged_dt = datetime.fromisoformat(branch.merged_at.replace("Z", "+00:00"))
            age = now - merged_dt
            if age.days >= older_than_days:
                victims.append(name)
    return victims


def _resolve_branch_for_merge(state: State, branch_name: str | None) -> Branch:
    name = branch_name or state.current_branch
    if name not in state.branches:
        raise click.ClickException(f"Branch {name!r} does not exist.")
    return state.branches[name]


def _execute_merge_call(
    branch: Branch,
    prompt: str,
    schema: dict | None,
    timeout: int,
) -> tuple[dict | None, str | None, str | None]:
    """Try structured schema call first, fall back to text on failure.

    Returns (payload, raw_text, fallback_mode).
    """
    if schema is not None:
        try:
            result = headless_call(
                session_id=branch.session_id,
                prompt=prompt,
                system_prompt=None,
                json_schema=schema,
                timeout=timeout,
            )
            return result.parsed, None, None
        except ClaudeInvokerError as exc:
            CONSOLE.print(f"[yellow]⚠[/yellow] Schema mode failed ({exc}) — retrying in text mode.")

    result = headless_call(
        session_id=branch.session_id,
        prompt=prompt,
        system_prompt=None,
        json_schema=None,
        timeout=timeout,
    )
    return None, result.raw_text, "text"


def _write_merge_artifact(
    project_root: Path,
    merge_id: str,
    branch: Branch,
    payload: dict | None,
    raw_text: str | None,
    fallback: str | None,
) -> Path:
    merges_dir = project_root / "ctxbranch" / MERGES_DIR
    merges_dir.mkdir(parents=True, exist_ok=True)
    artifact = merges_dir / f"{merge_id}.json"
    artifact.write_text(
        json.dumps(
            {
                "merge_id": merge_id,
                "branch": branch.name,
                "intent": branch.intent.value if branch.intent else None,
                "parent": branch.parent,
                "payload": payload,
                "raw_text": raw_text,
                "fallback": fallback,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return artifact


def _attach(parent_node: Tree, branch_name: str, state: State, current: str) -> None:
    branch = state.branches[branch_name]
    label_parts = [f"[bold]{branch.name}[/bold]"]
    if branch_name == current:
        label_parts.append("[yellow]● current[/yellow]")
    if branch.intent:
        label_parts.append(f"[dim]<{branch.intent.value}>[/dim]")
    status_mark = _STATUS_MARK.get(branch.status, "")
    label = " ".join(label_parts) + status_mark
    node = parent_node.add(label)
    for child_name in branch.children:
        if child_name in state.branches:
            _attach(node, child_name, state, current)


if __name__ == "__main__":
    main()
