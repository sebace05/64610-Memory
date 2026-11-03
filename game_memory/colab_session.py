"""Keep one model in the isolated Colab Python process between notebook cells.

Only weights/tokenizer are reused. The existing CLI creates fresh episode state
and enforces its manifest guards on every request. No jobs run in the background.
"""

from contextlib import redirect_stdout
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import traceback

from .pilot import runtime_environment
from .runner import source_metadata


class ColabSession:
    def __init__(self, python, repository, model_settings: dict, log_path):
        self.log_path = Path(log_path)
        self._log = self.log_path.open("x")
        self._log.write(json.dumps({"model_settings": model_settings}) + "\n")
        self._log.flush()
        try:
            self.process = subprocess.Popen(
                [str(python), "-u", "-m", "game_memory.colab_session"],
                cwd=repository, env=runtime_environment(), text=True,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log,
            )
        except OSError:
            traceback.print_exc(file=self._log)
            self._log.close()
            raise
        self.ready = self._exchange(model_settings)

    def _exchange(self, request):
        try:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError(f"Model session stopped; inspect {self.log_path}")
            reply = json.loads(line)
            if "error" in reply:
                raise RuntimeError(f"{reply['error']}; inspect {self.log_path}")
            return reply
        except BaseException:
            # An interrupted read cannot be safely paired with the next request.
            self.close()
            raise

    def run(self, arguments):
        reply = self._exchange(list(map(str, arguments)))
        if reply["returncode"]:
            raise RuntimeError(f"Run exited with status {reply['returncode']}; inspect {self.log_path}")
        return reply

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=5)
        self.process.stdout.close()
        self._log.close()


def serve():
    """Small stdin/stdout protocol; all model and CLI output goes to the log."""
    from .run_episode import main
    from .transformers_model import TransformersConfig, TransformersModel

    protocol = sys.stdout

    def reply(value):
        print(json.dumps(value), file=protocol, flush=True)

    def code_snapshot():
        return {p.name: p.read_bytes() for p in Path(__file__).parent.glob("*.py")}

    with redirect_stdout(sys.stderr):
        try:
            config = TransformersConfig(**json.loads(sys.stdin.readline()))
            source = source_metadata()
            code = code_snapshot()
            model = TransformersModel(config)
            arguments = ["--backend", "transformers", "--pilot"]
            for key, value in asdict(config).items():
                flag = "--" + ("model-revision" if key == "revision" else key.replace("_", "-"))
                if isinstance(value, bool):
                    if value:
                        arguments.append(flag)
                else:
                    arguments.extend([flag, str(value)])
            ready = {"ready": True, "source": source,
                     "model_load_seconds": model.metadata["load_seconds"]}
            print(json.dumps(ready), flush=True)
            reply(ready)
        except Exception as error:
            traceback.print_exc()
            reply({"error": str(error)})
            return 1
        for line in sys.stdin:
            try:
                if source_metadata() != source or code_snapshot() != code:
                    raise ValueError("Repository changed; restart the model session before running new code")
                request = json.loads(line)
                print(json.dumps({"arguments": request}), flush=True)
                status = main(arguments + request, model=model)
            except SystemExit as error:
                status = error.code
            except Exception:
                traceback.print_exc()
                status = 1
            print(f"Exit status: {status}", flush=True)
            reply({"returncode": status})
    return 0


if __name__ == "__main__":
    raise SystemExit(serve())
