# 64610-Memory

MIT 6.4610 research project: how does the cost of recovering forgotten recipe
information affect prose versus structured JSON memory in a CookingWorld agent?

## Start here

Open **[the notebook in Colab](https://colab.research.google.com/github/sebace05/64610-Memory/blob/main/notebooks/qwen_colab.ipynb)**,
select T4, and choose **Runtime → Run all**. Authorize Drive if prompted.
The launcher resolves and records the development commit automatically; set
`REPO_REF` to a full SHA for a frozen run. See [the checkpoint guide](docs/qwen-checkpoint.md).
It currently selects a one-room/one-ingredient full-history capability check and
keeps Qwen loaded between explicitly chosen development runs.

Local corrected-greedy runs use the RTX 5070 Ti. Two full-history Qwen 4B
checks succeeded. The original eight-condition bounded-memory MVP exhausted
the budget in every cell. A later versioned development replay (actor v29,
memory v16) completed the same prose/JSON × prices 2/5 × seeds 0/1 grid:
prose won all four, while JSON ended in four gameplay losses. None of these
eight runs exhausted the budget or repeated an action on consecutive turns;
all traces passed audit. The actor keeps legal repeat actions available and
uses model-generated reviews for specific action errors. See the
[measured results](docs/mvp-results.md). Hybrid, large evaluations, dashboards,
and batch/resume remain deferred.

## Code map

| Purpose | Files in `game_memory/` |
| --- | --- |
| Run one game | `runner.py`, `environment.py`, `actor.py` |
| Shared inputs and interfaces | `contracts.py`, `components.py` |
| Model inference and live Colab session | `transformers_model.py`, `colab_session.py` |
| Memory strategies and diagnostic history | `memory.py`, `diagnostics.py` |
| Commands, manifests, and launch logs | `run_episode.py`, `pilot.py` |
| Read saved evidence | `inspect_episode.py`, `summarize_diagnostics.py` |
| Scripted integration fixtures | `integration_fixtures.py` (simulator checks live in `tests/`) |

## Local checks

Requires Python 3.10+ and Java. GPU packages are separate from base dependencies.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
```

Model-adapter checks require `requirements-model.txt`; they skip when optional
packages are absent. Production Qwen runs require Colab GPU checks in the guide.
The optional local RTX 5070 Ti setup and launcher are documented in the [Qwen checkpoint guide](docs/qwen-checkpoint.md#run-the-same-checkpoint-locally-on-an-rtx-5070-ti).

## Evidence and references

Keep new run logs in Drive or local `artifacts/` (ignored by Git). Existing
committed fixtures remain tracked; they are simulator/fake-model evidence, not
memory-comparison results. Keep notebook outputs empty and download trace ZIPs
separately. Pinned older notebooks still reproduce their original code revisions.

- [Environment rules](docs/s1-environment.md), [runner contract](docs/s2-runner.md),
  [memory policies](docs/p1-memory.md), [actor trace analysis](docs/actor-policy.md).
- [Original proposal, team task board, and deferred evaluation plan](https://github.com/sebace05/64610-Memory/blob/595cf5ca83912e6ab5d50c36717cd41f342108f5/README.md).
