"""Offline adapter validation; tiny random weights do not test Qwen capability."""

import pytest

from game_memory.components import Message
from game_memory.transformers_model import TransformersConfig, TransformersModel


@pytest.mark.parametrize("changes", [
    {"revision": "main"}, {"context_limit": 0}, {"action_max_new_tokens": -1},
    {"generation_seed": -1}, {"device": "cpu", "dtype": "float16"},
])
def test_invalid_inference_configuration_is_rejected(changes):
    settings = {"revision": "0" * 40, **changes}
    with pytest.raises(ValueError):
        TransformersConfig(**settings)


@pytest.fixture(scope="module")
def tiny_adapter(tmp_path_factory):
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers

    torch.set_num_threads(1)
    torch.manual_seed(19)
    directory = tmp_path_factory.mktemp("random-qwen3-not-research-weights")
    backend = Tokenizer(models.BPE(unk_token="[UNK]"))
    backend.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    backend.decoder = decoders.ByteLevel()
    backend.train_from_iterator(["Choose one action. look around recipe memory"],
        trainers.BpeTrainer(vocab_size=300, initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
                            special_tokens=["[UNK]", "<|im_end|>", "<|im_start|>"]))
    tokenizer = transformers.PreTrainedTokenizerFast(
        tokenizer_object=backend, unk_token="[UNK]", eos_token="<|im_end|>",
        pad_token="<|im_end|>",
        chat_template="{% for m in messages %}{{ '<|im_start|>' + m['role'] + '\\n' + m['content'] + '<|im_end|>\\n' }}{% endfor %}{% if add_generation_prompt %}{{ '<|im_start|>assistant\\n' }}{% endif %}",
    )
    tokenizer.save_pretrained(directory)
    config = transformers.Qwen3Config(
        vocab_size=len(tokenizer), hidden_size=32, intermediate_size=64,
        num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=1,
        head_dim=16, max_position_embeddings=4096,
        eos_token_id=tokenizer.eos_token_id, pad_token_id=tokenizer.pad_token_id,
    )
    transformers.Qwen3ForCausalLM(config).save_pretrained(directory, safe_serialization=True)
    return TransformersModel(TransformersConfig(
        model_id=str(directory), revision="0" * 40, device="cpu", dtype="float32",
        context_limit=128, action_max_new_tokens=4, memory_max_new_tokens=6,
        local_files_only=True,
    ))


def test_actual_generation_uses_fresh_prompts_and_real_token_counts(tiny_adapter):
    messages = (Message("user", "look around"),)
    first = tiny_adapter.generate(messages, purpose="action")
    tiny_adapter.generate((Message("user", "different evidence"),), purpose="memory")
    repeated = tiny_adapter.generate(messages, purpose="action")
    assert first.text == repeated.text
    assert first.input_tokens == repeated.input_tokens
    assert 0 < first.output_tokens <= 4
    assert first.elapsed_seconds > 0
    assert first.metadata["finish_reason"] in {"eos", "length"}
    assert tiny_adapter.count_tokens("look around") == len(
        tiny_adapter._tokenizer.encode("look around", add_special_tokens=False))
    assert first.input_tokens > tiny_adapter.count_tokens("look around")
    assert tiny_adapter.metadata["revision"] == "0" * 40


def test_prompt_is_not_echoed_and_eos_is_counted(tiny_adapter, monkeypatch):
    import torch
    generated = tiny_adapter._tokenizer.encode("look around", add_special_tokens=False)
    generated.append(tiny_adapter._tokenizer.eos_token_id)

    def controlled_generation(*, input_ids, **kwargs):
        return torch.cat((input_ids, torch.tensor([generated])), dim=1)

    monkeypatch.setattr(tiny_adapter._model, "generate", controlled_generation)
    response = tiny_adapter.generate((Message("user", "DO NOT ECHO THIS PROMPT"),), purpose="action")
    assert response.text == "look around"
    assert response.output_tokens == len(generated)
    assert response.metadata["finish_reason"] == "eos"


def test_context_overflow_fails_without_truncation_or_inference(tiny_adapter, monkeypatch):
    def forbidden(**kwargs):
        pytest.fail("generation must not run after context overflow")

    monkeypatch.setattr(tiny_adapter._model, "generate", forbidden)
    with pytest.raises(ValueError, match="prompt was not truncated"):
        tiny_adapter.generate((Message("user", "x " * 200),), purpose="action")


def test_missing_cuda_fails_before_attempting_model_download(monkeypatch):
    torch = pytest.importorskip("torch")
    pytest.importorskip("transformers")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="CUDA is unavailable"):
        TransformersModel(TransformersConfig(revision="0" * 40))


def test_actual_adapter_runs_through_simulator_and_checkpoint_audit(tiny_adapter, tmp_path):
    # This is end-to-end inference with random local weights, not a production
    # Qwen capability test. A valid game loss must still have auditable usage.
    from dataclasses import replace
    from game_memory.actor import PromptedActor
    from game_memory.diagnostics import FullHistoryMemory
    from game_memory.environment import CookingWorldEnvironment
    from game_memory.runner import EpisodeConfig, run_episode
    from game_memory.summarize_diagnostics import summarize

    adapter = TransformersModel(replace(tiny_adapter.config, context_limit=4096))
    with CookingWorldEnvironment(action_budget=1) as env:
        result = run_episode(EpisodeConfig(strategy="full_history", action_budget=1), env,
                             PromptedActor(full_history=True), FullHistoryMemory(), adapter,
                             output_dir=tmp_path)
    assert result["status"] == "completed" and result["usage_complete"]
    assert result["steps"] == result["budget_spent"] == 1
    assert result["input_tokens"] > 0 and result["output_tokens"] > 0
    report = summarize(tmp_path)
    assert report["logging_checks_passed"] and report["real_infrastructure_errors"] == 0
