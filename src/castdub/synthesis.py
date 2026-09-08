from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Protocol

from castdub.jobs import (
    JobStateError,
    advance_episode_job,
    episode_work_dir,
    get_episode_job,
)


MAX_TEMPO_RATIO = 1.16


class BatchSynthesisProvider(Protocol):
    name: str
    model_revision: str

    def synthesize_many(self, requests: list[dict[str, Any]]) -> list[Path]: ...


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _duration_ms(path: Path) -> int:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return round(float(result.stdout.strip()) * 1000)


def _fit_duration(source: Path, output: Path, target_ms: int, tempo: float) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    filters = []
    if tempo > 1:
        filters.append(f"rubberband=tempo={tempo:.6f}")
    filters.extend(("apad", f"atrim=duration={target_ms / 1000:.3f}"))
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-af",
            ",".join(filters),
            "-ac",
            "1",
            "-ar",
            "24000",
            str(output),
        ],
        check=True,
    )


def synthesize_episode(
    store_path: Path,
    job_id: str,
    provider: BatchSynthesisProvider,
) -> dict[str, Any]:
    job = get_episode_job(store_path, job_id)
    work_dir = episode_work_dir(store_path, job)
    timeline_path = work_dir / "synthesis" / "takes.v1.jsonl"
    manifest_path = work_dir / "synthesis" / "manifest.json"
    approval_template_path = work_dir / "approvals" / "takes.template.json"
    if job["status"] == "synthesis_completed" and timeline_path.is_file():
        rows = _read_jsonl(timeline_path)
        return {
            "ok": True,
            "cache_hit": True,
            "job_id": job_id,
            "status": job["status"],
            "utterance_count": len(rows),
            "takes": str(timeline_path),
            "manifest": str(manifest_path),
            "approval_template": str(approval_template_path),
        }
    if job["status"] != "performance_analysed":
        raise JobStateError(
            f"Cannot synthesize {job_id} from {job['status']}; "
            "expected performance_analysed"
        )

    performance_rows = _read_jsonl(
        work_dir / "performance" / "analysed.v1.jsonl"
    )
    stable_references: dict[str, str] = {}
    requests: list[dict[str, Any]] = []
    for row in performance_rows:
        character_id = row["character_id"]
        profile_path = work_dir / "voice-profiles" / character_id / "profile.json"
        if not profile_path.is_file():
            raise JobStateError(f"Approved voice profile is missing: {character_id}")
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        if profile.get("character_id") != character_id or profile.get("approved") is not True:
            raise JobStateError(f"Voice profile is not approved for {character_id}")
        stable_reference = Path(profile["stable_reference"]).expanduser().resolve()
        if not stable_reference.is_file():
            raise JobStateError(f"Stable voice reference is missing for {character_id}")
        reference_key = str(stable_reference)
        if reference_key in stable_references and stable_references[reference_key] != character_id:
            raise JobStateError(
                f"Characters {stable_references[reference_key]} and {character_id} "
                "cannot share one stable voice reference"
            )
        stable_references[reference_key] = character_id
        performance_reference = Path(row["performance_reference_path"]).resolve()
        if not performance_reference.is_file():
            raise JobStateError(
                f"Performance reference is missing for {row['utterance_id']}"
            )
        raw_path = work_dir / "synthesis" / "raw" / f"{row['utterance_id']}.wav"
        requests.append(
            {
                "utterance_id": row["utterance_id"],
                "character_id": character_id,
                "target_language": job["target_language"],
                "target_text": row["approved_target_text"],
                "start_ms": row["start_ms"],
                "end_ms": row["end_ms"],
                "target_duration_ms": row["target_duration_ms"],
                "stable_voice_reference": str(stable_reference),
                "performance_reference": str(performance_reference),
                "reference_text": row["source_text"],
                "emotion": row.get("emotion"),
                "emotion_intensity": row.get("emotion_intensity"),
                "output_path": str(raw_path),
            }
        )

    previous_rows = _read_jsonl(timeline_path) if timeline_path.is_file() else []
    previous_by_id = {row["utterance_id"]: row for row in previous_rows}
    generation_fields = (
        "target_language",
        "target_text",
        "stable_voice_reference",
        "performance_reference",
        "reference_text",
        "emotion",
        "emotion_intensity",
    )
    raw_by_id: dict[str, Path] = {}
    pending_requests: list[dict[str, Any]] = []
    for request in requests:
        previous = previous_by_id.get(request["utterance_id"])
        previous_raw = Path(previous["raw_path"]) if previous else None
        reusable = (
            previous is not None
            and previous.get("provider") == provider.name
            and previous.get("model_revision") == provider.model_revision
            and all(previous.get(field) == request.get(field) for field in generation_fields)
            and previous_raw is not None
            and previous_raw.is_file()
        )
        if reusable:
            raw_by_id[request["utterance_id"]] = previous_raw
        else:
            pending_requests.append(request)

    generated_paths = (
        provider.synthesize_many(pending_requests) if pending_requests else []
    )
    if len(generated_paths) != len(pending_requests):
        raise JobStateError(
            f"TTS provider returned {len(generated_paths)} takes for "
            f"{len(pending_requests)} utterances"
        )
    for request, raw_path in zip(pending_requests, generated_paths):
        raw_by_id[request["utterance_id"]] = raw_path
    raw_paths = [raw_by_id[request["utterance_id"]] for request in requests]

    take_rows: list[dict[str, Any]] = []
    rejected = 0
    for request, raw_path in zip(requests, raw_paths):
        raw_path = raw_path.resolve()
        if not raw_path.is_file():
            raise JobStateError(
                f"TTS output is missing for {request['utterance_id']}: {raw_path}"
            )
        raw_duration = _duration_ms(raw_path)
        target_duration = int(request["target_duration_ms"])
        tempo = raw_duration / target_duration if raw_duration > target_duration else 1.0
        accepted = tempo <= MAX_TEMPO_RATIO
        fitted_path: Path | None = None
        if accepted:
            fitted_path = (
                work_dir / "synthesis" / "fitted" / f"{request['utterance_id']}.wav"
            )
            _fit_duration(raw_path, fitted_path, target_duration, tempo)
        else:
            rejected += 1
        take_rows.append(
            {
                **request,
                "provider": provider.name,
                "model_revision": provider.model_revision,
                "raw_path": str(raw_path),
                "raw_duration_ms": raw_duration,
                "tempo_ratio": round(tempo, 6),
                "fitted_path": str(fitted_path) if fitted_path else None,
                "fitted_duration_ms": target_duration if fitted_path else None,
                "status": "generated" if accepted else "needs_text_adaptation",
            }
        )

    _write_jsonl(timeline_path, take_rows)
    manifest = {
        "schema_version": 1,
        "job_id": job_id,
        "provider": provider.name,
        "model_revision": provider.model_revision,
        "utterances": len(take_rows),
        "accepted": len(take_rows) - rejected,
        "needs_text_adaptation": rejected,
        "reused_raw_takes": len(requests) - len(pending_requests),
        "maximum_tempo_ratio": MAX_TEMPO_RATIO,
        "takes": str(timeline_path),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if rejected:
        return {
            "ok": False,
            "cache_hit": False,
            "job_id": job_id,
            "status": job["status"],
            "utterance_count": len(take_rows),
            "needs_text_adaptation": rejected,
            "takes": str(timeline_path),
            "manifest": str(manifest_path),
        }

    approval_template = {
        "schema_version": 1,
        "job_id": job_id,
        "approved": False,
        "takes": [
            {
                "utterance_id": row["utterance_id"],
                "character_id": row["character_id"],
                "target_text": row["target_text"],
                "fitted_path": row["fitted_path"],
                "decision": "pending",
                "review_notes": "",
            }
            for row in take_rows
        ],
    }
    approval_template_path.parent.mkdir(parents=True, exist_ok=True)
    approval_template_path.write_text(
        json.dumps(approval_template, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    updated = advance_episode_job(
        store_path,
        job_id,
        "synthesis_completed",
        {"manifest": str(manifest_path), "utterances": len(take_rows)},
    )
    return {
        "ok": True,
        "cache_hit": False,
        "job_id": job_id,
        "status": updated["status"],
        "utterance_count": len(take_rows),
        "needs_text_adaptation": 0,
        "takes": str(timeline_path),
        "manifest": str(manifest_path),
        "approval_template": str(approval_template_path),
    }


class QwenMlxSubprocessProvider:
    name = "qwen3-tts-mlx"

    def __init__(
        self, worker_python: Path, model_path: Path, model_revision: str
    ) -> None:
        self.worker_python = worker_python.expanduser().absolute()
        self.model_path = model_path.expanduser().resolve()
        self.model_revision = model_revision.strip()
        if not self.worker_python.is_file():
            raise JobStateError(f"MLX worker Python not found: {worker_python}")
        if not self.model_path.is_dir():
            raise JobStateError(f"Qwen3-TTS model path not found: {model_path}")
        if not self.model_revision:
            raise JobStateError("Qwen3-TTS model revision is required for provenance")

    def synthesize_many(self, requests: list[dict[str, Any]]) -> list[Path]:
        worker = Path(__file__).with_name("synthesis_worker.py")
        result = subprocess.run(
            [
                str(self.worker_python),
                str(worker),
                "--model-path",
                str(self.model_path),
            ],
            input=json.dumps(requests, ensure_ascii=False),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            detail = result.stderr.strip().splitlines()[-1:] or ["unknown error"]
            raise JobStateError(f"Qwen3-TTS worker failed: {detail[0]}")
        try:
            paths = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise JobStateError("Qwen3-TTS worker returned invalid JSON") from error
        if not isinstance(paths, list):
            raise JobStateError("Qwen3-TTS worker returned a non-list result")
        return [Path(path) for path in paths]
