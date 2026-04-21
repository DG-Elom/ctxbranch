# ctxbranch — Design Document

> Git-like branching for Claude Code conversations.
>
> **Author** : Elda (DG-Elom) + Claude Opus 4.7
> **Date** : 2026-04-21
> **Status** : Approved design, pending implementation

---

## 1. Problem statement

Claude Code sessions are linear. When a user triggers a digression, tries a speculative fix, wants to compare two approaches, or hits the context ceiling, they have three bad options:

1. **Continue in the same session** → pollutes reasoning with orthogonal material
2. **`/compact`** → lossy; loses critical intermediate details
3. **`/clear`** → nuclear; loses everything

From analysis of 187 user messages across 8 recent sessions, the most painful patterns are :

| # | Pattern | Frequency | Current workaround |
|---|---|---|---|
| 1 | Recall inter-session — "what were we working on ?" | Medium | `session-summary.sh` hook (linear only) |
| 2 | Debugging spéculatif — same error × N tries | High | Context piles up, no comparison |
| 3 | Digression orthogonale — "also, do X" | High | Pollutes current context |
| 4 | A/B exploration | Low | Serial, one approach thrown away |
| 5 | Pre-compact — task unfinished, context saturated | High (63% of usage >150k tokens) | `/compact` lossy |

All five reduce to one primitive : **fork + merge-back with declared intent**.

---

## 2. Goals & non-goals

### Goals (G)
- **G1** — Let user fork a Claude Code session mid-conversation with a declared intent
- **G2** — Provide intent-appropriate merge-back strategies (text, structured, diff+verdict)
- **G3** — Navigable tree of branches per project
- **G4** — Autonomous pause/resume across quota resets (user-specific requirement)
- **G5** — Zero intrusion on existing `~/.claude/` files — read-only use of session `.jsonl`

### Non-goals (NG)
- **NG1** — Own storage engine or conversation format (lean on Claude Code's `--fork-session`)
- **NG2** — Real-time conversation synchronization across machines
- **NG3** — Multiple users sharing a branch tree
- **NG4** — GUI / web UI (CLI + slash-commands only)
- **NG5** — CoW storage optimization (YAGNI until sessions exceed 1 GB total)

---

## 3. Architecture

### Components

```
┌────────────────────────────────────┐
│   Claude Code (session active)     │
│                                    │
│   /fork, /merge, /throw, /tree  ───┼─┐
│                                    │ │
└────────────────────────────────────┘ │
                                       │ shell out
┌────────────────────────────────────┐ │
│   ctxbranch CLI (Python)           │◄┘
│                                    │
│   Commands :                       │
│     fork / merge / throw / tree    │
│     pause --until / resume         │
│     clean / doctor / install       │
│                                    │
│   ┌──────────────────────────────┐ │
│   │ ctxbranch.core (lib)         │ │
│   │  - state manager (JSON)      │ │
│   │  - claude CLI invoker        │ │
│   │  - merge strategies          │ │
│   │  - cron/at scheduler         │ │
│   └──────────────────────────────┘ │
└──────┬─────────────────────────────┘
       │ reads/writes
       ▼
┌────────────────────────────────────┐
│  ~/.claude/projects/<cwd>/         │
│    ctxbranch/                      │
│      state.json      (tree)        │
│      branches/<name>.json (meta)   │
│      merges/<id>.json (summaries)  │
│      errors.log                    │
└────────────────────────────────────┘
```

**Core principle** : ctxbranch never mutates Claude Code's `.jsonl` files. Every fork uses `claude --resume <uuid> --fork-session` (existing CLI primitive). State lives alongside, in a sibling directory.

### Data model

**state.json** (per-project root) :
```json
{
  "version": 1,
  "current_branch": "main",
  "branches": {
    "main": {
      "session_id": "d32d4bfe-...",
      "parent": null,
      "intent": null,
      "created_at": "2026-04-21T22:00:00Z",
      "status": "active",
      "children": ["digression-jwt-1776808900"]
    },
    "digression-jwt-1776808900": {
      "session_id": "a8f12b6e-...",
      "parent": "main",
      "intent": "digression",
      "description": "check auth flow jwt refresh",
      "created_at": "2026-04-21T22:15:00Z",
      "status": "merged",
      "merged_at": "2026-04-21T22:38:00Z",
      "merge_id": "merge-abc123",
      "children": []
    }
  }
}
```

**branches/\<name\>.json** : extended metadata (free-form notes, tags, rebased_from).
**merges/\<id\>.json** : structured merge payload, re-injectable.

### Intent taxonomy

| Intent | Use case | Merge strategy |
|---|---|---|
| `digression` | Orthogonal side-request | Short text summary (50-500 words) |
| `hypothesis` | Speculative debug attempt | Verdict + diff summary + findings |
| `ab` | Compare two approaches | Two structured summaries + comparison table |
| `checkpoint` | Pre-compact snapshot | Full structured state (goal/completed/in-progress/decisions/artifacts/next) |

---

## 4. Commands

### Slash commands (mid-session)

| Command | Purpose |
|---|---|
| `/fork <intent> "<desc>"` | Fork the current session with declared intent |
| `/merge [--into <parent>] [--mode <auto\|text\|structured\|artifacts>]` | Merge child back into parent |
| `/throw [--archive]` | Discard branch |
| `/tree` | Render branch tree inline |

### CLI (`ctxbranch`)

| Command | Purpose |
|---|---|
| `ctxbranch tree [--all-projects]` | Render tree in shell |
| `ctxbranch resume <branch>` | Relaunch Claude on a branch with pending merges injected |
| `ctxbranch fork <branch> <intent> "<desc>"` | Shell equivalent of /fork |
| `ctxbranch pause --until <HH:MM\|+Nh>` | Auto-checkpoint + schedule `at` job to resume |
| `ctxbranch clean [--thrown] [--older-than <days>]` | GC |
| `ctxbranch doctor` | Health check : claude CLI version, state integrity, scheduled jobs |
| `ctxbranch install` | Install slash-commands to `~/.claude/commands/` |

---

## 5. Merge-back strategies

### 5.1 `digression`
- **Prompt** : "Summarize this digression in 3-5 sentences for the parent session."
- **Schema** : `{summary: string (50-500 words)}`
- **Injection** : wrapped in `<ctxbranch:merge>` block as user message

### 5.2 `hypothesis`
- **Prompt** : "Produce verdict, diff summary, key findings, next steps."
- **Schema** : `{verdict: 'worked'|'partial'|'failed', diff_summary: [{file, change}], key_findings: string[], next_steps: string[]}`
- **Injection** : rendered markdown block

### 5.3 `ab`
- **Per branch** : `{approach_name, summary, pros[], cons[], metrics: {loc, complexity, files_touched}}`
- **Injection** : side-by-side comparison table

### 5.4 `checkpoint`
- **Schema** : `{goal, completed[], in_progress, decisions[], artifacts[], next_steps[], open_questions[]}`
- **Usage** : payload for `ctxbranch resume` and `ctxbranch pause`

All strategies are implemented as headless Claude calls :
```
claude --resume <branch-session> --print --output-format json \
       --append-system-prompt <strategy-prompt> \
       --json-schema <intent-schema>
```

---

## 6. Autonomous pause/resume

### Flow `ctxbranch pause --until 22:59`

1. **Auto-checkpoint** : invoke `checkpoint` strategy → `merges/<pause-id>.json`
2. **Generate resume script** (`/tmp/ctxbranch-resume-<id>.sh`) :
   ```bash
   #!/bin/bash
   cd "{cwd}"
   claude --resume "{branch-session}" \
          --permission-mode auto \
          -p "$(cat {resume-prompt})" \
          --append-system-prompt "$(cat {checkpoint-md})"
   ```
3. **Schedule via `at`** (one-shot) :
   ```bash
   echo "bash /tmp/ctxbranch-resume-<id>.sh >> /tmp/ctxbranch-resume-<id>.log 2>&1" | at 22:59
   ```
4. **Announce** what to expect + how to cancel (`atrm <job>`)
5. **Clean exit**

### Safeguards

- **Relaunch limit** : `state.resume_count++`. After 3 unsuccessful resumes on same branch, stop and notify user (`notify-send` / email if configured).
- **Idempotency** : if branch advanced manually since pause, abort rather than overwrite.
- **Partial failure** : checkpoint is produced *before* scheduling, so a failed schedule still leaves a recoverable state.

### Known limits (honesty)

- Machine must be powered on at reset time
- No ground-truth quota detection — relies on user-provided reset time
- Anthropic quota format changes would break the assumption

---

## 7. Error handling

| Scenario | Behavior |
|---|---|
| `claude` CLI missing/incompatible | `doctor` detects, bail out with install hint |
| `state.json` corrupt | Backup to `state.json.bak-<ts>`, attempt rebuild from scanning `.jsonl`, else read-only mode |
| Fork fails (UUID collision, perms) | Rollback state entry, log to `errors.log`, actionable message |
| Merge-back fails (timeout, quota, schema) | Retry × 2 with backoff → fallback to text mode → last resort `--manual` via $EDITOR |
| Cron/`at` job missing at resume | `doctor` detects and re-schedules |
| Quota hits during `pause` setup | Checkpoint happens before schedule, guaranteed recoverable |

---

## 8. Testing

### Unit (pytest)
- `core.state_manager` : load/save/mutate/migrate
- `core.claude_invoker` : mock subprocess, validate flags
- `strategies.*` : prompt fixtures, schema validation

### Integration
- Fork-then-merge E2E with synthetic `.jsonl` fixtures under `tests/fixtures/`
- Pause/resume with mocked `at`
- CLI parsing & dispatch

### Contract tests
- Parse `claude --help`, alert on breaking flag changes
- Version whitelist in `ctxbranch/compat.py`

### Coverage target
80%+ on `core` and `strategies`. `cli` less critical.

---

## 9. Packaging & distribution

- **Python 3.10+**
- **`pyproject.toml`**, build via `uv build`
- **Entry point** : `ctxbranch = ctxbranch.cli:main`
- **Dependencies** : `click`, `pydantic`, `rich`, `python-crontab` (for `at`/cron)
- **Distribution** : PyPI + GitHub releases. `pipx install ctxbranch` recommended.
- **Slash-commands** : markdown files in `slash-commands/`, installed by `ctxbranch install` to `~/.claude/commands/`
- **Compat** : `claude --version` check, whitelist in `ctxbranch/compat.py`

---

## 10. Out-of-scope / future work

- **GUI / web tree viewer**
- **Multi-machine state sync** (obsidian vault sync could approximate)
- **Auto-branch detection** (LLM heuristic that proposes fork when digression detected)
- **Integration with `git worktree`** (each branch → worktree with its own cwd)
- **Team / shared branches**
- **Token-precise quota detection** (when Anthropic exposes it)

---

## 11. Implementation order (plan to follow)

1. Scaffolding : repo structure, `pyproject.toml`, CI, pre-commit
2. `core.state_manager` + tests
3. `core.claude_invoker` + tests (mocked)
4. `cli.fork` + `cli.tree` (happiest path)
5. `strategies.digression` + `cli.merge` (first full loop)
6. Remaining strategies (hypothesis, ab, checkpoint)
7. `cli.pause` + `cli.resume` (at scheduling)
8. `cli.doctor`, `cli.clean`, `cli.install`
9. Slash-commands in `slash-commands/`
10. `doctor` hardening, error paths, logs
11. README + usage examples
12. PyPI publish (v0.1.0)
