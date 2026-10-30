# S2 integration fixtures

These runs use the real CookingWorld environment with a fake model and fake memory.
They verify wiring, logging, and configuration switching; they are not LLM evaluation results.
Usage counts are whitespace fixture units, not Qwen tokens.

| Strategy | Reread price | Ending | Steps | Budget used | Result | Trace |
| --- | --- | --- | --- | --- | --- | --- |
| prose | 2 | budget_exhaustion | 5 | 6 | [result](d2f708f1b0154738a88756d1e68c9c2a/result.json) | [events](d2f708f1b0154738a88756d1e68c9c2a/events.jsonl) |
| hybrid | 5 | budget_exhaustion | 2 | 6 | [result](f476d72512fe4b7b902cd7f65c4a4116/result.json) | [events](f476d72512fe4b7b902cd7f65c4a4116/events.jsonl) |

Read events in sequence order: episode_start, reset, model requests/responses,
memory updates, game actions, and episode_end. Only the current view and bounded
memory are supplied to the actor; complete history exists only in the trace.

S2 remains in progress until the real model and real memory implementations are connected.
