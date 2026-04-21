"""Command-line entry point for ctxbranch."""

from __future__ import annotations

import uuid
from pathlib import Path

import click
from rich.console import Console
from rich.tree import Tree

from ctxbranch import __version__
from ctxbranch.core.claude_invoker import build_fork_command
from ctxbranch.core.state_manager import (
    BranchStatus,
    Intent,
    StateManager,
)

CONSOLE = Console()

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
        # Defensive : no root found (shouldn't happen), render flat
        roots = list(state.branches.values())

    rich_tree = Tree(
        f"[bold]{project_root.name or project_root}[/bold]",
        guide_style="dim",
    )
    for root in roots:
        _attach(rich_tree, root.name, state, state.current_branch)

    CONSOLE.print(rich_tree)


def _attach(parent_node: Tree, branch_name: str, state, current: str) -> None:
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
