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
        head_dim=16, max_position_embeddings=8192,
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


@pytest.mark.parametrize("purpose", ["action", "action_review", "action_repair", "memory", "memory_repair"])
def test_checkpoint_sampling_defaults_cannot_override_greedy_decoding(tiny_adapter, monkeypatch, purpose):
    from copy import deepcopy

    defaults = deepcopy(tiny_adapter._model.generation_config)
    defaults.transformers_version = "4.57.6"
    defaults.do_sample, defaults.num_beams = True, 3
    defaults.temperature, defaults.top_k, defaults.top_p = 0.7, 20, 0.8
    monkeypatch.setattr(tiny_adapter._model, "generation_config", defaults)
    prepare = tiny_adapter._model._prepare_generation_config
    effective = []

    def capture(*args, **kwargs):
        config, model_kwargs = prepare(*args, **kwargs)
        effective.append(config)
        return config, model_kwargs

    monkeypatch.setattr(tiny_adapter._model, "_prepare_generation_config", capture)
    response = tiny_adapter.generate((Message("user", "look around"),), purpose=purpose)
    assert len(effective) == 1
    assert effective[0].do_sample is False
    assert effective[0].num_beams == 1
    assert response.metadata["use_model_defaults"] is False


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


@pytest.mark.parametrize("prompt_version", ["v31"])
def test_actual_adapter_runs_through_simulator_and_checkpoint_audit(tiny_adapter, tmp_path, prompt_version):
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
                             PromptedActor(full_history=True, prompt_version=prompt_version),
                             FullHistoryMemory(), adapter,
                             output_dir=tmp_path)
    assert result["status"] == "completed" and result["usage_complete"]
    assert result["steps"] == result["budget_spent"] == 1
    assert result["input_tokens"] > 0 and result["output_tokens"] > 0
    report = summarize(tmp_path)
    assert report["logging_checks_passed"] and report["real_infrastructure_errors"] == 0


@pytest.mark.parametrize("strategy", ["prose", "structured"])
@pytest.mark.parametrize("prompt_version", ["v31"])
def test_p1_strategies_use_actual_adapter_tokenizer_and_repair_purposes(tiny_adapter, tmp_path, strategy, prompt_version):
    # Exercise the seam between PR #1 and the inference adapter with random
    # local weights. This does not evaluate production Qwen memory quality.
    from dataclasses import replace
    import json
    from game_memory.actor import PromptedActor
    from game_memory.environment import CookingWorldEnvironment
    from game_memory.memory import ProseMemory, StructuredMemory
    from game_memory.runner import EpisodeConfig, run_episode

    factories = {"prose": ProseMemory, "structured": StructuredMemory}
    adapter = TransformersModel(replace(tiny_adapter.config, context_limit=4096))
    memory = factories[strategy]()
    with CookingWorldEnvironment(action_budget=1) as env:
        result = run_episode(EpisodeConfig(strategy=strategy, action_budget=1), env,
                             PromptedActor(prompt_version=prompt_version), memory, adapter, output_dir=tmp_path)
    assert result["status"] == "completed" and result["usage_complete"]
    assert result["usage_by_purpose"]["memory"]["calls"] == 1
    events = [json.loads(line) for line in
              (tmp_path / result["episode_id"] / "events.jsonl").read_text().splitlines()]
    update = next(event for event in events if event["event"] == "memory_update")
    assert update["memory_tokens"] == adapter.count_tokens(update["memory"]) <= 256
    replies = [event for event in events if event["event"] == "model_response"]
    assert result["input_tokens"] == sum(event["input_tokens"] for event in replies)
    assert result["output_tokens"] == sum(event["output_tokens"] for event in replies)


@pytest.mark.parametrize("strategy", ["prose", "structured"])
def test_real_inference_cli_runs_bounded_memory_and_audits_isolation(tiny_adapter, tmp_path, strategy):
    from dataclasses import replace
    import json
    from game_memory.run_episode import main
    from game_memory.summarize_diagnostics import summarize

    adapter = TransformersModel(replace(tiny_adapter.config, context_limit=8192))
    output = tmp_path / strategy
    assert main([
        "--protocol-id", "software-fixture", "--backend", "transformers", "--strategy", strategy, "--actor-prompt", "v31",
        "--model-revision", adapter.config.revision, "--action-budget", "1",
        "--num-locations", "1", "--num-ingredients", "1", "--output-dir", str(output),
    ], model=adapter) == 0
    result = json.loads(next(output.glob("*/result.json")).read_text())
    assert result["kind"] == "development"
    assert result["components"]["memory"]["is_fake"] is False
    manifest = json.loads((output / "pilot-manifest.json").read_text())
    assert manifest["memory"] == result["components"]["memory"]
    assert manifest["source"] == result["source"]
    assert manifest["protocol_id"] == result["protocol_id"] == "software-fixture"
    assert result["usage_by_purpose"]["memory"]["calls"] == 1
    report = summarize(output)
    assert report["kind"] == "bounded_memory_checkpoint_report"
    assert report["logging_checks_passed"] and report["real_infrastructure_errors"] == 0


def test_real_test_fold_episode_is_labeled_evaluation_and_audited(tiny_adapter, tmp_path):
    from dataclasses import replace
    import json
    from game_memory.run_episode import main
    from game_memory.summarize_diagnostics import summarize

    adapter = TransformersModel(replace(tiny_adapter.config, context_limit=8192))
    assert main(["--protocol-id", "software-fixture", "--strategy", "structured", "--actor-prompt", "v31",
                 "--game-fold", "test", "--action-budget", "1",
                 "--num-locations", "1", "--num-ingredients", "1",
                 "--output-dir", str(tmp_path)], model=adapter) == 0
    result = json.loads(next(tmp_path.glob("*/result.json")).read_text())
    assert result["kind"] == "evaluation"
    assert summarize(tmp_path)["logging_checks_passed"]


def test_legal_choice_one_forward_restricted_argmax_and_exact_hash(tiny_adapter, monkeypatch):
    import hashlib
    import json
    import torch
    from types import SimpleNamespace
    from game_memory.transformers_model import validate_choice_tokens

    messages = (Message('user', '  café ☃\n  '),)
    prompt = tiny_adapter._tokenizer.apply_chat_template(
        [{'role': m.role, 'content': m.content} for m in messages],
        tokenize=False, add_generation_prompt=True)
    vocab = tiny_adapter._model.get_output_embeddings().weight.shape[0]
    ids = validate_choice_tokens(tiny_adapter._tokenizer, prompt, ('A', 'B'), vocab)
    seen, forwards = [], []
    original = tiny_adapter._tokenizer.__class__.__call__
    def capture(tokenizer, text, **kwargs):
        if tokenizer is tiny_adapter._tokenizer:
            seen.append((text, kwargs))
        return original(tokenizer, text, **kwargs)
    monkeypatch.setattr(tiny_adapter._tokenizer.__class__, '__call__', capture)
    def forward(**kwargs):
        assert torch.is_inference_mode_enabled() is True
        assert torch.is_grad_enabled() is False
        forwards.append(kwargs)
        logits = torch.zeros((1, kwargs['input_ids'].shape[1], vocab))
        noncandidate = next(i for i in range(vocab) if i not in ids)
        logits[0, -1, noncandidate] = 1000
        logits[0, -1, ids[0]] = 1
        logits[0, -1, ids[1]] = 2
        return SimpleNamespace(logits=logits)
    def forbidden(*args, **kwargs):
        pytest.fail('score_choices must never call generate')
    monkeypatch.setattr(tiny_adapter._model, 'forward', forward)
    monkeypatch.setattr(tiny_adapter._model, 'generate', forbidden)
    result = tiny_adapter.score_choices(messages, labels=('A', 'B'))
    assert result.text == 'B' and result.output_tokens == 1
    assert len(forwards) == 1 and forwards[0]['use_cache'] is False
    assert seen == [(prompt, {'add_special_tokens': False, 'return_tensors': 'pt',
                             'return_token_type_ids': False, 'truncation': False})]
    m = result.metadata
    assert m['special_token_ids'] == sorted(set(tiny_adapter._tokenizer.all_special_ids))
    assert set(ids).isdisjoint(m['special_token_ids'])
    assert m['candidate_logits'] == [1.0, 2.0]
    assert sum(m['conditional_probabilities']) == pytest.approx(1)
    assert m['rendered_prompt_sha256'] == hashlib.sha256(prompt.encode()).hexdigest()
    assert m['rendered_prompt_sha256'] != hashlib.sha256(json.dumps(
        [{'role': x.role, 'content': x.content} for x in messages]).encode()).hexdigest()
    assert m['rendered_prompt_sha256'] != hashlib.sha256(messages[0].content.encode()).hexdigest()
    assert m['prompt_hash_evidence'] == 'actual_rendered_prompt'
    assert prompt.endswith('assistant\n') and '  café ☃\n  ' in prompt


@pytest.mark.parametrize('failure', ['missing', 'shape', 'nan', 'infinity', 'tie'])
def test_legal_choice_forward_scores_fail_visibly_or_tie_first(tiny_adapter, monkeypatch, failure):
    import torch
    from types import SimpleNamespace
    def forward(**kwargs):
        if failure == 'missing': return SimpleNamespace()
        vocab = tiny_adapter._model.get_output_embeddings().weight.shape[0]
        shape = (1, kwargs['input_ids'].shape[1], vocab)
        logits = torch.zeros(shape if failure != 'shape' else (1, vocab))
        if failure in {'nan', 'infinity'}:
            logits[:] = float('nan' if failure == 'nan' else 'inf')
        return SimpleNamespace(logits=logits)
    monkeypatch.setattr(tiny_adapter._model, 'forward', forward)
    if failure == 'tie':
        result = tiny_adapter.score_choices((Message('user', 'choose'),), labels=('B', 'A'))
        assert result.text == 'B' and result.metadata['conditional_probabilities'] == [0.5, 0.5]
    else:
        with pytest.raises(ValueError):
            tiny_adapter.score_choices((Message('user', 'choose'),), labels=('A', 'B'))


def test_legal_choice_actual_tiny_forward_and_context_guard(tiny_adapter, monkeypatch):
    response = tiny_adapter.score_choices((Message('user', 'choose'),), labels=('A', 'B'))
    assert response.input_tokens > 0 and response.elapsed_seconds > 0
    assert response.metadata['scoring_evidence'] == 'actual_model_forward'
    def forbidden(**kwargs):
        pytest.fail('overflow reached inference')
    monkeypatch.setattr(tiny_adapter._model, 'forward', forbidden)
    with pytest.raises(ValueError, match='prompt was not truncated'):
        tiny_adapter.score_choices((Message('user', 'x '*200),), labels=('A', 'B'))


def test_cached_qwen_tokenizer_only_all_52_legal_labels():
    # Never loads weights; missing cache/dependencies is unexecuted verification.
    transformers = pytest.importorskip('transformers', reason='actual cached-tokenizer verification unexecuted: dependency unavailable')
    from game_memory.choice_actor import LegalChoiceActor
    from game_memory.contracts import AgentView
    from game_memory.integration_fixtures import FakeModel
    from game_memory.transformers_model import validate_choice_tokens
    try:
        tokenizer = transformers.AutoTokenizer.from_pretrained(
            'Qwen/Qwen3-4B-Instruct-2507', revision='cdbee75f17c01a7cc42f958dc650907174af0554',
            local_files_only=True, trust_remote_code=False)
    except OSError:
        pytest.skip('actual cached-tokenizer verification unexecuted: pinned tokenizer cache unavailable')
    class Capture(FakeModel):
        def score_choices(self, messages, *, labels):
            self.messages, self.labels = messages, labels
            return super().score_choices(messages, labels=labels)
    capture = Capture()
    LegalChoiceActor().choose_action(AgentView('Room café', 'Prepare and eat meal',
        tuple(f'public action {i}' for i in range(52)), 80, 2),
        '[{"action": "[INITIAL_OBSERVATION]", "observation": "Recipe ☃"}]', capture)
    prompt = tokenizer.apply_chat_template([{'role': m.role, 'content': m.content} for m in capture.messages],
                                           tokenize=False, add_generation_prompt=True)
    config = transformers.AutoConfig.from_pretrained(
        'Qwen/Qwen3-4B-Instruct-2507', revision='cdbee75f17c01a7cc42f958dc650907174af0554',
        local_files_only=True, trust_remote_code=False)
    ids = validate_choice_tokens(tokenizer, prompt, capture.labels, config.vocab_size)
    assert len(ids) == len(set(ids)) == 52
