# Laptop Codex + Modal setup

**Laptop implementation update, November 16:** the launcher now exists at
`scripts/modal_calibration.py`. Remote CPU preflight passed 389 tests with zero
skips, and the first authorized A10 pilot succeeded in 11 actions. Follow
[the implemented launcher workflow](modal-calibration.md) for current commands,
saved run references and evidence retrieval. On this laptop, use the working
`python3`/Modal installation; the local `.venv` is not required. The original
setup and implementation-assignment instructions below remain as handoff context.

Prepared November 16, 2026. The intended arrangement is:

`Codex on laptop → Modal client credentials → remote Linux GPU job → persistent results → Codex review`

The laptop does not need CUDA, a GPU, Java, or the Qwen model weights for this
workflow. They belong in the remote image/cache. Codex works in a local project
folder and uses the authenticated Modal client to submit and retrieve work.
There is no need to install Codex in the GPU container. A separate OpenAI API
integration is not required to use your existing Codex session for later review.

**Important:** this handoff supplies source, evidence and an implementation
prompt. The project-specific Modal launcher has **not** been implemented or
cloud-tested yet. The receiving agent will build it before the first GPU run.
Do not mistake the old RTX/Colab launchers for a Modal launcher.

## 1. Clone the handoff branch on the laptop

The `codex/modal-calibration-handoff` branch contains the tested v17/v30 source,
tests, reports and these instructions. It also includes the original portable
snapshot and research evidence as `handoff/codex-modal-handoff-20261116.zip`,
with an adjacent checksum. No separate download from the old session is needed.
Use a new laptop directory; do not overlay unrelated local edits.

With Git and Python 3.12 installed, on macOS/Linux:

```sh
git clone --branch codex/modal-calibration-handoff https://github.com/sebace05/64610-Memory.git 64610-Memory-modal
cd 64610-Memory-modal
python3.12 -m venv .venv
.venv/bin/python -m pip install modal
```

On Windows PowerShell, use the same clone and `cd`, then:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install modal
```

Authentication to GitHub, if required, uses your normal Git credentials. Do not
check out old commit `739e72d`: it predates the implemented v17/v30 changes.
That original dirty state is preserved as provenance inside the archive.

The receiving agent will follow `handoff/README.md` to verify the archive's
SHA-256 and internal payload manifest and restore its `artifacts/` entries,
including historical test fixtures. Keep the branch's committed source/docs;
the archived setup docs describe the earlier pre-commit transfer workflow and
should not replace the current instructions. The archive excludes environments,
model weights, `.git`, credentials and home-directory configuration. No project
files have been uploaded to Modal yet.

## 2. Create and authenticate your Modal account

Create an account at <https://modal.com>, select the intended personal/workspace
account, and add a payment method for GPU usage. Set account spending controls
appropriate to this small pilot. Log into the same account from your laptop.

From the new project folder on macOS/Linux:

```sh
.venv/bin/python -m modal setup
.venv/bin/python -m modal app list --json
.venv/bin/python -m modal volume list --json
```

On Windows substitute `.\.venv\Scripts\python.exe` for `.venv/bin/python`.
The setup command opens the authentication flow. Do not paste account tokens
into the Codex conversation, commit them, or include them in uploaded source.
The two list commands verify client/account access; they do not launch a GPU.
Record the installed Modal client version when the agent prepares the image.

Official installation/authentication guide:
<https://modal.com/docs/guide>.

## 3. Open the laptop folder in Codex and provide the handoff

Select the local `64610-Memory-modal` project folder in your Codex UI. This is
the laptop checkout, not the former SSH workspace. Start a new conversation.

Paste the contents of `docs/codex-modal-handoff-prompt.md`. If Codex can read
the local folder already, the shorter equivalent is:

```text
Read docs/codex-modal-handoff-prompt.md and execute that handoff. This is the
laptop checkout of codex/modal-calibration-handoff. Verify and restore the
archived evidence as described in handoff/README.md before editing.
Modal is authenticated on this laptop.
```

Submitting that handoff explicitly authorizes necessary source deployment,
remote CPU checks and **one** paid A10 JSON seed-1 cloud episode with fixed
policy settings, a 60-minute execution timeout, finite startup timeout and no
blind retries. It does not authorize policy tuning or the full comparison.
If you want preparation only, tell the new agent to implement/test the launcher
but stop before paid GPU execution.

## 4. What the agent will set up and verify

- A thin `scripts/modal_calibration.py` launcher around the existing runner,
  with explicit deployment source allowlists.
- Python 3.12, Java 17 and pinned dependencies in a remote Linux image.
- One A10 GPU (24 GB VRAM), explicitly requested 32 GiB system RAM and four
  CPU cores; no locally shared WSL RAM/swap or Windows disk dependency.
- Separate persistent volumes for model cache and results, with fresh run and
  attempt IDs, periodic commits, immutable manifests and real exit statuses.
- Remote CPU/simulator checks and meaningful launcher failure handling before
  inference. GPU preflight happens before weights are allocated.
- One unchanged-policy JSON seed-1 episode, condition audit, trace inspection,
  token recount, report, downloadable ZIP and checksum.

Modal resource requests and timeout controls are documented at
<https://modal.com/docs/guide/resources> and
<https://modal.com/docs/guide/timeouts>. GPU usage is subject to preemption, so
the launcher must preserve interrupted attempts and prevent automatic replay
from overwriting them: <https://modal.com/docs/guide/preemption>.

Historical source/results remain read-only. A10 is a different runtime from the
local RTX 5070 Ti; the cloud job needs a separate root and declared identity.
It must not be silently inserted into the local six-game manifest. There are
currently five completed local episodes; two startup OOMs and an earlier partial
prose trace remain preserved.

## 5. Submit, disconnect and retrieve results

Have the agent provide and verify the exact project launch command after it
implements the launcher. For detached execution the command will use the
documented shape:

```text
.venv/bin/python -m modal run --detach scripts/modal_calibration.py::<remote-entrypoint>
```

This is a command **shape**, not an executable command yet: the file and remote
entrypoint must first be implemented, and `<remote-entrypoint>` must be replaced
with its real name. The execution plan must run inside that remote entrypoint;
putting a submission loop in a laptop-only entrypoint would still depend on
the laptop staying online.

After submission, the agent should save a local run-reference JSON under
`artifacts/modal/` with app/function IDs, run ID, provider workspace, volume
names and remote paths. Keep that file for the next Codex session.

These documented commands are useful once the agent supplies real values:

```text
.venv/bin/python -m modal app list --json
.venv/bin/python -m modal app logs APP_ID
.venv/bin/python -m modal volume ls memory-research-results
.venv/bin/python -m modal volume get memory-research-results RUN_ID artifacts/modal-downloads/RUN_ID
```

Replace APP_ID and RUN_ID, and use the actual volume name selected by the
launcher. Do not download the model-cache volume unnecessarily. Use the same
workspace/profile when retrieving data. See
<https://modal.com/docs/guide/apps> and
<https://modal.com/docs/reference/cli/volume>.

You can then close the laptop/session while the detached remote job executes.
Results must be persisted remotely, not just printed to a terminal. When you
return, tell Codex:

```text
Read the saved Modal run-reference under artifacts/modal/. Check that run's
status, retrieve completed and failed attempt evidence into a fresh local
directory, audit it, and explain the results and the smallest justified fixes.
Preserve the frozen run; propose policy changes separately before another pilot.
```

The same file-based handoff works for a later new Codex conversation. Automatic
delivery of an AI-written report while Codex is closed requires a separate
completion-triggered agent/notification integration. It is not installed by
`modal setup` and is outside this first migration checkpoint.

## 6. What follows the cloud pilot

Review actual gameplay before more launches. The local results show useful
recipe retention but actor/review finalization failures and writer omissions of
carried/completed state, with no observed 512-token capacity failure. First
validate cloud execution. Any proposed actor/writer changes then need explicit
prompt versions and a new declared calibration. Do not tune settings mid-pilot,
auto-retry gameplay losses, or launch the eight-game comparison early.
