# First Modal migration pilot — JSON seed 1 succeeded

November 16, 2026. The single authorized A10 migration episode completed with
score **1.0**, **11 actions**, **14/80 budget units spent**, and three paid recipe
rereads. Model loading, gameplay, remote offline auditing and verified evidence
retrieval all succeeded. Both Modal apps subsequently stopped with zero tasks.
The five old RTX results and both startup OOM attempts remain unchanged.

## Outcome and accounting

| Outcome | Actions | Budget spent | Recipe rereads | Writer primary / repair / fallback | Stored tokens |
| --- | ---: | ---: | ---: | --- | --- |
| Success, score 1.0 | 11 | 14/80 | 3 | 11 / 0 / 0 | 101–105 of 512 |

All 11 writes were nonempty JSON objects. There were no syntax/size rejections,
writer repairs, previous-state fallbacks, or generation-limit hits. The cached
pinned tokenizer independently recounted every stored rendering, with all 11
counts matching the trace. The observed 512-token limit was nonbinding.

There were 26 returned inference calls: 11 actor, three actor repairs, one actor
review and 11 writer calls. All input/output usage reconciled to the raw trace:
**13,141 input tokens, 1,665 output tokens**, and **69.22 seconds** of synchronized
generation. Generation by purpose was 14.65 seconds actor, 3.75 repair, 1.71
review and 49.11 writer. No usage was omitted because a response was rejected.

Episode time was **69.89 seconds**. Model/tokenizer loading took **47.69 seconds**,
including the cold checkpoint download. The measured pilot subprocess took
**125.12 seconds**; the full remote worker, including preflight and offline
auditing, took **152.17 seconds**. These scopes exclude initial image building
and scheduling. They do not establish a hardware speed advantage over the
unequal-length historical RTX episodes.

GNU time recorded maximum RSS **16,588,236 KiB (15.82 GiB)** and exit 0. This is
the tool's process/descendant maximum-RSS statistic, not an aggregate sampled
container-memory peak. Every recorded preflight, episode and audit subprocess
returned 0; there was no timeout, replay, OOM or additional GPU episode.

## Actual gameplay and memory

Episode `e249e942d97c4a309d0d5dd6ab2142d9` requires chicken wing and salt, with
directions to grill the chicken and prepare the meal. All citations below are
zero-based raw event sequence IDs. Annotations use only public evidence available
at each checkpoint; these are manual, non-blind diagnostics.

- Reset 1 provides the recipe. Memory 4 retains both required ingredients and
  the grilling/preparation directions. Its `inventory.*=present` fields already
  list counter objects before taking them. Their carriage semantics remain
  unknown rather than being automatically scored as false inventory claims.
- Action 21 says **“You take the chicken wing.”** Memory 24 does not add an
  explicit chicken-possession fact. It keeps the prior recipe and object fields.
- Action 33 says **“You grill the chicken wing with the toaster.”** Memory 36
  changes progress to `toaster_used`. After cookbook action 41, memory 44 replaces
  that with `recipe_examined`, losing the appliance-use marker. The generic
  earlier marker is ambiguous about completed chicken preparation.
- Salt take 53 receives **“You take the salt.”** Memory 56 keeps the same salt
  `present` flag that existed before taking it. Memory 62 before preparation
  retains all four selected recipe requirements, with explicit chicken carriage
  and completed grilling omitted. In the manually selected eight-fact checklist,
  four facts are supported, two omitted and two unknown. Unknowns stay in the
  denominator; this is a scoped checklist, not whole-memory accuracy.
- Prepare action 67 says **“Adding the meal to your inventory.”** Memory 70
  records `meal_prepared` but does not explicitly add meal carriage. The next
  actor response 72 still proposes unavailable `grill chicken wing`. Model repair
  74 chooses `eat meal`; action 75 succeeds. The current public observation also
  states meal creation, so this final turn does not isolate reliance on memory.

Three repairs recover unavailable first proposals; no invalid action reaches
the environment. The recipe is reread at actions 27, 41 and 59 while it remains
stored correctly. Successful gameplay coexists with avoidable rereads, omitted
state and inconsistent finalization. No Python factual correction or forced
useful action was added. Six annotated memory checkpoints, their cited public
quotes and separately scoped retention/claim assessments are saved in
`artifacts/modal-review/modal-a10-gpu-20261116T183246Z-0e520586/offline-structured-annotations.json`.

## Frozen policy and runtime identity

Protocol `qwen-calibration-v17-v30-modal-a10-pilot-v1`; model/tokenizer
`Qwen/Qwen3-4B-Instruct-2507` revision
`cdbee75f17c01a7cc42f958dc650907174af0554`; actor `s2-action-v30`, writer
`p1-memory-v17`, renderer `p1-render-v2`. CUDA FP16, no quantization, greedy
generation seed 0, context 8192, actor cap 128, writer cap 1024, stored limit 512.
Train game seed 1, one room, two ingredients, zero distractors, no doors,
unlimited inventory, one free initial recipe, budget 80 and reread price 2.

Requested GPU `A10`; actual device **NVIDIA A10G**, four CPUs and 32 GiB requested
host RAM. Python 3.12.10, Java 17.0.21, PyTorch 2.8.0, CUDA runtime 12.8,
Transformers 4.57.6 and Modal SDK 1.6.4. NVIDIA-SMI reports KMD 620.70.06 and
CUDA UMD 13.5, distinct from PyTorch's CUDA runtime. The package freeze and
complete driver output are saved. GPU region was `us-west`; CPU validation was
`uk`, using the same image `im-lUVTCGHpNdXdw1DYmPurBg`.

Frozen executable digest:
`f4c9b85a1594d02e3b2ac6ae225a4e82b9b0566ab6b545cc93d055d5cd860afb`.
Uploaded source/test/fixture/launcher snapshot:
`60e7d33508ac9ca617fb78d10501b62802220e0b6919246bcf73cbeb730a1993`.
Laptop commit was `18ade457aef86bf907c0877db9432d318095bfbc`, with new launcher
work outside the frozen executable digest. Remote Git commit/dirty metadata are
null because `.git` was deliberately excluded. Original historical provenance
is recorded separately, not fabricated as the remote checkout identity.

## Engineering validation and retrieval

The original handoff ZIP SHA-256 and CRC passed; all **282** internal manifest
file hashes matched. **197** artifact files were restored after validating the
entire selection; no existing content was overwritten. Remote CPU preflight then
passed **389 tests with zero skips in 404.69 seconds**, plus pip and Java checks.
Its nine migration tests cover duplicate/preempted attempt rejection, durable
marker failure, subprocess output/exits, timeouts and source isolation.

The first recursive CPU download exposed Modal 1.6.4 treating a nonexistent
destination as one file. That invalid local download is preserved and labeled.
The laptop fetch helper now precreates a fresh directory and verifies the plan,
source manifest and source ZIP CRC/per-file hashes. **Ten focused local launcher
tests passed** after that isolated retrieval fix. It was not redeployed into the
running pilot. Exact executed launcher/tests remain in each remote source ZIP.
The frozen experimental Python source stayed unchanged.

The retrieved condition was independently audited again on the laptop and
matched the remote audit exactly. All raw results/traces, usage, status files,
recount and source identities are retained. Commands tested in this session:

```sh
python3 scripts/modal_calibration.py submit cpu
python3 scripts/modal_calibration.py submit gpu --preflight artifacts/modal/modal-a10-cpu-20261116T182256Z-7d073670.json
python3 scripts/modal_calibration.py status artifacts/modal/modal-a10-gpu-20261116T183246Z-0e520586.json
python3 scripts/modal_calibration.py logs artifacts/modal/modal-a10-gpu-20261116T183246Z-0e520586.json
python3 scripts/modal_calibration.py fetch artifacts/modal/modal-a10-gpu-20261116T183246Z-0e520586.json
```

The submit commands are historical records of the two completed submissions;
do not repeat the GPU command. The local reservation prevents a second casual
submission. Status, logs and fetch are safe reconnect commands. Child output is
saved in volume logs; the app console primarily reports worker completion.

GPU app `ap-rKhW2KphvCB0dh4PqW24uA`, call
`fc-01M7JT46BTH6AKB0ARFTSZE2JF`, function `fu-Qdw61AdrlFQjWU4K6JaRPJ`,
workspace/profile `abdivuu`, environment `main`.
Remote root: `memory-research-results/modal-a10-gpu-20261116T183246Z-0e520586`.
Model cache remains in `memory-research-cache`; no weights were downloaded to
the laptop. The saved references in `artifacts/modal/` identify both runs.

Verified local GPU evidence root:
`artifacts/modal-downloads/modal-a10-gpu-20261116T183246Z-0e520586-d0a1ec0a/modal-a10-gpu-20261116T183246Z-0e520586/`.
Local review summary and annotations:
`artifacts/modal-review/modal-a10-gpu-20261116T183246Z-0e520586/`.
The final combined package is
`artifacts/modal/modal-a10-migration-20261116-evidence.zip`, with adjacent
`.zip.sha256`. It includes CPU/GPU evidence, original submitted source, current
laptop retrieval code/tests, references, review notes and this report. ZIP CRC
and per-file checksums are verified. It excludes credentials, environments and
model weights. Raw cloud evidence remains durable on the Modal results volume;
the combined ZIP is local and has not been uploaded elsewhere.

## Next iteration

The migration checkpoint passed and JSON succeeded on this cloud seed. The old
hardware-pinned local six-cell checkpoint remains five completed games with a
missing JSON cell. This separate A10 observation does not establish a format
advantage, reliable multi-seed competence or a memory-capacity effect.

Before drawing cloud comparisons, declare controls and a consistent cloud
runtime baseline. For subsequent policy work, the demonstrated targets remain
preserving confirmed possession/completed progress across unrelated writer
observations and aligning actor/review/repair finalization priorities. The actor
already has an eat-meal instruction; another copy is not a demonstrated fix.
Any changes need new prompt versions and focused real-Qwen checks with controls
inspected first. No prompt tuning or further GPU episodes were performed.
