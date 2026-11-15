#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python=".venv/bin/python"
if [[ ! -x "$python" ]]; then
  printf 'Missing %s. Follow the Local RTX 5070 Ti setup in docs/qwen-checkpoint.md.\n' "$python" >&2
  exit 2
fi
if ! command -v java >/dev/null 2>&1; then
  printf 'Java was not found on PATH. Install a Java 17 runtime, then retry.\n' >&2
  exit 2
fi
dtype="${LOCAL_QWEN_DTYPE:-bfloat16}"
if [[ "$dtype" != bfloat16 && "$dtype" != float16 ]]; then
  printf 'LOCAL_QWEN_DTYPE must be bfloat16 or float16.\n' >&2
  exit 2
fi

# Fail before creating a pilot if CUDA or the requested precision is unavailable.
LOCAL_QWEN_DTYPE="$dtype" "$python" - <<'PY'
import os
import torch

if not torch.cuda.is_available():
    raise SystemExit("PyTorch cannot access CUDA. Install a CUDA-enabled PyTorch build in .venv.")
name = torch.cuda.get_device_name()
if "5070 Ti" not in name:
    raise SystemExit(f"Expected the RTX 5070 Ti, found {name!r}; check CUDA_VISIBLE_DEVICES.")
if os.environ["LOCAL_QWEN_DTYPE"] == "bfloat16" and not torch.cuda.is_bf16_supported():
    raise SystemExit("The detected GPU/PyTorch build does not support BF16; use the documented float16 override.")
print(f"Using {name}; PyTorch {torch.__version__}; CUDA {torch.version.cuda}; dtype {os.environ['LOCAL_QWEN_DTYPE']}")
PY

if (($#)); then
  output_dir="$1"
  shift
else
  output_dir="artifacts/local-qwen-$(date -u +%Y%m%dT%H%M%SZ)"
fi
exec "$python" -m game_memory.pilot \
  --output-dir "$output_dir" \
  --backend transformers --strategy full_history --actor-prompt v3 \
  --model-id Qwen/Qwen3-4B-Instruct-2507 \
  --model-revision cdbee75f17c01a7cc42f958dc650907174af0554 \
  --device cuda --dtype "$dtype" \
  --context-limit 8192 --action-max-new-tokens 128 \
  --generation-seed 0 --recheck-cost 2 --action-budget 80 \
  --num-locations 1 --num-ingredients 1 --seed 0 \
  "$@"
