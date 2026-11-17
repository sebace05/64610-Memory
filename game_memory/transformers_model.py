"""Single-device Transformers inference with no retained conversation state.

Imports are lazy so the simulator and fake-backend tests need no GPU packages.
Use an immutable Hugging Face commit for both model and tokenizer. This adapter
never truncates prompts, quantizes weights, or falls back from CUDA to CPU.
"""

from dataclasses import asdict, dataclass
from importlib.metadata import version
import platform
import re
import time
from typing import Sequence

from .components import Generation, Message


@dataclass(frozen=True)
class TransformersConfig:
    revision: str
    model_id: str = "Qwen/Qwen3-4B-Instruct-2507"
    device: str = "cuda"
    dtype: str = "bfloat16"
    context_limit: int = 8192
    action_max_new_tokens: int = 128
    memory_max_new_tokens: int = 512
    generation_seed: int = 0
    local_files_only: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.revision, str) or not re.fullmatch(r"[0-9a-f]{40}", self.revision):
            raise ValueError("revision must be an immutable 40-character model commit SHA")
        if self.device not in {"cuda", "cpu"}:
            raise ValueError("device must be cuda or cpu")
        if self.dtype not in {"bfloat16", "float16", "float32"}:
            raise ValueError("unsupported dtype")
        if self.device == "cpu" and self.dtype != "float32":
            raise ValueError("use float32 for the explicit CPU validation path")
        for name in ("context_limit", "action_max_new_tokens", "memory_max_new_tokens"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if type(self.generation_seed) is not int or not 0 <= self.generation_seed < 2**32:
            raise ValueError("generation_seed must be an integer in [0, 2**32)")


def runtime_metadata(config: TransformersConfig) -> dict:
    """Validate hardware without loading weights; also identifies the pilot runtime."""
    import torch

    if config.device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable; select a GPU runtime before loading Qwen")
        if config.dtype == "bfloat16" and not torch.cuda.is_bf16_supported():
            raise RuntimeError("GPU does not support BF16; explicitly select float16")
    return {
        "torch_version": version("torch"), "transformers_version": version("transformers"),
        "tokenizers_version": version("tokenizers"), "safetensors_version": version("safetensors"),
        "huggingface_hub_version": version("huggingface-hub"),
        "python_version": platform.python_version(), "cuda_version": torch.version.cuda,
        "gpu": torch.cuda.get_device_name() if config.device == "cuda" else None,
    }


class TransformersModel:
    """Load once, generate greedily, and account for actual prompt/output tokens."""

    def __init__(self, config: TransformersConfig) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.config = config
        runtime = runtime_metadata(config)
        torch.manual_seed(config.generation_seed)
        if config.device == "cuda":
            torch.cuda.manual_seed_all(config.generation_seed)
        started = time.perf_counter()
        common = {"revision": config.revision, "local_files_only": config.local_files_only,
                  "trust_remote_code": False}
        self._tokenizer = AutoTokenizer.from_pretrained(config.model_id, **common)
        if not self._tokenizer.chat_template:
            raise ValueError("checkpoint tokenizer has no chat template")
        self._model = AutoModelForCausalLM.from_pretrained(
            config.model_id, dtype=getattr(torch, config.dtype),
            use_safetensors=True, attn_implementation="sdpa", **common,
        ).to(config.device).eval()
        self._synchronize()
        model_limit = getattr(self._model.config, "max_position_embeddings", config.context_limit)
        self._context_limit = min(config.context_limit, model_limit)
        generation = self._model.generation_config
        self._eos_token_id = generation.eos_token_id
        if self._eos_token_id is None:
            self._eos_token_id = self._tokenizer.eos_token_id
        if self._eos_token_id is None:
            raise ValueError("checkpoint has no EOS token")
        self._pad_token_id = self._tokenizer.pad_token_id
        if self._pad_token_id is None:
            self._pad_token_id = (self._eos_token_id[0] if isinstance(self._eos_token_id, list)
                                  else self._eos_token_id)
        self._metadata = {
            "implementation": "TransformersModel", "is_fake": False,
            **asdict(config), "tokenizer_revision": config.revision,
            "effective_context_limit": self._context_limit,
            "do_sample": False, "num_beams": 1, "use_model_defaults": False,
            "attention_implementation": "sdpa",
            **runtime,
            "load_seconds": time.perf_counter() - started,
            "latency_scope": "synchronized_generate_excludes_tokenization_transfer_decode",
            "eos_token_id": self._eos_token_id, "pad_token_id": self._pad_token_id,
        }

    @property
    def metadata(self) -> dict:
        return dict(self._metadata)

    def _synchronize(self) -> None:
        if self.config.device == "cuda":
            import torch
            torch.cuda.synchronize()

    def count_tokens(self, text: str) -> int:
        return len(self._tokenizer.encode(text, add_special_tokens=False))

    def score_choices(self, messages: Sequence[Message], *, labels: Sequence[str]) -> Generation:
        import hashlib
        import torch

        labels = tuple(labels)
        prompt = self._tokenizer.apply_chat_template(
            [{"role": m.role, "content": m.content} for m in messages],
            tokenize=False, add_generation_prompt=True,
        )
        vocab_size = self._model.get_output_embeddings().weight.shape[0]
        ids = validate_choice_tokens(self._tokenizer, prompt, labels, vocab_size)
        inputs = self._tokenizer(prompt, add_special_tokens=False, return_tensors="pt",
                                 return_token_type_ids=False, truncation=False)
        shape = inputs["input_ids"].shape
        if len(shape) != 2 or shape[0] != 1 or shape[1] < 1:
            raise ValueError("invalid choice input shape")
        input_tokens = shape[1]
        if inputs["input_ids"][0].tolist() != self._tokenizer.encode(prompt, add_special_tokens=False):
            raise ValueError("choice tokenization disagrees with validated prompt")
        if input_tokens + 1 > self._context_limit:
            raise ValueError(f"context overflow: {input_tokens} input + 1 reserved output "
                             f"> {self._context_limit}; prompt was not truncated")
        inputs = inputs.to(self.config.device)
        if self.config.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        self._synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            output = self._model(**inputs, use_cache=False)
        self._synchronize()
        elapsed = time.perf_counter() - started
        scores = getattr(output, "logits", None)
        if scores is None or tuple(scores.shape) != (1, input_tokens, vocab_size):
            raise ValueError("invalid or missing choice logits shape")
        logits = scores[0, -1, list(ids)].float().cpu().tolist()
        selected, probabilities = restricted_choice(logits, labels=labels, token_ids=ids)
        details = {
            "inference_mode": "legal_label_argmax_v1", "generation_called": False,
            "labels": list(labels), "label_token_ids": list(ids),
            "special_token_ids": sorted(set(self._tokenizer.all_special_ids)),
            "candidate_logits": logits, "conditional_probabilities": probabilities,
            "selected_label": labels[selected], "selected_token_id": ids[selected],
            "selection_rule": "argmax", "tie_break": "first_in_supplied_order",
            "finish_reason": "choice", "decision_token_count": 1,
            "rendered_prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_hash_evidence": "actual_rendered_prompt",
            "scoring_evidence": "actual_model_forward", "output_vocab_size": vocab_size,
            "latency_scope": "synchronized_forward_excludes_tokenization_validation_transfer_cpu_selection",
            "peak_cuda_allocated_bytes": (torch.cuda.max_memory_allocated()
                                          if self.config.device == "cuda" else None),
        }
        return Generation(labels[selected], input_tokens, 1, elapsed, details)

    def generate(self, messages: Sequence[Message], *, purpose: str) -> Generation:
        import torch
        from transformers import GenerationConfig

        if purpose not in {"action", "action_review", "action_repair", "memory", "memory_repair"}:
            raise ValueError(f"unsupported generation purpose: {purpose}")
        cap = (self.config.action_max_new_tokens if purpose.startswith("action")
               else self.config.memory_max_new_tokens)
        # Apply the template once and tokenize without inserting duplicate BOS/EOS.
        prompt = self._tokenizer.apply_chat_template(
            [{"role": m.role, "content": m.content} for m in messages],
            tokenize=False, add_generation_prompt=True,
        )
        inputs = self._tokenizer(prompt, add_special_tokens=False, return_tensors="pt",
                                 return_token_type_ids=False)
        input_tokens = inputs["input_ids"].shape[-1]
        if input_tokens + cap > self._context_limit:
            raise ValueError(f"context overflow: {input_tokens} input + {cap} reserved output "
                             f"> {self._context_limit}; prompt was not truncated")
        inputs = inputs.to(self.config.device)
        settings = GenerationConfig(
            do_sample=False, num_beams=1, max_new_tokens=cap,
            eos_token_id=self._eos_token_id, pad_token_id=self._pad_token_id,
            use_cache=True,
        )
        if self.config.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        self._synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            # Otherwise Transformers 4.57 can replace False/1 with checkpoint
            # sampling/beam defaults because they match global default values.
            output = self._model.generate(**inputs, generation_config=settings, use_model_defaults=False)
        self._synchronize()
        elapsed = time.perf_counter() - started
        generated = output[0, input_tokens:].tolist()
        eos = self._eos_token_id if isinstance(self._eos_token_id, list) else [self._eos_token_id]
        stopped = bool(generated) and generated[-1] in eos
        details = {
            "do_sample": False, "num_beams": 1, "use_model_defaults": False,
            "finish_reason": "eos" if stopped else "length",
            "max_new_tokens": cap,
            "peak_cuda_allocated_bytes": (torch.cuda.max_memory_allocated()
                                          if self.config.device == "cuda" else None),
        }
        return Generation(self._tokenizer.decode(generated, skip_special_tokens=True),
                          input_tokens, len(generated), elapsed, details)


def validate_choice_tokens(tokenizer, prompt: str, labels: Sequence[str], vocab_size: int):
    """Validate actual encoding and full rendered-prefix stability before inference."""
    labels = tuple(labels)
    if not labels or any(not isinstance(label, str) or not label for label in labels):
        raise ValueError("nonempty choice labels required")
    prefix = tokenizer.encode(prompt, add_special_tokens=False)
    ids = []
    for label in labels:
        encoded = tokenizer.encode(label, add_special_tokens=False)
        if len(encoded) != 1:
            raise ValueError("choice label must encode as exactly one token")
        token = encoded[0]
        if type(token) is not int or not 0 <= token < vocab_size:
            raise ValueError("choice token outside output vocabulary")
        if token in tokenizer.all_special_ids:
            raise ValueError("choice token is special")
        if token in ids:
            raise ValueError("choice token IDs must be distinct")
        if tokenizer.encode(prompt + label, add_special_tokens=False) != prefix + [token]:
            raise ValueError("choice label is not prefix-stable")
        ids.append(token)
    return tuple(ids)


def restricted_choice(logits, *, labels, token_ids):
    """Pure finite-score arithmetic; ties retain the first supplied candidate."""
    import math

    if not labels or not (len(labels) == len(token_ids) == len(logits)):
        raise ValueError("missing or misaligned choice scores")
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in logits):
        raise ValueError("non-finite or missing candidate logit")
    largest = max(logits)
    weights = [math.exp(x - largest) for x in logits]
    total = sum(weights)
    selected = logits.index(largest)
    return selected, [w / total for w in weights]
