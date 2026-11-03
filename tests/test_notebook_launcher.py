"""Notebook forwards the policy choice and rejects mixed/duplicate pilot runs."""

import ast
import json
from pathlib import Path

import pytest


class Commands:
    def __init__(self):
        self.runs = []

    def check_output(self, *args, **kwargs):
        return "a" * 40 + "\n"

    def run(self, command, **kwargs):
        self.runs.append(command)


@pytest.fixture
def launcher(tmp_path):
    root = Path(__file__).resolve().parents[1]
    notebook = json.loads((root / "notebooks/qwen_colab.ipynb").read_text())
    function = next(n for cell in notebook["cells"] if cell["cell_type"] == "code"
                    for n in ast.parse("".join(cell["source"])).body
                    if isinstance(n, ast.FunctionDef) and n.name == "run_diagnostic")
    commands = Commands()
    ns = dict(json=json, PILOT_DIR=tmp_path, REPO_DIR=root, subprocess=commands, PYTHON="python",
              ENV={}, MODEL_ID="model", MODEL_REVISION="b" * 40, DTYPE="float16",
              RECHECK_COST=2, ACTION_BUDGET=80, CONTEXT_LIMIT=8192,
              ACTION_MAX_NEW_TOKENS=128, GENERATION_SEED=0, ACTOR_PROMPT="v2")
    manifest = dict(source_commit="a" * 40, model_id="model", model_revision="b" * 40,
                    dtype="float16", recheck_cost=2, action_budget=80, context_limit=8192,
                    action_max_new_tokens=128, generation_seed=0, actor_prompt="v2")
    (tmp_path / "pilot-manifest.json").write_text(json.dumps(manifest))
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<notebook-launcher>", "exec"), ns)
    return ns, commands


def test_launcher_passes_recorded_actor_prompt_to_cli(launcher):
    ns, commands = launcher
    ns["run_diagnostic"]([0])
    command = commands.runs[0]
    assert command[command.index("--actor-prompt") + 1] == "v2"
    assert command[command.index("--model-revision") + 1] == "b" * 40


@pytest.mark.parametrize("field,value", [("ACTOR_PROMPT", "v1"), ("DTYPE", "bfloat16"),
                                        ("ACTION_BUDGET", 100)])
def test_launcher_refuses_changed_settings_before_inference(launcher, field, value):
    ns, commands = launcher
    ns[field] = value
    with pytest.raises(RuntimeError, match="Pilot settings changed"):
        ns["run_diagnostic"]([0])
    assert not commands.runs


@pytest.mark.parametrize("partial", [False, True])
def test_launcher_preserves_existing_and_partial_attempts(launcher, partial):
    ns, commands = launcher
    directory = ns["PILOT_DIR"] / "attempt"
    directory.mkdir()
    if partial:
        (directory / "events.jsonl").write_text('{}\n')
    else:
        (directory / "result.json").write_text('{"config":{"seed":0}}')
    with pytest.raises(RuntimeError):
        ns["run_diagnostic"]([0])
    assert not commands.runs
