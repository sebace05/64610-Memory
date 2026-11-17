# 64610-Memory

CookingWorld with a Qwen actor and three memory conditions: full public history,
model-written prose, and model-written structured JSON. The active workflow is the
[v31-preserving minimal core](docs/minimal-core.md). New real inference requires
separate authorization; documented real-model commands are prepared only.

The canonical gameplay command is:

```sh
.venv/bin/python -m game_memory.run_episode --help
```

Use `--strategy full_history`, `prose`, or `structured`; v31 is the only actor and
the default for real and fixture runs. Each invocation enforces an immutable
manifest through `prepare_pilot`. `--prepare-only` validates without weights or
gameplay. The guide gives exact future settings, fresh condition directories, and
startup stdout/stderr/exit-status capture requirements. Linux/A10 is the current
known execution target.

Prose/structured stored memory counts its entire rendered text against the memory
allowance. Full history retains actual public records without a writer and is
exempt from that allowance. The complete model-context limit, generated-output
caps, game action budget, and cookbook-reread cost are separate constraints.
Memory is text supplied to the model, not weight training. Comparing generated
formats includes both writing and subsequent use.

Read-only reporting remains separate:

```sh
.venv/bin/python -m game_memory.summarize_diagnostics PATH_TO_CONDITION
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
```

Reports include per-turn behavior, errors, memory decisions and inference usage.
Fixtures are excluded by default and never establish Qwen capability. Optional
model-adapter tests skip when their already-installed dependencies are absent.
The unchanged environment requires compatible Java; this cleanup makes no runtime
or dependency changes.

`game_memory/` contains the actor, environment/contracts, model backend, memory
writers/archive, runner, gameplay CLI, manifest helper, report and test fixtures.
There is no cloud launcher or separate pilot/inspection CLI.

Previous guides, notebooks, evaluations and diagnostic workflows are historical
and require the archived source. Their commands are not current instructions.
The exact dirty starting source and all retired files are verified in
[the restoration archive](artifacts/minimal-core-cleanup-v1/attempt-20261116-232112/source-before.zip)
(SHA-256 `e7bb7b42ad4b29a41e446ef29403cc16070cbe78639641112cd151a5e9d03d93`).
Existing artifacts, manifests, traces, failed gates and handoffs remain untouched.
The old [history-window checkpoint](docs/history-window-checkpoint.md) retains its
recorded failed readiness gate; its Phase B is not executed by this cleanup.

Experimental opt-in [legal-choice-v1](docs/legal-choice-v1.md) scores single-token
labels over the complete public legal-action set in full-history mode. V31 remains
the default; real execution requires separate authorization.
