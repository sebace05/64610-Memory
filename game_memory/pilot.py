"""Pilot manifests, launch guards, and durable subprocess logs."""

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import uuid

from .runner import source_metadata


JAVA_GATEWAY_LOG_OPTIONS = "-Xlog:os+container=off:stdout -Xlog:os+container=warning:stderr"


def runtime_environment(base=None) -> dict:
    environment = dict(os.environ if base is None else base)
    options = environment.get("JAVA_TOOL_OPTIONS", "")
    if not options.endswith(JAVA_GATEWAY_LOG_OPTIONS):
        environment["JAVA_TOOL_OPTIONS"] = (options + " " + JAVA_GATEWAY_LOG_OPTIONS).strip()
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return environment


def prepare_pilot(directory: Path, episode, actor, model, backend: str, seeds: list[int]) -> dict:
    """Create an immutable manifest and reject mixed, duplicate, or partial runs.

    This supports one sequential worker. Batch scheduling/resume is separate.
    """
    episode_settings = asdict(episode)
    episode_settings.pop("seed")
    runtime = None
    if model is not None:
        from .transformers_model import runtime_metadata
        runtime = runtime_metadata(model)
    manifest = {"schema_version": 1, "source": source_metadata(), "backend": backend,
                "episode": episode_settings, "actor": actor.metadata,
                "model": asdict(model) if model is not None else None, "runtime": runtime}
    directory = Path(directory)
    path = directory / "pilot-manifest.json"
    if not path.exists() and (list(directory.glob("*/result.json")) or list(directory.glob("*/events.jsonl"))):
        raise ValueError("Existing episode files have no manifest; preserve them and use a new pilot directory")
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x") as stream:
            json.dump(manifest, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except FileExistsError:
        if json.loads(path.read_text()) != manifest:
            raise ValueError("Pilot settings changed or manifest uses an older format; use a new pilot directory")
    for trace in directory.glob("*/events.jsonl"):
        if not (trace.parent / "result.json").exists():
            raise ValueError("Partial episode exists; preserve it and use a new pilot directory")
    for result_path in directory.glob("*/result.json"):
        if not (result_path.parent / "events.jsonl").exists():
            raise ValueError("Episode result has no trace; preserve it and use a new pilot directory")
        result = json.loads(result_path.read_text())
        settings = {k: v for k, v in result["config"].items() if k != "seed"}
        if (settings != manifest["episode"] or result["components"]["actor"] != manifest["actor"]
                or result.get("source") != manifest["source"]):
            raise ValueError("Existing episode settings disagree with the manifest; use a new pilot directory")
        if model is not None and any(result["components"]["model"].get(k) != v
                                     for k, v in (manifest["model"] | manifest["runtime"]).items()):
            raise ValueError("Existing model settings disagree with the manifest; use a new pilot directory")
        if result["config"]["seed"] in seeds:
            raise ValueError("Requested seed already has a result; preserve it and use a new pilot directory")
    return manifest


def run_logged(command: list[str], log_path: Path, environment: dict) -> None:
    """Keep child output even if initialization fails; preserve its exit status."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("x") as stream:
        stream.write(json.dumps({"command": command}) + "\n\n")
        stream.flush()
        print(f"Writing output to: {log_path}", flush=True)
        try:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                    env=environment, text=True)
        except OSError:
            traceback.print_exc(file=stream)
            raise
        stream.write(f"\nExit status: {result.returncode}\n")
    print(log_path.read_text())
    print(f"Saved log: {log_path}")
    result.check_returncode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="Check dependencies, Java, and tests without loading weights")
    args, forwarded = parser.parse_known_args()
    if args.check and forwarded:
        parser.error("--check does not accept episode arguments")
    environment = runtime_environment()
    attempt = uuid.uuid4().hex
    try:
        if args.check:
            logs = args.output_dir / f"checks-{attempt}"
            for command, name in [([sys.executable, "-m", "pip", "check"], "pip-check"),
                                  (["java", "-version"], "java-version"),
                                  ([sys.executable, "-m", "pytest", "-q", "--tb=short"], "pytest")]:
                run_logged(command, logs / f"{name}.log", environment)
            (logs / "pip-freeze.txt").write_text(subprocess.check_output(
                [sys.executable, "-m", "pip", "freeze"], env=environment, text=True))
        else:
            run_logged([sys.executable, "-m", "game_memory.run_episode", *forwarded,
                        "--pilot", "--output-dir", str(args.output_dir)],
                       args.output_dir / f"launch-{attempt}.log", environment)
    except subprocess.CalledProcessError as error:
        return error.returncode if error.returncode >= 0 else 128 - error.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
