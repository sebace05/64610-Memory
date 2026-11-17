"""Offline legal-choice tests: no Java, pretrained weights, or network."""
from dataclasses import asdict, replace
import json
import math

import pytest

from game_memory.actor import build_v31_action_messages
from game_memory.choice_actor import FOOTER, LABELS, LegalChoiceActor
from game_memory.components import Generation
from game_memory.contracts import AgentView, Transition
from game_memory.diagnostics import FullHistoryMemory
from game_memory.integration_fixtures import FakeModel
from game_memory.runner import EpisodeConfig, _LoggedModel, run_episode
from game_memory.summarize_diagnostics import summarize
from game_memory.transformers_model import restricted_choice, validate_choice_tokens


def view(actions=("put meal in trash", "eat meal")):
    return AgentView('Room café\n"☃"', 'Eat meal', actions, 2, 2)


class Script(FakeModel):
    def __init__(self, label):
        super().__init__()
        self.label = label
        self.calls = []

    def score_choices(self, messages, *, labels):
        self.calls.append((tuple(messages), tuple(labels)))
        result = super().score_choices(messages, labels=labels)
        return replace(result, text=self.label)


def test_exact_prompt_mapping_boundary_and_no_semantic_rescue():
    actions = tuple(f"command {i} ☃" for i in range(52))
    public, history = view(actions), ' literal history\n"café"\n'
    model = Script('a')
    assert LegalChoiceActor().choose_action(public, history, model) == actions[26]
    (messages, labels), = model.calls
    baseline = build_v31_action_messages(public, history, full_history=True)
    assert labels == tuple(LABELS)
    assert messages[0].content == baseline[0].content.replace(
        'Return JSON with next_direction, missing_prerequisite, action.',
        'Return only the label of one listed legal action option, with no other text.')
    assert messages[1].content == baseline[1].content + FOOTER + json.dumps(
        [{"label": l, "action": a} for l, a in zip(LABELS, actions)], ensure_ascii=False, sort_keys=True)
    assert json.loads(messages[1].content.split(FOOTER)[1])[25:27] == [
        {"label": "Z", "action": actions[25]}, {"label": "a", "action": actions[26]}]
    # A damaging legal action is returned verbatim even with eat meal available.
    assert LegalChoiceActor().choose_action(view(), 'Prepared meal available', Script('A')) == 'put meal in trash'


@pytest.mark.parametrize('actions', [(), ('',), (None,), (1,), ('x', 'x'), tuple(map(str, range(53)))])
def test_bad_actions_fail_before_scoring(actions):
    model = Script('A')
    with pytest.raises(ValueError):
        LegalChoiceActor().choose_action(view(actions), '', model)
    assert not model.calls


@pytest.mark.parametrize('label', [' A', 'A\n', 'a', '"A"', '{"label":"A"}', '', 'Answer: A'])
def test_exact_labels_only_no_repairs(label):
    model = Script(label)
    with pytest.raises(ValueError, match='unexpected exact label'):
        LegalChoiceActor().choose_action(view(), '', model)
    assert len(model.calls) == 1


def test_stateless_across_turns_episodes_and_sentence_guard(monkeypatch):
    actor, model = LegalChoiceActor(), Script('A')
    actor.choose_action(view(), 'first secret', model)
    actor.choose_action(view(('new action',)), 'new history', model)
    assert 'first secret' not in model.calls[-1][0][1].content
    assert 'put meal in trash' not in model.calls[-1][0][1].content
    import game_memory.choice_actor as module
    original = module.build_v31_action_messages
    def changed(*args, **kwargs):
        system, user = original(*args, **kwargs)
        return replace(system, content=system.content * 2), user
    monkeypatch.setattr(module, 'build_v31_action_messages', changed)
    with pytest.raises(ValueError, match='exactly one'):
        actor.choose_action(view(), '', model)
    assert len(model.calls) == 2


class Tokenizer:
    all_special_ids = [9]
    def encode(self, text, *, add_special_tokens):
        assert add_special_tokens is False
        return {'P': [0], 'A': [1], 'B': [2], 'PA': [0, 1], 'PB': [0, 2]}[text]


def test_token_validation_and_stable_softmax_ties():
    assert validate_choice_tokens(Tokenizer(), 'P', ('A', 'B'), 10) == (1, 2)
    i, p = restricted_choice([10000.0, 10000.0], labels=['A', 'B'], token_ids=[1, 2])
    assert i == 0 and p == [0.5, 0.5]
    i, p = restricted_choice([-10000.0, -9999.0], labels=['A', 'B'], token_ids=[1, 2])
    assert i == 1 and math.isclose(sum(p), 1) and math.isclose(p[1], 1/(1+math.exp(-1)))


@pytest.mark.parametrize('kind', ['multi', 'duplicate', 'special', 'range', 'unstable'])
def test_tokenizer_rejects_invalid_encodings(kind):
    class Bad(Tokenizer):
        def encode(self, text, **kwargs):
            if text == 'B':
                return {'multi': [2, 3], 'duplicate': [1], 'special': [9], 'range': [10], 'unstable': [2]}[kind]
            if text == 'PB' and kind == 'unstable':
                return [3]
            return super().encode(text, **kwargs)
    with pytest.raises(ValueError):
        validate_choice_tokens(Bad(), 'P', ('A', 'B'), 10)


@pytest.mark.parametrize('scores', [[], [1], [None, 1], [float('nan'), 1], [1, float('inf')]])
def test_missing_nonfinite_or_misaligned_scores_are_rejected(scores):
    with pytest.raises(ValueError):
        restricted_choice(scores, labels=['A', 'B'], token_ids=[1, 2])


class StubEnvironment:
    recheck_cost = 2
    action_budget = 2
    metadata = {'is_fake': True}
    steps = budget_spent = recipe_rechecks = 0

    def reset(self, seed, config):
        self.steps = self.budget_spent = self.recipe_rechecks = 0
        return view(('put meal in trash', 'eat meal'))

    def step(self, action):
        self.steps += 1
        self.budget_spent += 1
        done = self.steps == 2
        public = replace(view(), observation='Visible feedback', budget_remaining=2-self.steps,
                         allowed_actions=() if done else view().allowed_actions)
        return Transition(public, action, 1, True, True, False, 0, 0, 0, False, False,
                          False, done, 'budget_exhaustion' if done else None)


def episode(tmp_path, model=None):
    result = run_episode(EpisodeConfig(strategy='full_history', action_budget=2), StubEnvironment(),
                         LegalChoiceActor(), FullHistoryMemory(), model or FakeModel(), output_dir=tmp_path)
    directory = tmp_path / result['episode_id']
    events = [json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
    return result, events, directory


def test_stub_game_loss_history_usage_and_audit(tmp_path):
    result, events, _ = episode(tmp_path)
    assert result['status'] == 'completed' and result['success'] is False
    assert result['usage_by_purpose']['action']['calls'] == result['output_tokens'] == 2
    assert result['model_elapsed_seconds'] == 0 and result['usage_complete']
    requests = [e for e in events if e['event'] == 'model_request']
    assert len(requests) == 2 and all(e['purpose'] == 'action' for e in requests)
    history = requests[-1]['messages'][1]['content']
    assert '"action": "put meal in trash"' in history
    report = summarize(tmp_path, include_fixtures=True)
    assert report['logging_checks_passed'], report['issues']
    assert not report['real_model_capability_tested']
    assert report['episodes'][0]['legality_guaranteed_by_interface'] is True
    assert report['episodes'][0]['behavior']['action_output_validation']['action'] == {'choice': 2}


def test_request_precedes_scoring_partial_failure_preserves_usage_and_error(tmp_path):
    class Fails(FakeModel):
        calls = 0
        def score_choices(self, messages, *, labels):
            records = [json.loads(s) for s in next(tmp_path.glob('*/events.jsonl')).read_text().splitlines()]
            assert records[-1]['event'] == 'model_request'
            assert records[-1]['labels'] == list(labels)
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError('scripted scorer failure')
            return super().score_choices(messages, labels=labels)
    result, events, _ = episode(tmp_path, Fails())
    assert result['status'] == 'error' and result['success'] is None
    assert result['output_tokens'] == result['usage_by_purpose']['action']['calls'] == 1
    assert not result['usage_complete']
    assert [e['event'] for e in events][-3:] == ['model_error', 'episode_error', 'episode_end']
    report = summarize(tmp_path, include_fixtures=True)
    assert report['logging_checks_passed'], report['issues']


def test_logged_scorer_rethrows_and_rejects_wrong_return():
    events = []
    class Wrong(FakeModel):
        def score_choices(self, messages, *, labels):
            return 'A'
    logged = _LoggedModel(Wrong(), lambda event, **kw: events.append((event, kw)), lambda: 1)
    with pytest.raises(TypeError):
        logged.score_choices((), labels=('A',))
    assert [e for e, _ in events] == ['model_request', 'model_error']
    assert not logged.usage_complete and logged.by_purpose == {}


@pytest.mark.parametrize('corruption', ['map', 'order', 'history', 'hidden', 'request_label', 'response_label',
    'scores', 'probabilities', 'ids', 'action', 'duplicate_request', 'duplicate_response', 'sequence',
    'fake_hash', 'fake_actual', 'review', 'decision_tokens', 'latency', 'tie'])
def test_independent_audit_rejects_tampering(tmp_path, corruption):
    result, events, directory = episode(tmp_path)
    request = next(e for e in events if e['event'] == 'model_request')
    response = next(e for e in events if e['event'] == 'model_response')
    action = next(e for e in events if e['event'] == 'action')
    if corruption in {'map', 'order', 'hidden'}:
        prefix, options = request['messages'][1]['content'].rsplit(FOOTER, 1)
        options = json.loads(options)
        if corruption == 'map': options[0]['action'] = 'invented action'
        if corruption == 'order': options.reverse()
        if corruption == 'hidden': options[0]['expected_action'] = True
        request['messages'][1]['content'] = prefix + FOOTER + json.dumps(options, ensure_ascii=False, sort_keys=True)
    elif corruption == 'history': request['messages'][1]['content'] += 'stale extra annotation'
    elif corruption == 'request_label': request['labels'].reverse()
    elif corruption == 'response_label': response['text'] = 'B'
    elif corruption == 'scores': response['metadata']['candidate_logits'] = [None, 0]
    elif corruption == 'probabilities': response['metadata']['conditional_probabilities'] = [0.9, 0.1]
    elif corruption == 'ids': response['metadata']['label_token_ids'] = [0, 0]
    elif corruption == 'action': action['transition']['action'] = 'eat meal'
    elif corruption == 'duplicate_request': events.insert(events.index(request), dict(request))
    elif corruption == 'duplicate_response': events.insert(events.index(response), dict(response))
    elif corruption == 'sequence': events[2]['sequence'] = 999
    elif corruption == 'fake_hash': response['metadata']['rendered_prompt_sha256'] = 'a'*64
    elif corruption == 'fake_actual': response['metadata']['scoring_evidence'] = 'actual_model_forward'
    elif corruption == 'review': request['purpose'] = response['purpose'] = 'action_review'
    elif corruption == 'decision_tokens': response['metadata']['decision_token_count'] = 2
    elif corruption == 'latency': result['usage_by_purpose']['action']['elapsed_seconds'] = 1
    elif corruption == 'tie':
        response['text'] = response['metadata']['selected_label'] = 'B'
        response['metadata']['selected_token_id'] = 1
    if corruption != 'sequence':
        for i, e in enumerate(events): e['sequence'] = i
    (directory/'result.json').write_text(json.dumps(result))
    (directory/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
    assert not summarize(tmp_path, include_fixtures=True)['logging_checks_passed']


@pytest.mark.parametrize('mode', ['winner', 'tie', 'shape', 'missing', 'nan', 'overflow'])
def test_adapter_scoring_path_with_scripted_tensors_without_torch(tmp_path, monkeypatch, mode):
    """Exercise orchestration offline; these tensors are not model measurements."""
    import contextlib
    import hashlib
    import sys
    from types import SimpleNamespace
    from game_memory.components import Message
    from game_memory.transformers_model import TransformersConfig, TransformersModel

    prompt = '  café ☃\nassistant\n'
    class Input:
        shape = (1, 2)
        def __getitem__(self, key): return self
        def tolist(self): return [0, 3]
    class Batch(dict):
        def to(self, device):
            assert device == 'cpu'
            return self
    class Tokens:
        all_special_ids = [9]
        def apply_chat_template(self, messages, **kwargs):
            assert kwargs == {'tokenize': False, 'add_generation_prompt': True}
            return prompt
        def encode(self, text, **kwargs):
            assert kwargs == {'add_special_tokens': False}
            return {prompt: [0, 3], 'A': [1], 'B': [2], prompt+'A': [0, 3, 1], prompt+'B': [0, 3, 2]}[text]
        def __call__(self, text, **kwargs):
            assert text == prompt and kwargs['truncation'] is False
            assert kwargs['add_special_tokens'] is False
            return Batch(input_ids=Input())
    class Scores:
        shape = (1, 10) if mode == 'shape' else (1, 2, 10)
        def __getitem__(self, key):
            # Noncandidate token 7 has the largest score but cannot be selected.
            assert key == (0, -1, [1, 2])
            self.values = [float('nan'), 2] if mode == 'nan' else ([1, 1] if mode == 'tie' else [1, 2])
            return self
        def float(self): return self
        def cpu(self): return self
        def tolist(self): return self.values
    class Backend:
        calls = 0
        def get_output_embeddings(self): return SimpleNamespace(weight=SimpleNamespace(shape=(10, 4)))
        def __call__(self, **kwargs):
            assert kwargs['use_cache'] is False and set(kwargs) == {'input_ids', 'use_cache'}
            self.calls += 1
            return SimpleNamespace() if mode == 'missing' else SimpleNamespace(logits=Scores())
        def generate(self, **kwargs): pytest.fail('generate called')
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(inference_mode=contextlib.nullcontext))
    adapter = TransformersModel.__new__(TransformersModel)
    adapter.config = TransformersConfig(revision='0'*40, device='cpu', dtype='float32')
    adapter._tokenizer, adapter._model = Tokens(), Backend()
    adapter._context_limit = 2 if mode == 'overflow' else 100
    messages = (Message('user', 'untemplated content'),)
    if mode in {'shape', 'missing', 'nan', 'overflow'}:
        with pytest.raises(ValueError): adapter.score_choices(messages, labels=('A', 'B'))
        assert adapter._model.calls == (0 if mode == 'overflow' else 1)
    else:
        result = adapter.score_choices(messages, labels=('A', 'B'))
        assert adapter._model.calls == 1
        assert result.text == ('A' if mode == 'tie' else 'B')
        assert result.input_tokens == 2 and result.output_tokens == 1
        assert result.metadata['special_token_ids'] == [9]
        assert result.metadata['rendered_prompt_sha256'] == hashlib.sha256(prompt.encode()).hexdigest()
        assert result.metadata['rendered_prompt_sha256'] != hashlib.sha256(messages[0].content.encode()).hexdigest()


@pytest.mark.parametrize('corruption', ['system', 'retry', 'duplicate_end', 'real_fixture_hash'])
def test_choice_audit_strict_identity_sequence_and_real_evidence(tmp_path, corruption):
    result, events, directory = episode(tmp_path)
    request = next(e for e in events if e['event'] == 'model_request')
    if corruption == 'system':
        request['messages'][0]['content'] += ' Hidden oracle fact.'
    elif corruption == 'retry':
        # A complete additional request/response pair in the same step is still
        # invalid even if aggregate accounting is adjusted to match it.
        from copy import deepcopy
        response = next(e for e in events if e['event'] == 'model_response')
        pair = [deepcopy(request), deepcopy(response)]
        events[events.index(response)+1:events.index(response)+1] = pair
        result['input_tokens'] += response['input_tokens']
        result['output_tokens'] += 1
        result['usage_by_purpose']['action']['calls'] += 1
        result['usage_by_purpose']['action']['input_tokens'] += response['input_tokens']
        result['usage_by_purpose']['action']['output_tokens'] += 1
    elif corruption == 'duplicate_end':
        events.append(dict(events[-1]))
    else:
        # Null fixture hash evidence may never be adopted as actual evidence.
        result['components']['model']['is_fake'] = False
        result['kind'] = 'full_history_diagnostic'
        events[0]['components']['model']['is_fake'] = False
        events[0]['kind'] = 'full_history_diagnostic'
    for i, e in enumerate(events): e['sequence'] = i
    (directory/'result.json').write_text(json.dumps(result))
    events[-1]['result'] = result
    (directory/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
    assert not summarize(tmp_path, include_fixtures=True)['logging_checks_passed']


def rejected_count_episode(tmp_path):
    class BadCount(FakeModel):
        def __init__(self):
            super().__init__()
            self.returned = []

        def score_choices(self, messages, *, labels):
            response = super().score_choices(messages, labels=labels)
            if self.returned:
                response = replace(response, output_tokens=2)
            self.returned.append(response)
            return response

    model = BadCount()
    result, events, directory = episode(tmp_path, model)
    return result, events, directory, model.returned


def write_trace(directory, result, events):
    for index, event in enumerate(events):
        event['sequence'] = index
    events[-1]['result'] = result
    (directory/'result.json').write_text(json.dumps(result))
    (directory/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))


def test_returned_bad_count_preserves_responses_usage_and_stops(tmp_path):
    from dataclasses import asdict
    result, events, _, returned = rejected_count_episode(tmp_path)
    responses = [e for e in events if e['event'] == 'model_response']
    assert len(responses) == len(returned) == 2
    for event, response in zip(responses, returned):
        assert {key: event[key] for key in asdict(response)} == asdict(response)
    assert [e['output_tokens'] for e in responses] == [1, 2]
    assert result['status'] == 'error'
    assert result['success'] is result['failure'] is None
    assert result['termination_reason'] == 'infrastructure_error'
    assert result['usage_complete'] is True
    assert result['output_tokens'] == 3
    assert result['input_tokens'] == sum(r.input_tokens for r in returned)
    assert result['model_elapsed_seconds'] == sum(r.elapsed_seconds for r in returned)
    assert result['usage_by_purpose'] == {'action': {
        'calls': 2, 'input_tokens': result['input_tokens'], 'output_tokens': 3,
        'elapsed_seconds': result['model_elapsed_seconds']}}
    assert [e['event'] for e in events][-4:] == [
        'model_request', 'model_response', 'episode_error', 'episode_end']
    assert sum(e['event'] == 'action' for e in events) == result['steps'] == 1
    assert len([e for e in events if e['event'] == 'model_request']) == 2
    report = summarize(tmp_path, include_fixtures=True)
    assert report['logging_checks_passed'], report['issues']


@pytest.mark.parametrize('tamper', ['completed', 'error', 'action'])
def test_bad_count_failure_audit_rejects_tampering(tmp_path, tamper):
    from copy import deepcopy
    result, events, directory, _ = rejected_count_episode(tmp_path)
    if tamper == 'completed':
        result['status'] = 'completed'
    elif tamper == 'error':
        result['error']['error_message'] = 'different error'
        events[-2]['error_message'] = 'different error'
    else:
        action = deepcopy(next(e for e in events if e['event'] == 'action'))
        action['step'] = 2
        action['memory_before_action'] = next(
            e['memory'] for e in reversed(events) if e['event'] == 'memory_update')
        action['transition']['view']['budget_remaining'] = 0
        events.insert(len(events)-2, action)
        # Keep generic action/cost accounting consistent to isolate choice audit.
        result['steps'] += 1
        result['budget_spent'] += action['transition']['action_cost']
    write_trace(directory, result, events)
    report = summarize(tmp_path, include_fixtures=True)
    assert not report['logging_checks_passed']
    assert 'choice' in str(report['issues'])


def test_choice_audit_rejects_consistent_nonmodel_error_continuation(tmp_path):
    result, events, directory = episode(tmp_path)
    error = {'phase': 'memory_update', 'error_type': 'RuntimeError',
             'error_message': 'non-model error'}
    # The rest of this valid two-turn game remains present, with correct totals,
    # sequences, result identity and final error record.
    later = next(i for i, e in enumerate(events)
                 if e['event'] == 'model_request' and e['step'] == 2)
    events.insert(later, {'event': 'episode_error', 'step': 1, **error})
    result.update(status='error', success=None, failure=None, error=error,
                  termination_reason='infrastructure_error')
    write_trace(directory, result, events)
    report = summarize(tmp_path, include_fixtures=True)
    assert not report['logging_checks_passed']
    assert 'choice trace continues after episode_error' in str(report['issues'])


@pytest.mark.parametrize('inventory', [[], [9], [0], None, 'missing', [9, 9],
                                      [9, 8], [-1], [True], [1.5], '9'])
def test_actual_evidence_inventory_audit_with_synthetic_records(tmp_path, inventory):
    from game_memory.summarize_diagnostics import audit_legal_choices
    result, events, _ = episode(tmp_path)
    # Synthetic records exercise the actual-evidence validation branch only.
    # This does not load Qwen or verify an actual tokenizer inventory or forward.
    result['components']['model']['is_fake'] = False
    for event in events:
        if event['event'] == 'model_response':
            m = event['metadata']
            m.update(scoring_evidence='actual_model_forward',
                     prompt_hash_evidence='actual_rendered_prompt',
                     rendered_prompt_sha256='a'*64, output_vocab_size=10,
                     latency_scope='synchronized_forward_excludes_tokenization_validation_transfer_cpu_selection')
            if inventory != 'missing':
                m['special_token_ids'] = inventory
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    if inventory in ([], [9]):
        audit_legal_choices(events, result, require)
    else:
        with pytest.raises(ValueError, match='special.token'):
            audit_legal_choices(events, result, require)
