---
description: Checkpoint the current branch and schedule an autonomous resume.
argument-hint: <time-expression>
---

# /pause

Produce a structured checkpoint of the current branch and schedule `claude --resume`
to run at the given time via the `at` scheduler.

## Usage

```
/pause 22:59
/pause now + 4 hours
```

## What it does

1. Runs the CheckpointStrategy headless against the current branch
2. Writes `ctxbranch/pauses/<id>.json` + `/tmp/ctxbranch-resume-<id>.sh`
3. Schedules the script via `at <time>`
4. Bumps `resume_count` on the branch (capped at 3)

Cancel with `atrm <job-id>` (printed after scheduling).

## Under the hood

!`ctxbranch pause --until "$1"`
