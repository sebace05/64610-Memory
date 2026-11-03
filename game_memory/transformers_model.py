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


class TransformersModel:
    """Load once, generate greedily, and account for actual prompt/output tokens."""

    def __init__(self, config: TransformersConfig) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.config = config
        if config.device == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA is unavailable; select a GPU runtime before loading Qwen")
            if config.dtype == "bfloat16" and not torch.cuda.is_bf16_supported():
                raise RuntimeError("GPU does not support BF16; explicitly select float16")
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
            "do_sample": False, "num_beams": 1, "attention_implementation": "sdpa",
            "torch_version": version("torch"), "transformers_version": version("transformers"),
            "tokenizers_version": version("tokenizers"),
            "safetensors_version": version("safetensors"),
            "huggingface_hub_version": version("huggingface-hub"),
            "python_version": platform.python_version(),
            "cuda_version": torch.version.cuda,
            "gpu": torch.cuda.get_device_name() if config.device == "cuda" else None,
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

    def generate(self, messages: Sequence[Message], *, purpose: str) -> Generation:
        import torch
        from transformers import GenerationConfig

        if purpose not in {"action", "action_repair", "memory", "memory_repair"}:
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
            output = self._model.generate(**inputs, generation_config=settings)
        self._synchronize()
        elapsed = time.perf_counter() - started
        generated = output[0, input_tokens:].tolist()
        eos = self._eos_token_id if isinstance(self._eos_token_id, list) else [self._eos_token_id]
        stopped = bool(generated) and generated[-1] in eos
        details = {
            "finish_reason": "eos" if stopped else "length",
            "max_new_tokens": cap,
            "peak_cuda_allocated_bytes": (torch.cuda.max_memory_allocated()
                                          if self.config.device == "cuda" else None),
        }
        return Generation(self._tokenizer.decode(generated, skip_special_tokens=True),
                          input_tokens, len(generated), elapsed, details)
