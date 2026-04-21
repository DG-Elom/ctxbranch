"""Command-line entry point for ctxbranch."""

import click

from ctxbranch import __version__


@click.group()
@click.version_option(__version__, prog_name="ctxbranch")
def main() -> None:
    """Git-like branching for Claude Code conversations."""


if __name__ == "__main__":
    main()
