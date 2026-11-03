# Development guidelines

Apply the minimal-change approach described by [Ponytail](https://github.com/dietrichgebert/ponytail): read the real workflow, reuse existing code, and add only what the task needs.

- Tie each new module, dependency, option, or abstraction to an active research checkpoint or demonstrated failure. Avoid speculative features.
- Search callers, tests, and configuration before editing or declaring code unused. Prefer the standard library and existing helpers.
- Keep notebooks as configuration and launchers. Put reusable experiment logic in Python modules; test those functions directly rather than extracting notebook source.
- Preserve observations, inference accounting, raw traces, error records, and existing results. Fail visibly and retain the underlying exit status.
- Keep experiment settings fixed within a pilot. Never overwrite an existing manifest with different settings or mix prompt versions in a result directory.
- Version changes to model-facing prompts, memory rendering, and experimental behavior. Retain baseline options only while a documented comparison needs them.
- Keep scoring, diagnostic state, hidden history, and scripted solutions out of bounded-agent inputs. Stored plans share the declared memory allowance.
- Test meaningful behavior and failure cases. Avoid tests that only repeat implementation details, and do not weaken checks to obtain passing results.
- Support performance claims with measured tokens, generation time, and end-to-end time. Profile the expensive path before optimizing Python bookkeeping.
- Use `.venv/bin/python` for project commands. Run relevant checks after code changes; the full suite is `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q`.
- Use the existing isolated checkout; create a Git worktree only if explicitly requested.
- In reviews, give concrete evidence, the smallest fix, and what remains unverified. Passing tests or fewer lines alone do not prove research validity or efficiency.
