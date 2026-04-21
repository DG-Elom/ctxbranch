# Implementation Plan — ctxbranch v0.1.0

TDD approach. Each step ships a commit when tests pass.

## Step 0 : Scaffolding (15 min)
- [ ] `pyproject.toml` : Python 3.10+, deps (`click`, `pydantic>=2`, `rich`, `pytest`, `pytest-mock`)
- [ ] `src/ctxbranch/` layout with `__init__.py`
- [ ] `tests/` with `conftest.py` (temp dir fixture)
- [ ] `.github/workflows/ci.yml` : pytest + ruff on push
- [ ] `ruff.toml` + `pytest.ini` (or `[tool.*]` in pyproject)
- [ ] Pre-commit smoke : `pip install -e . && pytest`
- **Commit** : "chore: project scaffold with pyproject + CI"

## Step 1 : `core.state_manager` (30 min) — TDD
Tests first :
- [ ] `test_load_missing_file_returns_empty_state`
- [ ] `test_create_and_save_initial_state`
- [ ] `test_add_branch_updates_parent_children`
- [ ] `test_merge_branch_updates_status_and_merge_id`
- [ ] `test_throw_branch_sets_status_thrown`
- [ ] `test_load_corrupt_file_backs_up_and_returns_empty`
- [ ] `test_migration_from_version_0_to_1` (skipped for now, placeholder)

Implementation :
- [ ] `State` pydantic model : `version, current_branch, branches: dict[str, Branch]`
- [ ] `Branch` pydantic model : full fields per design
- [ ] `StateManager.load(project_root) -> State`
- [ ] `StateManager.save(state, project_root)`
- [ ] `StateManager.add_branch(name, session_id, parent, intent, desc)`
- [ ] `StateManager.merge_branch(name, merge_id)`
- [ ] `StateManager.throw_branch(name)`
- [ ] Path resolution : `<project_root>/ctxbranch/state.json`
- **Commit** : "feat(core): state manager with pydantic models + tests"

## Step 2 : `core.claude_invoker` (20 min) — TDD
Tests first (with `pytest-mock`) :
- [ ] `test_fork_session_passes_correct_flags`
- [ ] `test_headless_call_captures_json_output`
- [ ] `test_version_detection`
- [ ] `test_raises_on_nonzero_exit`
- [ ] `test_timeout_handling`

Implementation :
- [ ] `ClaudeInvoker.fork(parent_session_id, new_session_id, name) -> subprocess.Popen` (interactive)
- [ ] `ClaudeInvoker.headless(session_id, prompt, schema=None, timeout=120) -> dict | str`
- [ ] `ClaudeInvoker.version() -> str`
- [ ] Builds commands with proper shell escaping
- **Commit** : "feat(core): claude CLI invoker with mock-driven tests"

## Step 3 : `strategies.base` + `strategies.digression` (20 min)
Tests first :
- [ ] `test_digression_prompt_contains_description`
- [ ] `test_digression_schema_accepts_valid_summary`
- [ ] `test_digression_schema_rejects_too_short`
- [ ] `test_render_markdown_injection_has_merge_tag`

Implementation :
- [ ] `Strategy` ABC : `prompt(branch_meta) -> str`, `schema -> dict`, `render(payload) -> str`
- [ ] `DigressionStrategy` concrete
- [ ] `registry.get(intent) -> Strategy`
- **Commit** : "feat(strategies): base abc + digression strategy"

## Step 4 : `cli.fork` + `cli.tree` (30 min) — first usable loop
Tests first :
- [ ] `test_fork_cli_creates_branch_in_state` (end-to-end with mocked invoker)
- [ ] `test_tree_renders_current_branch_marker`
- [ ] `test_fork_validates_intent`

Implementation :
- [ ] `click` command group `ctxbranch`
- [ ] `ctxbranch fork <branch> <intent> "<desc>"`
- [ ] `ctxbranch tree`
- [ ] `rich` Tree rendering
- **Commit** : "feat(cli): fork and tree commands"

## Step 5 : `cli.merge` with digression (40 min) — first full loop
Tests first :
- [ ] `test_merge_produces_artifact_in_merges_dir`
- [ ] `test_merge_updates_state_to_merged`
- [ ] `test_merge_fallback_to_text_on_schema_fail`
- [ ] `test_merge_idempotent_on_already_merged`

Implementation :
- [ ] `ctxbranch merge [branch] [--mode]`
- [ ] Calls strategy → headless claude → writes `merges/<id>.json`
- [ ] Retry + fallback logic
- **Commit** : "feat(cli): merge command with digression strategy end-to-end"

## Step 6 : Remaining strategies (60 min)
- [ ] `HypothesisStrategy` + tests
- [ ] `AbStrategy` + tests (handles two branches)
- [ ] `CheckpointStrategy` + tests (largest schema)
- **Commit** : "feat(strategies): hypothesis, ab, checkpoint strategies"

## Step 7 : `cli.throw` + `cli.clean` + `cli.resume` (30 min)
- [ ] `ctxbranch throw [--archive]`
- [ ] `ctxbranch clean [--thrown] [--older-than]`
- [ ] `ctxbranch resume <branch>` : launches `claude --resume` with pending merge injection
- **Commit** : "feat(cli): throw, clean, resume commands"

## Step 8 : `cli.pause` + `at` scheduling (40 min)
Tests :
- [ ] `test_pause_creates_checkpoint_before_scheduling`
- [ ] `test_pause_writes_resume_script`
- [ ] `test_pause_increments_resume_count`
- [ ] `test_pause_aborts_if_at_not_installed`

Implementation :
- [ ] `ctxbranch pause --until <time>`
- [ ] Writes `/tmp/ctxbranch-resume-<id>.sh`
- [ ] Invokes `at` via subprocess
- [ ] Writes `state.resume_count++`
- **Commit** : "feat(cli): autonomous pause/resume across quota windows"

## Step 9 : `cli.doctor` + `cli.install` (30 min)
- [ ] `ctxbranch doctor` : checks claude CLI, state integrity, scheduled jobs
- [ ] `ctxbranch install` : copies slash-commands to `~/.claude/commands/`
- **Commit** : "feat(cli): doctor and install commands"

## Step 10 : Slash-commands (20 min)
- [ ] `slash-commands/fork.md`
- [ ] `slash-commands/merge.md`
- [ ] `slash-commands/throw.md`
- [ ] `slash-commands/tree.md`
Each shells out to `ctxbranch` binary.
- **Commit** : "feat(commands): Claude Code slash-commands"

## Step 11 : Hardening + docs (30 min)
- [ ] Error paths : corrupt state recovery, version mismatch, quota-hit-during-merge fallback
- [ ] `docs/usage.md` with real-world examples
- [ ] README polishing with GIF/asciicast link placeholder
- **Commit** : "chore: hardening + usage docs"

## Step 12 : Release v0.1.0 (15 min)
- [ ] Tag `v0.1.0`
- [ ] GitHub release with changelog
- [ ] (Optional — skip if time/quota low) PyPI publish via `uv publish`
- **Commit** : "release: v0.1.0"

---

## Budget estimé

- Total : ~6 heures de travail ininterrompu
- Commits : ~12
- LOC : ~1500-2000 (src + tests)
- Tests : ~50-80

## Règles d'exécution

- **TDD strict** : test d'abord, rouge, code minimal, vert, refactor
- **Commit dès que vert** — pas d'accumulation
- **Pas de subagent** pour l'impl (trop cher, ton quota a tapé 94% là-dessus)
- **`scratchpad/resume-state.md`** mis à jour après chaque commit (pour reprise de session)
- **Si quota menace** : `pause --until <reset>` (ou manuel `at` si le tool pas encore prêt)

## Risques identifiés

| Risque | Mitigation |
|---|---|
| Claude CLI change flags entre versions | Version whitelist + contract tests |
| `at` pas installé (certains linux minimaux) | Fallback sur systemd-user timer ; sinon erreur explicite |
| Headless claude produit JSON non-conforme | Retry + fallback text mode |
| User modifie state.json à la main | Validate on load, backup + rebuild si corrupt |
| Quota du user tape pendant un merge | Merge idempotent + reprise manuelle via `ctxbranch merge <branch> --retry` |
