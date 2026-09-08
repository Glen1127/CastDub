from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from castdub.jobs import (
    JobStateError,
    advance_episode_job,
    episode_work_dir,
    get_episode_job,
)


LOCKED_FIELDS = ("character_id", "target_text", "fitted_path")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def approve_synthesized_takes(
    store_path: Path, job_id: str, approval_path: Path
) -> dict[str, Any]:
    job = get_episode_job(store_path, job_id)
    work_dir = episode_work_dir(store_path, job)
    canonical = work_dir / "approvals" / "takes.v1.json"
    approved_timeline = work_dir / "synthesis" / "takes.approved.v1.jsonl"
    if job["status"] == "voice_approved" and canonical.is_file():
        rows = _read_jsonl(approved_timeline)
        return {
            "ok": True,
            "cache_hit": True,
            "job_id": job_id,
            "status": job["status"],
            "utterance_count": len(rows),
            "approval": str(canonical),
            "approved_takes": str(approved_timeline),
        }
    if job["status"] != "synthesis_completed":
        raise JobStateError(
            f"Cannot approve takes for {job_id} from {job['status']}; "
            "expected synthesis_completed"
        )

    generated_rows = _read_jsonl(work_dir / "synthesis" / "takes.v1.jsonl")
    generated = {row["utterance_id"]: row for row in generated_rows}
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if approval.get("job_id") != job_id or approval.get("approved") is not True:
        raise JobStateError("Take approval must match the job and set approved to true")
    items = approval.get("takes", [])
    approved = {item.get("utterance_id"): item for item in items}
    if len(items) != len(approved) or set(approved) != set(generated):
        raise JobStateError("Take approval must contain every utterance exactly once")

    final_rows: list[dict[str, Any]] = []
    for utterance_id, source in generated.items():
        item = approved[utterance_id]
        for field in LOCKED_FIELDS:
            source_field = "target_text" if field == "target_text" else field
            if item.get(field) != source.get(source_field):
                raise JobStateError(
                    f"Take approval changed locked field {field} in {utterance_id}"
                )
        if item.get("decision") != "approved":
            raise JobStateError(f"Synthesized take is not approved in {utterance_id}")
        fitted = Path(source["fitted_path"])
        if not fitted.is_file():
            raise JobStateError(f"Approved fitted take is missing in {utterance_id}")
        final_rows.append(
            {
                **source,
                "status": "approved",
                "review_notes": str(item.get("review_notes", "")),
            }
        )

    canonical.write_text(
        json.dumps(approval, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    approved_timeline.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in final_rows),
        encoding="utf-8",
    )
    updated = advance_episode_job(
        store_path,
        job_id,
        "voice_approved",
        {"approval": str(canonical), "utterances": len(final_rows)},
    )
    return {
        "ok": True,
        "cache_hit": False,
        "job_id": job_id,
        "status": updated["status"],
        "utterance_count": len(final_rows),
        "approval": str(canonical),
        "approved_takes": str(approved_timeline),
    }
