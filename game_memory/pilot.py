"""Immutable pilot manifests and runtime environment."""

from dataclasses import asdict
import json
import os
from pathlib import Path

from .runner import source_metadata


JAVA_GATEWAY_LOG_OPTIONS = "-Xlog:os+container=off:stdout -Xlog:os+container=warning:stderr"


def runtime_environment(base=None) -> dict:
    environment = dict(os.environ if base is None else base)
    options = environment.get("JAVA_TOOL_OPTIONS", "")
    if not options.endswith(JAVA_GATEWAY_LOG_OPTIONS):
        environment["JAVA_TOOL_OPTIONS"] = (options + " " + JAVA_GATEWAY_LOG_OPTIONS).strip()
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return environment


def prepare_pilot(directory: Path, episode, actor, model, backend: str, seeds: list[int], *,
                  memory_metadata: dict, protocol_id: str) -> dict:
    """Create an immutable manifest and reject mixed, duplicate, or partial runs.

    This supports one sequential worker. Batch scheduling/resume is separate.
    """
    if not isinstance(protocol_id, str) or not protocol_id.strip():
        raise ValueError("protocol_id must be nonempty")
    if not isinstance(memory_metadata, dict) or not memory_metadata:
        raise ValueError("memory_metadata must be a nonempty dictionary")
    episode_settings = asdict(episode)
    episode_settings.pop("seed")
    runtime = None
    if model is not None:
        from .transformers_model import runtime_metadata
        runtime = runtime_metadata(model)
    manifest = {"schema_version": 2, "source": source_metadata(), "backend": backend,
                "episode": episode_settings, "actor": actor.metadata,
                "memory": memory_metadata, "protocol_id": protocol_id,
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
                or result.get("source") != manifest["source"]
                or result["components"].get("memory") != manifest["memory"]
                or result.get("protocol_id") != manifest["protocol_id"]):
            raise ValueError("Existing episode settings disagree with the manifest; use a new pilot directory")
        if model is not None and any(result["components"]["model"].get(k) != v
                                     for k, v in (manifest["model"] | manifest["runtime"]).items()):
            raise ValueError("Existing model settings disagree with the manifest; use a new pilot directory")
        if result["config"]["seed"] in seeds:
            raise ValueError("Requested seed already has a result; preserve it and use a new pilot directory")
    return manifest
