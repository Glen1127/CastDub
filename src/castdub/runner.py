from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from castdub.jianying import import_draft
from castdub.jobs import JobStateError, advance_episode_job, get_episode_job


def episode_work_dir(store_path: Path, job: dict[str, Any]) -> Path:
    return (
        store_path.expanduser().resolve().parent
        / "artifacts"
        / job["series_id"]
        / job["episode_id"]
        / job["target_language"]
    )


def import_registered_draft(store_path: Path, job_id: str) -> dict[str, Any]:
    job = get_episode_job(store_path, job_id)
    work_dir = episode_work_dir(store_path, job)
    output_dir = work_dir / "import"
    report_path = output_dir / "import-report.json"

    if job["status"] == "awaiting_role_approval" and report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        return {
            "ok": True,
            "cache_hit": True,
            "job_id": job_id,
            "status": job["status"],
            "work_dir": str(work_dir),
            "import_report": str(report_path),
            "spoken_dialogue_segment_count": report[
                "spoken_dialogue_segment_count"
            ],
        }
    if job["status"] != "inputs_verified":
        raise JobStateError(
            f"Cannot import {job_id} from {job['status']}; expected inputs_verified"
        )

    source_video = Path(job["source_video"]) if job["source_video"] else None
    report = import_draft(
        draft_root=Path(job["draft_root"]),
        output_dir=output_dir,
        source_video=source_video,
    )
    advance_episode_job(
        store_path,
        job_id,
        "draft_imported",
        {
            "import_report": str(report_path),
            "spoken_dialogue_segment_count": report[
                "spoken_dialogue_segment_count"
            ],
        },
    )
    updated = advance_episode_job(
        store_path,
        job_id,
        "awaiting_role_approval",
        {"reason": "character IDs require approval before voice synthesis"},
    )
    return {
        "ok": True,
        "cache_hit": False,
        "job_id": job_id,
        "status": updated["status"],
        "work_dir": str(work_dir),
        "import_report": str(report_path),
        "timeline": str(output_dir / "timeline.jsonl"),
        "dialogue_plan": str(output_dir / "dialogue-plan.jsonl"),
        "spoken_dialogue_segment_count": report["spoken_dialogue_segment_count"],
    }
