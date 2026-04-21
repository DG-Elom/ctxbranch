# Usage

## Install

```bash
pipx install ctxbranch
ctxbranch install       # copies slash-commands to ~/.claude/commands/
ctxbranch doctor        # sanity-check the install
```

Prerequisites : `claude` CLI (Claude Code), and `at` for pause/resume (Debian : `sudo apt install at`).

## Quick start

```bash
# inside a project directory — once per project
ctxbranch init                        # or --session-id <uuid>

# list the tree
ctxbranch tree

# fork from the current branch
ctxbranch fork digression-jwt digression "check refresh TTL"

# ... work in the forked session (run the emitted `claude --resume` command) ...

# back in the shell : merge the branch
ctxbranch merge digression-jwt

# discard a branch
ctxbranch throw hypothesis-cache

# clean up thrown / old branches
ctxbranch clean --thrown
ctxbranch clean --older-than 30       # remove merged branches >30 days old

# schedule an autonomous resume (e.g. across a quota reset)
ctxbranch pause --until 22:59
```

## Inside Claude Code

Once `ctxbranch install` has been run, the following slash-commands are available :

| Command | Effect |
|---|---|
| `/fork <intent> "<desc>"` | Create a new branch with declared intent |
| `/merge [branch]` | Merge a branch back with intent-driven summary |
| `/throw <branch>` | Discard a branch |
| `/tree` | Render the branch tree |
| `/pause <time>` | Checkpoint and schedule an auto-resume |

### Intents

| Intent | Purpose | Merge payload |
|---|---|---|
| `digression` | Orthogonal side-request | Short text summary (50-500 words) |
| `hypothesis` | Speculative fix attempt | Verdict + diff + findings + next steps |
| `ab` | One side of an A/B | Approach name + summary + pros/cons + metrics |
| `checkpoint` | Pre-compact / pre-pause snapshot | Full structured state |

## Data locations

| Path | Purpose |
|---|---|
| `<project>/ctxbranch/state.json` | Branch tree for this project |
| `<project>/ctxbranch/branches/<name>.json` | Per-branch extended metadata (future) |
| `<project>/ctxbranch/merges/<id>.json` | Merge payloads (structured or text) |
| `<project>/ctxbranch/pauses/<id>.json` | Pause checkpoints + `at` job ids |
| `/tmp/ctxbranch-resume-<id>.sh` | Scheduled resume scripts |
| `/tmp/ctxbranch-resume-<id>.log` | Resume output logs |

ctxbranch **never** modifies Claude Code's own `~/.claude/` session files.

## Typical workflows

### 1. Quick digression mid-task

Inside Claude :
```
/fork digression "wait, quickly audit the error message format"
```
Claude emits a `claude --resume ... --fork-session ...` command. Run it in a new terminal, work the digression, exit, then :
```
ctxbranch merge
```
The parent session (still running or freshly resumed) gets a concise briefing.

### 2. Speculative debug attempt

```
/fork hypothesis "try patching the refresh token flow"
# ... apply a potential fix, run tests ...
/merge           # produces verdict + diff + findings
/throw           # if it didn't work, discard instead of merging
```

### 3. Pause across a quota reset

Session about to hit quota, task unfinished :
```
/pause 22:59 UTC
```
Bash script is scheduled via `at`. When it fires, `claude --resume <main-session>` runs with the checkpoint injected as system prompt and `--permission-mode auto` for continuation.

Cancel with `atrm <job-id>` (printed by `pause`).

## Troubleshooting

```bash
ctxbranch doctor         # check claude, at, state
```

Corrupted state.json → auto-backup to `ctxbranch/state.json.bak-<ts>`.

`at` not installed → `sudo apt install at` (Debian/Ubuntu) or `brew install at` (macOS).
