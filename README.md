# 64610-Memory

**Standing GPU authorization, November 17:** the user authorized GPU runs for this
project. Proceed with bounded, versioned experiments without requesting GPU
permission again. This supersedes older per-run authorization wording; preserve
each run's settings, resource ceilings, evidence, exit status, and shutdown.

**Writer calibration completed, November 17: B=256.** All 64 C00–C03 P0/P12
snapshots passed raw-trace audit and independent tokenizer recount; the largest
is 183 tokens. The selected corpus contains 448 primary writes and two repairs,
with no fallbacks or empty snapshots. Recovery preserved completed units after
two Modal preemptions; all Apps are verified stopped. Read the
[results and evidence](docs/writer-collection-results-2026-11-17.md) and
[collector guide](docs/writer-collection-v1.md). Offline validation: 559 tests
passed, 26 skipped, plus transport checks. Training remains the next stage.

**Earlier GPU result, November 17:** reader diagnostic v1.1 completed 312 model
requests on A10G. Production/reference scores matched exactly on all 104 distinct
prompts. Q00's JSON errors followed green across option labels and changed with
entity order. Both diagnostic Apps are verified stopped. See the
[results, integration fix, and evidence](docs/reader-diagnostic-results-2026-11-17.md).

**Earlier checkpoint:** the controlled memory harness and Modal transport are
implemented. The first real run stopped at its frozen reader gate: 15/16 full
history, 16/16 sufficient prose, and 13/16 sufficient JSON. That attempt reached
neither writer calibration nor task-specific fine-tuning. Read the
[implementation and verification handoff](docs/implementation-status-handoff-2026-11-17.md)
and the new [pretrained-versus-fine-tuned reader proposal](docs/pretrained-vs-finetuned-memory-proposal.md).
The proposal counts ordinary model errors in accuracy and compares memory schemes
before and after reader adaptation.

The implemented checkpoint includes a [reader diagnostic](docs/reader-diagnostic-v1.md)
with offline preparation/tests and specifies a [matched reader-training protocol](docs/matched-reader-training-v1.md).
It tests entity/option order and compares restricted scoring, an independent raw
forward, and greedy answers. GPU diagnosis has completed; reader fine-tuning and
the matched training comparison remain future implementation work.

CookingWorld with a Qwen actor and three memory conditions: full public history,
model-written prose, and model-written structured JSON. Its preserved workflow is the
[v31-preserving minimal core](docs/minimal-core.md). Follow the current diagnostic
workflow above; older CookingWorld commands retain their historical settings.

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
CookingWorld has no separate pilot/inspection CLI. The controlled study and its
Modal transport are described in the progress handoff above.

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
the default CookingWorld actor.
