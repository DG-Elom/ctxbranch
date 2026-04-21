---
description: Discard a branch — mark it thrown and switch back to its parent.
argument-hint: <branch-name> [--archive]
---

# /throw

Throw away the work in a branch without merging. The entry stays in `state.json`
for audit (unless `ctxbranch clean --thrown` is run later), but the branch is
flagged as thrown and the current branch switches back to its parent.

## Usage

```
/throw hypothesis-cache
/throw hypothesis-cache --archive
```

## Under the hood

!`ctxbranch throw $1 ${2}`
