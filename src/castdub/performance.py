from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Protocol

from castdub.jobs import (
    JobStateError,
    advance_episode_job,
    episode_work_dir,
    get_episode_job,
)


class BatchPerformanceProvider(Protocol):
    name: str
    model_revision: str

    def analyse_many(self, references: list[Path]) -> list[dict[str, Any]]: ...


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


def _safe_name(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"utterance-{digest}.wav"


def _extract_reference(row: dict[str, Any], output_path: Path) -> None:
    source = Path(row["performance_reference_path"]).expanduser().resolve()
    if not source.is_file():
        raise JobStateError(
            f"Performance reference is missing for {row['utterance_id']}: {source}"
        )
    start_ms = int(row.get("performance_reference_start_ms", 0))
    duration_ms = int(
        row.get("performance_reference_duration_ms", row["target_duration_ms"])
    )
    if start_ms < 0 or duration_ms <= 0:
        raise JobStateError(
            f"Invalid performance reference range for {row['utterance_id']}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start_ms / 1000:.3f}",
            "-t",
            f"{duration_ms / 1000:.3f}",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(output_path),
        ],
        check=True,
    )


def analyse_episode_performance(
    store_path: Path,
    job_id: str,
    provider: BatchPerformanceProvider,
) -> dict[str, Any]:
    job = get_episode_job(store_path, job_id)
    work_dir = episode_work_dir(store_path, job)
    output_path = work_dir / "performance" / "analysed.v1.jsonl"
    manifest_path = work_dir / "performance" / "manifest.json"
    if job["status"] == "performance_analysed" and output_path.is_file():
        rows = _read_jsonl(output_path)
        return {
            "ok": True,
            "cache_hit": True,
            "job_id": job_id,
            "status": job["status"],
            "utterance_count": len(rows),
            "performance_timeline": str(output_path),
            "manifest": str(manifest_path),
        }
    if job["status"] != "voice_profiles_approved":
        raise JobStateError(
            f"Cannot analyse performance for {job_id} from {job['status']}; "
            "expected voice_profiles_approved"
        )

    translations = _read_jsonl(
        work_dir / "translations" / "approved.v1.jsonl"
    )
    references: list[Path] = []
    for row in translations:
        reference = work_dir / "performance" / "references" / _safe_name(
            row["utterance_id"]
        )
        _extract_reference(row, reference)
        references.append(reference)

    results = provider.analyse_many(references)
    if len(results) != len(translations):
        raise JobStateError(
            f"Performance provider returned {len(results)} results for "
            f"{len(translations)} utterances"
        )

    analysed_rows: list[dict[str, Any]] = []
    for row, reference, result in zip(translations, references, results):
        emotion = str(result.get("emotion", "unknown")).strip() or "unknown"
        intensity = float(result.get("emotion_intensity", 0.5))
        if not 0 <= intensity <= 1:
            raise JobStateError(
                f"Performance intensity must be 0..1 in {row['utterance_id']}"
            )
        analysed_rows.append(
            {
                **row,
                "emotion": emotion,
                "emotion_intensity": intensity,
                "speaking_rate": result.get("speaking_rate"),
                "pause_boundaries_ms": result.get("pause_boundaries_ms", []),
                "breath_boundaries_ms": result.get("breath_boundaries_ms", []),
                "vocal_events": result.get("vocal_events", []),
                "performance_reference_path": str(reference),
                "performance_provider": provider.name,
                "performance_model_revision": provider.model_revision,
                "performance_raw": result.get("raw"),
            }
        )

    _write_jsonl(output_path, analysed_rows)
    manifest = {
        "schema_version": 1,
        "job_id": job_id,
        "provider": provider.name,
        "model_revision": provider.model_revision,
        "utterances": len(analysed_rows),
        "performance_timeline": str(output_path),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    updated = advance_episode_job(
        store_path,
        job_id,
        "performance_analysed",
        {"manifest": str(manifest_path), "utterances": len(analysed_rows)},
    )
    return {
        "ok": True,
        "cache_hit": False,
        "job_id": job_id,
        "status": updated["status"],
        "utterance_count": len(analysed_rows),
        "performance_timeline": str(output_path),
        "manifest": str(manifest_path),
    }


class SenseVoiceSubprocessProvider:
    name = "sensevoice-small"

    def __init__(
        self, worker_python: Path, model_path: Path, model_revision: str
    ) -> None:
        self.worker_python = worker_python.expanduser().absolute()
        self.model_path = model_path.expanduser().resolve()
        self.model_revision = model_revision.strip()
        if not self.worker_python.is_file():
            raise JobStateError(f"Performance worker Python not found: {worker_python}")
        if not self.model_path.is_dir():
            raise JobStateError(f"SenseVoice model path not found: {model_path}")
        if not self.model_revision:
            raise JobStateError("SenseVoice model revision is required for provenance")

    def analyse_many(self, references: list[Path]) -> list[dict[str, Any]]:
        worker = Path(__file__).with_name("performance_worker.py")
        request = json.dumps([str(path) for path in references])
        environment = {
            **os.environ,
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        }
        result = subprocess.run(
            [
                str(self.worker_python),
                str(worker),
                "--model-path",
                str(self.model_path),
            ],
            input=request,
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )
        if result.returncode:
            detail = result.stderr.strip().splitlines()[-1:] or ["unknown error"]
            raise JobStateError(f"SenseVoice worker failed: {detail[0]}")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise JobStateError("SenseVoice worker returned invalid JSON") from error
        if not isinstance(payload, list):
            raise JobStateError("SenseVoice worker returned a non-list result")
        return payload
