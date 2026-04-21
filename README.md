# ctxbranch

**Git-like branching for Claude Code conversations.**

Fork mid-session, explore hypotheses without polluting main context, compare A/B approaches, checkpoint before quota resets — then merge a structured summary back into the parent.

## Why

Claude Code sessions are linear. When you want to :

- try a speculative fix without losing the original path
- explore a digression that doesn't belong in the current task
- compare two design approaches side-by-side
- checkpoint before the context window saturates
- pause until a quota reset and auto-resume

...your only current options are `/compact` (lossy) or `/clear` (nuclear). `ctxbranch` gives you a third way : **fork the conversation with a declared intent, work in isolation, merge back a structured summary**.

## Status

**v0.1.0 — initial alpha release.** 97 tests, ruff-clean. Treat as a technology preview ; the CLI surface may still move between minor versions.

See :
- [`docs/2026-04-21-ctxbranch-design.md`](docs/2026-04-21-ctxbranch-design.md) — design
- [`docs/2026-04-21-implementation-plan.md`](docs/2026-04-21-implementation-plan.md) — TDD plan followed during build
- [`docs/usage.md`](docs/usage.md) — day-to-day usage

## Install

```bash
pipx install ctxbranch           # or: uv tool install ctxbranch
ctxbranch install                # copy slash-commands to ~/.claude/commands/
ctxbranch doctor                 # verify setup
```

Prerequisites :
- `claude` CLI (Claude Code) on PATH
- `at` for pause/resume (`sudo apt install at` on Debian/Ubuntu)

## Usage

From inside Claude Code :

```
/fork digression "check refresh token TTL"
/fork hypothesis "try switching to asymmetric JWT"
/fork ab "approach A: middleware | approach B: decorator"
/fork checkpoint "pre-compact"
/merge
/tree
/pause 22:59
```

From the shell :

```bash
ctxbranch init                    # bootstrap the project's tree
ctxbranch tree
ctxbranch fork d-1 digression "check TTL"
ctxbranch merge d-1
ctxbranch resume main
ctxbranch pause --until 22:59     # checkpoint + schedule auto-resume via `at`
ctxbranch clean --thrown
```

Full walkthrough : [`docs/usage.md`](docs/usage.md).

## Design

Full design doc : [`docs/2026-04-21-ctxbranch-design.md`](docs/2026-04-21-ctxbranch-design.md)

Key ideas :

- Leans on Claude Code's existing `claude --resume <uuid> --fork-session` primitive (no new storage engine)
- Intent-driven merge strategies : `digression`, `hypothesis`, `ab`, `checkpoint`
- Structured summaries produced by headless Claude calls with JSON schemas
- Autonomous pause/resume via `at` scheduling for quota windows

## License

MIT
