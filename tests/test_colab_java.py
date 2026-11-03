"""Reproduce JVM diagnostics corrupting Py4J's numeric-port startup protocol."""

import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


def test_notebook_logging_options_restore_noisy_java_gateway_startup():
    if shutil.which("java") is None:
        pytest.skip("Java runtime is unavailable")
    supported = subprocess.run(["java", "-Xlog:help"], capture_output=True, timeout=10)
    if supported.returncode:
        pytest.skip("regression targets Java 9+ unified logging used by Colab Java 21")
    root = Path(__file__).resolve().parents[1]
    notebook = json.loads((root / "notebooks/qwen_colab.ipynb").read_text())
    assignments = []
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assignments.extend(n for n in ast.parse("".join(cell["source"])).body
                               if isinstance(n, ast.Assign))
    options = next(ast.literal_eval(n.value) for n in assignments
                   if any(isinstance(t, ast.Name) and t.id == "JAVA_GATEWAY_LOG_OPTIONS"
                          for t in n.targets))
    # Deliberately reproduce extra JVM stdout before the port. The existing
    # heap limit must also remain effective after applying the notebook fix.
    base = dict(os.environ, JAVA_TOOL_OPTIONS="-Xmx128m -Xlog:os+container=trace:stdout")
    script = (
        "from game_memory.environment import CookingWorldEnvironment; "
        "e = CookingWorldEnvironment(); e.reset(0); "
        "assert e.view.allowed_actions; print('SIMULATOR_READY'); e.close()"
    )
    broken = subprocess.run([sys.executable, "-c", script], cwd=root, env=base,
                            capture_output=True, text=True, timeout=30)
    assert broken.returncode != 0
    assert "invalid literal for int()" in broken.stderr
    assert "[os,container]" in broken.stderr
    fixed = dict(base, JAVA_TOOL_OPTIONS=base["JAVA_TOOL_OPTIONS"] + " " + options)
    ready = subprocess.run([sys.executable, "-c", script], cwd=root, env=fixed,
                           capture_output=True, text=True, timeout=30)
    assert ready.returncode == 0, ready.stdout + ready.stderr
    assert ready.stdout.strip() == "SIMULATOR_READY"
