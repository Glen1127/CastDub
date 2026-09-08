from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from castdub.jobs import (
    JobStateError,
    advance_episode_job,
    episode_work_dir,
    get_episode_job,
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _duration_ms(probe: dict[str, Any]) -> int:
    return round(float(probe["format"]["duration"]) * 1000)


def _srt_texts(path: Path) -> list[list[str]]:
    blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip())
    texts: list[list[str]] = []
    for block in blocks:
        lines = block.splitlines()
        if len(lines) >= 3 and " --> " in lines[1]:
            texts.append(lines[2:])
    return texts


def run_delivery_qc(
    store_path: Path, job_id: str, duration_tolerance_ms: int = 120
) -> dict[str, Any]:
    job = get_episode_job(store_path, job_id)
    work_dir = episode_work_dir(store_path, job)
    report_path = work_dir / "qc" / "qc-report.json"
    if job["status"] == "qc_passed" and report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        return {"cache_hit": True, "status": job["status"], **report}
    if job["status"] != "render_completed":
        raise JobStateError(
            f"Cannot run QC for {job_id} from {job['status']}; expected render_completed"
        )
    if duration_tolerance_ms < 0:
        raise JobStateError("Duration tolerance cannot be negative")

    failures: list[str] = []
    warnings: list[str] = []
    deliverables = json.loads(
        (work_dir / "deliverables" / "manifest.json").read_text(encoding="utf-8")
    )
    mix_manifest = json.loads(
        (work_dir / "mix" / "manifest.json").read_text(encoding="utf-8")
    )
    takes = _read_jsonl(work_dir / "synthesis" / "takes.approved.v1.jsonl")

    rights_path = Path(job["rights_path"])
    if not rights_path.is_file() or _sha256(rights_path) != job["rights_sha256"]:
        failures.append("rights manifest is missing or changed after job registration")

    required = {
        name: Path(deliverables[name])
        for name in (
            "dialogue_only",
            "full_mix",
            "timeline",
            "target_srt",
            "bilingual_srt",
            "target_vtt",
            "target_ass",
        )
    }
    for name, path in required.items():
        if not path.is_file():
            failures.append(f"missing deliverable: {name}")

    if not failures:
        target_blocks = _srt_texts(required["target_srt"])
        expected_target = [str(row["target_text"]).strip() for row in takes]
        if ["\n".join(block) for block in target_blocks] != expected_target:
            failures.append("target subtitles do not match approved spoken text")
        bilingual_blocks = _srt_texts(required["bilingual_srt"])
        if len(bilingual_blocks) != len(takes):
            failures.append("bilingual subtitle cue count does not match approved takes")
        else:
            for row, lines in zip(takes, bilingual_blocks):
                expected = [
                    str(row.get("reference_text", "")).strip(),
                    str(row["target_text"]).strip(),
                ]
                if lines != expected:
                    failures.append(
                        f"bilingual subtitle mismatch in {row['utterance_id']}"
                    )
                    break

        expected_duration = int(mix_manifest["duration_ms"])
        for name in ("dialogue_only", "full_mix"):
            probe = _probe(required[name])
            audio = next(
                (stream for stream in probe["streams"] if stream["codec_type"] == "audio"),
                None,
            )
            if audio is None:
                failures.append(f"{name} has no audio stream")
                continue
            if int(audio.get("sample_rate", 0)) != 48000:
                failures.append(f"{name} sample rate is not 48000 Hz")
            if int(audio.get("channels", 0)) != 2:
                failures.append(f"{name} is not stereo")
            if abs(_duration_ms(probe) - expected_duration) > duration_tolerance_ms:
                failures.append(f"{name} duration does not match the episode")

        style = deliverables.get("subtitle_style", {})
        expected_style = {
            "font": "Arial",
            "font_size": 20,
            "alignment": 2,
            "margin_v": 18,
            "outline": 2,
            "shadow": 1,
        }
        if style != expected_style:
            failures.append("burned-subtitle style differs from the approved safe area")

        if job["output_mode"] == "final":
            final_value = deliverables.get("final_video")
            final_video = Path(final_value) if final_value else None
            if final_video is None or not final_video.is_file():
                failures.append("final mode is missing the rendered MP4")
            else:
                final_probe = _probe(final_video)
                source_probe = _probe(Path(job["source_video"]))
                final_video_stream = next(
                    stream
                    for stream in final_probe["streams"]
                    if stream["codec_type"] == "video"
                )
                source_video_stream = next(
                    stream
                    for stream in source_probe["streams"]
                    if stream["codec_type"] == "video"
                )
                if (
                    final_video_stream.get("width"),
                    final_video_stream.get("height"),
                ) != (
                    source_video_stream.get("width"),
                    source_video_stream.get("height"),
                ):
                    failures.append("final video dimensions differ from the clean master")
                if not any(
                    stream["codec_type"] == "audio" for stream in final_probe["streams"]
                ):
                    failures.append("final video has no target audio stream")

    report = {
        "ok": not failures,
        "job_id": job_id,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
        "utterance_count": len(takes),
        "checked_subtitle_position": {"alignment": 2, "margin_v": 18},
        "deliverable_sha256": {
            name: _sha256(path) for name, path in required.items() if path.is_file()
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if failures:
        return {"cache_hit": False, "status": job["status"], **report}
    updated = advance_episode_job(
        store_path, job_id, "qc_passed", {"qc_report": str(report_path)}
    )
    return {"cache_hit": False, "status": updated["status"], **report}


def complete_episode(store_path: Path, job_id: str) -> dict[str, Any]:
    job = get_episode_job(store_path, job_id)
    if job["status"] == "completed":
        return {"ok": True, "cache_hit": True, "job_id": job_id, "status": "completed"}
    if job["status"] != "qc_passed":
        raise JobStateError(
            f"Cannot complete {job_id} from {job['status']}; expected qc_passed"
        )
    report_path = episode_work_dir(store_path, job) / "qc" / "qc-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("ok") is not True:
        raise JobStateError("Cannot complete an episode with failed QC")
    updated = advance_episode_job(
        store_path, job_id, "completed", {"qc_report": str(report_path)}
    )
    return {
        "ok": True,
        "cache_hit": False,
        "job_id": job_id,
        "status": updated["status"],
        "qc_report": str(report_path),
    }
