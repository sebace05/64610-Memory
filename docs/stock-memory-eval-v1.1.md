# Stock reader on saved writer notes v1.1

Pre-inference amendment to [v1](stock-memory-eval-v1.md): require actual
**NVIDIA A10G** for this stock baseline and any later matched adapted-reader
comparison. All other scientific settings stay fixed: the same 64 literal writer
snapshots/prompts, B=256, pinned Qwen revision/runtime, 64 primary forwards,
64 independent reference forwards, 64 repeats, and the same time/resource limits.

Two Modal `gpu="A10"` placements supplied A10G cards. V1 refused both before
tokenizer/weights; each made zero model calls. A fresh OCI-pinned placement was
rejected during Function creation and submitted no input. All three attempts and
their shutdown evidence are preserved. No reader prediction was seen before
this hardware amendment. New execution uses a fresh identity and source package.

Keep the original v1 annotation schema and labels unchanged. They were reviewed
before every inference attempt. The original review file has SHA-256
`a028c988c9288a74770afa8c28c6cc3d51178c16dda4845fca153308c08c82a1`;
the packaged JSON omits its final newline and has SHA-256
`353f73cf4a527c23a4e28297801ffe9fbdc5cf1a6826fecfb5103746dc2691fe`.
Their parsed contents are identical; the byte difference is recorded separately.

Do not interpret differences from the earlier A10 scripted-note study as effects
of writer quality alone: families, note contents and hardware differ. Compare
stock versus any future adapted reader on identical notes and actual A10G.
