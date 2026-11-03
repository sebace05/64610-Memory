# First Qwen capability checkpoint

The first real-model milestone is one auditable CookingWorld episode using
`Qwen/Qwen3-4B-Instruct-2507` with all previous visible observations/actions.
Then run several development seeds without changing settings. A completed game
loss is valid diagnostic data; it does not demonstrate adequate gameplay skill.

## What is implemented and verified

- A single-device Transformers adapter, pinned optional inference dependencies,
  and CLI that loads the model once for a sequence of diagnostic seeds.
- Exact tokenizer counting, new-output-only decoding, greedy generation,
  immutable model/tokenizer revisions, synchronized GPU timing, generation
  limits, and peak allocated CUDA memory per request.
- An explicit full-history archive with no compression, writer inference, or
  memory-limit enforcement. The actor sees the current public view and a JSON
  archive of initial/nonterminal observations and actions; the latest observation
  also appears in the current view. Prior action lists, repairs, hidden simulator
  state, and scoring fields are not added to the archive. Terminal evidence is
  logged but requires no later decision.
- Offline adapter tests execute actual generation with tiny random Qwen3
  weights, plus controlled EOS/output slicing and context-overflow checks.
  They never download or evaluate the production checkpoint.
- Real-simulator diagnostic tests and an auditor with hand-calculated log
  fixtures. Existing bounded-memory fixture tests remain required.

**Not yet verified:** Colab execution, CUDA/BF16/FP16 execution, production
checkpoint downloads, actual Qwen gameplay capability, production model/tokenizer
integration with the P1 memory strategies, and resumable batches. The implementation environment has no GPU. Hugging Face
access from that cloud environment is also restricted; Colab uses its own network.

## Colab workflow

1. Commit and push this implementation so Colab can retrieve it. Open
   [qwen_colab.ipynb](../notebooks/qwen_colab.ipynb) and enter the full code SHA.
2. Select a GPU runtime. Start with a 24 GB L4-class GPU if available. FP16 on a
   16 GB T4 may work, but test memory use. The notebook defaults to BF16; explicitly
   set FP16 for a T4. Do not mix precisions within a frozen experiment.
3. Mount persistent output storage, install the isolated environment, and pass
   the tests before loading weights. The isolation avoids Colab package conflicts.
4. Resolve the model revision once. The same immutable commit loads both model
   and tokenizer. Record it and reuse it when freezing the protocol.
5. Run seed 0 at budget 80 and reread price 2. Inspect the report and exact trace.
6. If the technical checks pass, run development seeds 1–4 with the same settings.
   The notebook loads the model once for these four games. It refuses to rerun
   existing seeds or silently retry partial episodes in the same pilot directory.
7. Save the manifest, dependency freeze, results, traces, and checkpoint report.
   Stop/disconnect the GPU when finished.

The notebook has no embedded tokens. Public weights ordinarily need no Hugging
Face credential. For a private GitHub checkout, use your normal secure Colab
authentication rather than storing credentials in notebook cells.

## Equivalent commands on a GPU machine

From the repository root, create an isolated Python 3.10+ environment and use
its Python consistently. For example:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-model.txt
.venv/bin/python -m pip check
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
java -version
```

The CUDA-enabled PyTorch distribution also requires a compatible NVIDIA driver.
The adapter fails if CUDA or the explicitly selected precision is unsupported;
it does not change devices, precision, or quantization automatically.

### Colab Java cgroup warnings and Py4J startup

Some Colab Java 21 runtimes print `[warning][os,container]` cgroup messages to
stdout before the Py4J gateway's numeric port. Py4J tries to parse the first line
as an integer and raises `ValueError: invalid literal for int()`. The subsequent
`TextWorldExpressEnv` destructor error about a missing `_gateway` is secondary:
construction failed before that field could be assigned.

The notebook appends the following Java 9+ unified-logging options to the
subprocess environment, preserving existing `JAVA_TOOL_OPTIONS`:

```text
-Xlog:os+container=off:stdout -Xlog:os+container=warning:stderr
```

These options route container warnings/errors to stderr and leave stdout free
for the gateway protocol. They do not disable container detection, change the
Python/Java versions, or modify installed packages. For an already-open notebook,
run this cell before retrying the tests and keep this same `ENV` for inference:

```python
ENV["JAVA_TOOL_OPTIONS"] = (
    ENV.get("JAVA_TOOL_OPTIONS", "")
    + " -Xlog:os+container=off:stdout"
    + " -Xlog:os+container=warning:stderr"
).strip()
result = subprocess.run(
    [PYTHON, "-m", "pytest", "-q"], cwd=REPO_DIR, env=ENV,
    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
)
print(result.stdout)
result.check_returncode()
```

Rerunning the original installation cell in an older notebook recreates `ENV`;
add the fix immediately after its `ENV = ...` assignment if rerunning that cell.
Native tests reproduce noisy JVM stdout with container trace logging and verify
that the notebook options restore a real simulator reset.

Replace the revision placeholder with the full checkpoint commit SHA. Use a new
output directory for each configuration or repeat attempt:

```sh
.venv/bin/python -m game_memory.run_episode \
  --backend transformers --strategy full_history \
  --model-revision FULL_40_CHARACTER_MODEL_COMMIT_SHA \
  --dtype bfloat16 --context-limit 8192 --action-max-new-tokens 128 \
  --generation-seed 0 --seed 0 --recheck-cost 2 --action-budget 80 \
  --output-dir /path/to/persistent/pilot-001

.venv/bin/python -m game_memory.summarize_diagnostics /path/to/persistent/pilot-001
```

For the next four development games, use `--seeds 1 2 3 4` with the same options.
The CLI stops on the first infrastructure error; inspect it before retrying.
This supports sequential diagnostics, not durable batch scheduling/resume.
The notebook adds duplicate/partial-run guards, but the CLI intentionally keeps
the existing behavior of preserving every attempt in a fresh episode directory.

Fake plumbing check, requiring only the base dependencies and Java:

```sh
.venv/bin/python -m game_memory.run_episode --backend fake \
  --strategy full_history --seeds 0 1 --action-budget 6 \
  --output-dir /tmp/qwen-fixture-check
.venv/bin/python -m game_memory.summarize_diagnostics \
  /tmp/qwen-fixture-check --include-fixtures
```

Fixtures never count toward real-model completion/success totals. Without
`--include-fixtures`, the auditor rejects them. Do not pass that flag for a real
pilot. Use a fresh directory when repeating this example.

## How to interpret the checkpoint

The report independently checks event sequences, result/header consistency,
request/response/error pairing, total and per-purpose inference tokens, model
latency totals, action budgets, rereads, and terminal records. Missing results
are pending; duplicate seeds and mixed configurations are flagged rather than
pooled. Infrastructure errors remain separate from valid unsuccessful games.
The report exits nonzero for broken/pending logs or real infrastructure errors;
gameplay losses alone do not fail the technical checkpoint.

Inspect output-limit hits and repair calls first. Then annotate loops,
navigation/cooking errors, decisions that ignore available recipe information,
and budget exhaustion. Cross-check assertions against the actual prompt the
model received. Five development games provide feasibility evidence, not a
precise success-rate estimate or a comparison of memory formats.

The adapter reserves room for its entire output allowance. If prompt plus
allowance exceeds the smaller of `context_limit` and the model's native limit,
it records an inference error without truncating history. Changing the context
cap, output allowance, prompt, precision, or game settings creates a new pilot
configuration. Retain previous artifacts and rerun consistently.

Inference timing excludes tokenization, input transfer, and decoding; end-to-end
episode runtime is recorded separately. Model-loading time is metadata, separate
from generation time. Drive writes may affect episode wall time. Neither number
alone equals billed GPU time; measure startup, setup, and idle allocation too.

Before evaluation, freeze the code commit, model/tokenizer revision, dependency
freeze, GPU/precision, greedy decoding, generation limits, prompts, game
settings, seed lists, and error/retry rules. GPU numerical behavior need not be
bitwise identical across hardware even with a fixed seed.

## Next milestone

After real full-history capability is assessed, connect the P1 prose, structured,
and hybrid writers in `game_memory/memory.py` to the real-model CLI and validate
their exact rendered token limits, one repair, previous-valid-memory fallback,
and reset/history isolation with the production Qwen tokenizer. Use the same
model adapter for acting and writing. P1's controlled-output and simulator tests
already exercise these policies. The current real-model CLI supports only the
full-history diagnostic and refuses to silently combine Qwen with fake memory.
