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

🚧 **Pre-alpha — under active development.** See `docs/2026-04-21-ctxbranch-design.md` for the full design.

## Install (when released)

```bash
pipx install ctxbranch
ctxbranch install  # install slash-commands to ~/.claude/commands/
ctxbranch doctor   # verify setup
```

## Usage (preview)

From inside Claude Code :

```
/fork digression "check refresh token TTL"
/fork hypothesis "try switching to asymmetric JWT"
/fork ab "approach A: middleware | approach B: decorator"
/fork checkpoint "pre-compact"
/merge
/tree
```

From the shell :

```bash
ctxbranch tree
ctxbranch resume main
ctxbranch pause --until 22:59
ctxbranch clean --thrown
```

## Design

Full design doc : [`docs/2026-04-21-ctxbranch-design.md`](docs/2026-04-21-ctxbranch-design.md)

Key ideas :

- Leans on Claude Code's existing `claude --resume <uuid> --fork-session` primitive (no new storage engine)
- Intent-driven merge strategies : `digression`, `hypothesis`, `ab`, `checkpoint`
- Structured summaries produced by headless Claude calls with JSON schemas
- Autonomous pause/resume via `at` scheduling for quota windows

## License

MIT
