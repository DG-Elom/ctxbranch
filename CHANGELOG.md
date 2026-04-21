# Changelog

All notable changes to this project are documented here.
Format inspired by [Keep a Changelog](https://keepachangelog.com) ; project uses semver.

## [Unreleased]

## [0.1.0] — 2026-04-21

### Added
- `ctxbranch init` — bootstrap a project with a `main` branch
- `ctxbranch fork <name> <intent> <description>` — fork current session
- `ctxbranch merge [branch]` — merge a branch back into its parent with an intent-driven summary
- `ctxbranch throw <branch>` — discard a branch
- `ctxbranch tree` — render the branch tree
- `ctxbranch resume <branch>` — emit `claude --resume` for a branch
- `ctxbranch clean` — GC thrown / old-merged branches
- `ctxbranch pause --until <time>` — checkpoint and schedule auto-resume via `at`
- `ctxbranch doctor` — health check
- `ctxbranch install` — deploy bundled slash-commands to `~/.claude/commands/`
- Strategies : `digression`, `hypothesis`, `ab`, `checkpoint`
- Slash-commands bundled : `/fork`, `/merge`, `/throw`, `/tree`, `/pause`
