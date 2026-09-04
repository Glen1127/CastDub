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


LOCKED_FIELDS = (
    "utterance_id",
    "character_id",
    "start_ms",
    "end_ms",
    "target_duration_ms",
    "source_text",
    "performance_reference_path",
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def approve_translation_worklist(
    store_path: Path, job_id: str, worklist_path: Path
) -> dict[str, Any]:
    job = get_episode_job(store_path, job_id)
    if job["status"] != "awaiting_translation_approval":
        raise JobStateError(
            f"Cannot approve translation for {job_id} from {job['status']}; "
            "expected awaiting_translation_approval"
        )
    work_dir = episode_work_dir(store_path, job)
    canonical_path = work_dir / "translations" / "worklist.jsonl"
    original_rows = _read_jsonl(canonical_path)
    candidate_rows = _read_jsonl(worklist_path)
    original = {row["utterance_id"]: row for row in original_rows}
    candidate = {row.get("utterance_id"): row for row in candidate_rows}
    if len(candidate_rows) != len(candidate):
        raise JobStateError("Translation worklist contains duplicate utterance IDs")
    if set(candidate) != set(original):
        missing = sorted(set(original) - set(candidate))
        extra = sorted(set(candidate) - set(original))
        raise JobStateError(
            f"Translation worklist must cover every utterance; "
            f"missing={missing[:5]}, extra={extra[:5]}"
        )

    approved_rows: list[dict[str, Any]] = []
    for utterance_id, source in original.items():
        approved = candidate[utterance_id]
        for field in LOCKED_FIELDS:
            if approved.get(field) != source.get(field):
                raise JobStateError(
                    f"Translation approval changed locked field {field} in {utterance_id}"
                )
        target_text = approved.get("approved_target_text")
        if not isinstance(target_text, str) or not target_text.strip():
            raise JobStateError(f"Missing approved target text in {utterance_id}")
        if approved.get("status") != "approved":
            raise JobStateError(f"Translation is not approved in {utterance_id}")
        intensity = approved.get("emotion_intensity")
        if intensity is not None and not 0 <= float(intensity) <= 1:
            raise JobStateError(f"Emotion intensity must be 0..1 in {utterance_id}")
        approved_rows.append({**approved, "approved_target_text": target_text.strip()})

    approved_path = work_dir / "translations" / "approved.v1.jsonl"
    approved_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False) + "\n" for row in approved_rows
        ),
        encoding="utf-8",
    )
    updated = advance_episode_job(
        store_path,
        job_id,
        "translation_approved",
        {"approved_worklist": str(approved_path), "utterances": len(approved_rows)},
    )
    return {
        "ok": True,
        "job_id": job_id,
        "status": updated["status"],
        "utterance_count": len(approved_rows),
        "approved_worklist": str(approved_path),
    }
