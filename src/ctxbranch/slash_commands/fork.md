---
description: Fork the current conversation into a new branch with a declared intent.
argument-hint: <intent> "<description>"
---

# /fork

Create a new branch of the current Claude Code session with a declared intent.
You continue in a fresh session that diverges from the current one ; the current
session stays untouched and can be resumed later.

## Usage

```
/fork digression "check refresh token TTL"
/fork hypothesis "try switching to JWT asymmetric"
/fork ab "approach A: middleware"
/fork checkpoint "pre-compact"
```

## What it does

1. Adds a new entry to `ctxbranch/state.json` with a generated UUID
2. Points the new entry to the current branch as its parent
3. Emits the exact `claude --resume ... --fork-session ...` command to start the fork

Run the emitted command in a new terminal (or tmux pane) to start working in the
branch. Use `/tree` to see where you are.

## Under the hood

This command shells out to :
```
ctxbranch fork <auto-name> $1 "$2"
```

Arguments :
- `$1` = intent (digression | hypothesis | ab | checkpoint)
- `$2` = description (quoted)

The branch name is auto-generated from the intent + timestamp.

!`ctxbranch fork "${1:-digression}-$(date +%s)" "$1" "$2"`
