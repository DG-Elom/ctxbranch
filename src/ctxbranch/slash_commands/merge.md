---
description: Merge the current branch back into its parent with an intent-driven summary.
argument-hint: [branch-name]
---

# /merge

Merge a branch back into its parent using the strategy matching the branch's intent :

- `digression` → short text summary wrapped in `<ctxbranch:merge>` block
- `hypothesis` → verdict + diff summary + findings + next steps
- `ab` → structured summary for one side of an A/B comparison
- `checkpoint` → full pre-compact snapshot (goal / completed / in_progress / decisions / artifacts / next / questions)

## Usage

```
/merge
/merge d-jwt-1776808900
```

Without arguments, merges the current branch.

## Under the hood

Runs a headless Claude call against the branch session with a strategy-specific
prompt and JSON schema ; persists the payload to `ctxbranch/merges/<merge-id>.json` ;
marks the branch `merged` in state.json and flips the current branch back to the
parent.

!`ctxbranch merge $1`
