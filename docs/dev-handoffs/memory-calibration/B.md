# Role B — actor policy

Status: READY

Contract: `memory-development-contract-v1`. Role B has stopped editing its files.

## Files and behavior

- `game_memory/actor.py`: explicit v30 selection, recovery-aware shared prose/JSON
  gameplay policy, equivalent full-history diagnostic instructions, and bypass
  of inspection-cache maintenance and previous-action storage on v30. Legal
  rereads and repeated actions remain available. Older prompt behavior and the
  v1 default are preserved.
- `tests/test_actor.py`: new boundary tests for repeats/rereads, format-neutral
  instructions, diagnostic context labels, current-turn review/repair evidence,
  prior-turn isolation, optional articles, failed repairs without substitution,
  model-approved meal preparation, metadata, and propagating inference errors.
- `docs/actor-policy.md`: explicit selection, evidence boundary, inference calls,
  metadata, and fake-test limitations documented.
- This role-owned handoff note.

## Checks

Exact commands run:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_actor.py
git diff --check -- game_memory/actor.py tests/test_actor.py docs/actor-policy.md
```

Final result: **85 passed in 0.18s**, exit 0; no skips or failures.
The earlier focused iteration passed 81 tests before four further cases were
added. Diff check passed, exit 0. Full-suite integration is reserved for role D
once A/B/C are ready; it was not run here.

## Compliance and integration

Confirmed v30 availability before editing. Identities are `s2-action-v30` and
`full-history-v30`; explicit opt-in only. Public component interfaces unchanged.
V29 review/repair behavior is preserved, with only context-label substitutions
for v30, retaining `qwen_format_neutral_prepare_review_v1` and
`qwen_format_neutral_unavailable_review_v1`. Optional-article validation retains
`optional_article_exact_match_v1`. Purposes remain `action`, `action_review`,
`action_repair`; no new logger events or action substitutions were introduced.
Reviews may occur on either primary or repaired prepare-meal proposals, as in
v29. At most one repair occurs.

No blocking dependencies or contract mismatches found. The CLI imports
`PROMPT_VERSIONS`, so v30 becomes an available explicit choice without editing
role D's files. D should run combined integration checks and select v30
explicitly in subsequent preflight/calibration configurations. Concurrent edits
outside role B ownership were left untouched.

## Remaining uncertainty and exclusions

Fake models verify wiring, boundaries, error propagation, and legal-action
availability; they cannot establish Qwen's adherence, recovery quality, or actual
gameplay success. Full-history capability and useful bounded-memory behavior
remain for separately authorized T7 calibration.

No GPU job, real-Qwen inference, model download, real-model tuning, or old-artifact
modification occurred. No other role's files or handoff notes were edited. No
branches/worktrees, staging, or commits were created.
