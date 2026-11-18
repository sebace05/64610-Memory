# Paper-reading pilot — November 18

**The stock model answered every question from the full papers, but the notebooks
lost facts during updates. This pilot does not establish a winning format.**

We ran three real papers with nine objective questions using stock
`Qwen3-4B-Instruct-2507`, without fine-tuning. Each writer read the paper once in
order, seeing only its previous notebook and the next chunk. Questions stayed
hidden until reading finished. Prose and JSON each had **2,048 stored tokens**;
the reader received only the final notebook and one question. The reference
reader received the full paper. There were no artificial filler rewrites.
The [frozen protocol](paper-memory-v1.md) and
[curated QASPER training inputs](../data/paper-memory-v1/papers.json) give the details.

## Accuracy

These are the prespecified exact-match scores; all questions remain counted.

| Context | Correct | Accuracy |
|---|---:|---:|
| Full paper | 9/9 | 100% |
| Prose notebook | 5/9 | 55.6% |
| JSON notebook | 6/9 | 66.7% |
| Gold evidence paragraph | 9/9 | 100% |
| No context | 1/9 | 11.1% |

| Paper | Source tokens / chunks | Full paper | Prose | JSON | Final prose / JSON tokens |
|---|---:|---:|---:|---:|---:|
| P00: acoustic word embeddings | 6,176 / 6 | 3/3 | 3/3 | 1/3 | 1,828 / 1,908 |
| P01: annotation reliability | 2,923 / 3 | 3/3 | 0/3 | 3/3 | 393 / 1,582 |
| P02: autocompletion study | 4,244 / 4 | 3/3 | 2/3 | 2/3 | 1,941 / 1,782 |

JSON's token F1 was 76.5%; prose's was 55.6%. One JSON exact-match miss gives the
correct corpus name followed by `(BIBREF31)`. Counting that citation-only answer
as factually correct gives **7/9 JSON**, a separate post-hoc agent judgment.
The frozen aliases and primary scores are unchanged.

## What the traces show

We reviewed all seven strict notebook misses against the source and saved notes:

- **Four facts disappeared after being stored.** P00 JSON initially recorded the
  classifier dimension, 1061, then dropped it in the next update; the final reader
  answered 1024, another embedding dimension. P01 prose stored 541 tweets, 56
  participants and 1120 annotations, then omitted all three in its 393-token final
  note. The reader appropriately abstained. The writer had received the correct
  previous note, so P01's loss occurred in the generated rewrite despite ample
  unused allowance.
- **One fact never entered the saved note.** P02 prose rejected the update
  containing the 300-dimensional vectors and its repair. Later updates also fell
  back, leaving the reader without that fact.
- **One case needs a label diagnostic.** P02 JSON retains `total_workers: 176`,
  the Control/AUI group counts and the separate 119 quality raters, but drops the
  term “conceptualization.” The reader abstains on the original question, including
  its repeat. A reader retrieval/wording problem, a lost task-label link, or both
  remain possible.
- **One miss is citation-only**, as described above.

Fallback sometimes protected earlier queried facts by rejecting later writes.
P00 prose and P01 JSON benefited from this. Higher accuracy on these questions
therefore does not imply better coverage of the whole paper. There were **eight
repairs and seven fallbacks across 26 updates**. The allowance and generation cap
were binding in several cases; 2,048 tokens cannot be described as uniformly
generous. P01 also shows that extra space alone does not guarantee retention.

The no-context success was the familiar Google News word2vec dimension, 300.
That question stays in the results, but its correct answer cannot be attributed
solely to memory. Future questions should emphasize paper-specific facts.

## Execution and evidence

All three runs used the same pinned checkpoint, FP16, greedy decoding and actual
NVIDIA A10G. **94 requests and 94 responses** completed: 26 primary writes, eight
repairs, 45 primary answers and 15 repeats. Every repeat matched exactly. Raw
prompt replay, independent notebook token recounts, scoring and completion hashes
passed. No input was truncated. Five setup failures made zero model calls; all
eight submitted Apps are verified stopped with zero tasks. Explicit `gpu="A10G"`
worked for the final two runs; generic `A10` also produced rejected A10 allocations,
and cloud pinning was refused by the service.

Measured usage: **204,056 input tokens, 65,570 output tokens**. Writing used 2,719.3
seconds of synchronized generation time; answering and repeats used 28.8 seconds.
Worker times were 1,377.0 / 461.8 / 1,061.4 seconds, including loading and I/O;
P01/P02 overlapped. Peak allocated CUDA memory was at most 9.54 GB. These are
measurements, not a monetary billing estimate.

Offline validation: **641 passed, 26 skipped**, including 21 new paper tests.
The full suite emitted one existing TextWorldExpress destructor warning.
Transport templates passed ten checks each, including the explicit-A10G packets.

[Evidence archive](../handoff/paper-memory-20261118-evidence.zip),
[SHA-256](../handoff/paper-memory-20261118-evidence.zip.sha256).
Extract into `artifacts/`; the archive contains frozen launchers/packages, raw
updates and answers, failures, shutdown proofs, `analysis-final/predictions.csv`,
`analysis-final/error-review.json`, and the read-only analysis script. An earlier
diagnostic substring flag confused 300 with 4300; the corrected final analysis
uses number boundaries. No primary score changed; both derived versions remain.

Scientific manifest:
`ff8262391d10c7d18398a3957840a870b2dd7b7b74d8b76b704e45ec0c7ca3a4`.
Implementation was committed before predictions at `fbfa675`.

## Next iteration

First replay the P02 JSON case with its original wording, an explicit main
AUI/Control question, and a supplied mapping of “conceptualization” to that
experiment. Then freeze a larger paper study with paper-specific facts spread
across sections, a development rule for a generous shared allowance and output
headroom, and explicit citation handling. Keep the stock model baseline and track
when facts enter and leave each notebook before considering adaptation.

Three agent-curated papers, nine questions and one writer trajectory per format
are exploratory. Questions mostly concern middle sections. Different paper
lengths also differ in content; these results do not isolate a length effect or
justify a general prose-versus-JSON ranking. Source questions and error reviews
were agent-checked, without independent human validation.
