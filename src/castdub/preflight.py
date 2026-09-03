from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from castdub.jobs import advance_episode_job, get_episode_job


def probe_duration_ms(path: Path) -> int:
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
        check=True,
        capture_output=True,
        text=True,
    )
    return round(float(result.stdout.strip()) * 1000)


def inspect_episode_inputs(
    draft_root: Path,
    output_mode: str,
    source_video: Path | None = None,
    duration_tolerance_ms: int = 1000,
) -> dict[str, Any]:
    errors: list[str] = []
    draft_file = draft_root / "draft_content.json"
    if not draft_file.is_file():
        errors.append(f"draft_content.json not found: {draft_file}")
        return {"ok": False, "output_mode": output_mode, "errors": errors}
    if output_mode == "final" and source_video is None:
        errors.append("final output mode requires a clean no-subtitle video")
        return {"ok": False, "output_mode": output_mode, "errors": errors}

    draft = json.loads(draft_file.read_text(encoding="utf-8"))
    draft_duration_ms = round(int(draft.get("duration", 0)) / 1000)
    video_duration_ms = probe_duration_ms(source_video) if source_video else None
    duration_delta_ms = (
        abs(draft_duration_ms - video_duration_ms)
        if video_duration_ms is not None
        else None
    )
    if duration_delta_ms is not None and duration_delta_ms > duration_tolerance_ms:
        errors.append(f"duration mismatch: {duration_delta_ms} ms")
    tracks = draft.get("tracks", [])
    return {
        "ok": not errors,
        "output_mode": output_mode,
        "draft_duration_ms": draft_duration_ms,
        "video_duration_ms": video_duration_ms,
        "duration_delta_ms": duration_delta_ms,
        "track_counts": {
            kind: sum(track.get("type") == kind for track in tracks)
            for kind in ("video", "audio", "text", "effect")
        },
        "errors": errors,
    }


def preflight_registered_job(
    store_path: Path, job_id: str, duration_tolerance_ms: int = 1000
) -> dict[str, Any]:
    job = get_episode_job(store_path, job_id)
    source_video = Path(job["source_video"]) if job["source_video"] else None
    report = inspect_episode_inputs(
        draft_root=Path(job["draft_root"]),
        output_mode=job["output_mode"],
        source_video=source_video,
        duration_tolerance_ms=duration_tolerance_ms,
    )
    report["job_id"] = job_id
    if report["ok"]:
        advance_episode_job(store_path, job_id, "inputs_verified", report)
    return report
