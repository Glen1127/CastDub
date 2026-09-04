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
from castdub.project import load_rights


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


def create_role_mapping_template(
    dialogue_plan_path: Path,
    rights_path: Path,
    job_id: str,
    output_path: Path,
) -> dict[str, Any]:
    rows = _read_jsonl(dialogue_plan_path)
    grants = load_rights(rights_path).voice_grants
    template = {
        "schema_version": 1,
        "job_id": job_id,
        "approved": False,
        "authorized_characters": [grant.character_id for grant in grants],
        "assignments": [
            {
                "segment_id": row["segment_id"],
                "start_ms": row["target_start_ms"],
                "duration_ms": row["target_duration_ms"],
                "source_text": row["reference_text_zh"],
                "reference_path": row["reference_path"],
                "approved_character_id": None,
            }
            for row in rows
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return template


def approve_role_mapping(
    store_path: Path, job_id: str, mapping_path: Path
) -> dict[str, Any]:
    job = get_episode_job(store_path, job_id)
    if job["status"] != "awaiting_role_approval":
        raise JobStateError(
            f"Cannot approve roles for {job_id} from {job['status']}; "
            "expected awaiting_role_approval"
        )

    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    if mapping.get("job_id") != job_id:
        raise JobStateError("Role mapping job_id does not match the registered job")
    if mapping.get("approved") is not True:
        raise JobStateError("Role mapping must set approved to true")

    work_dir = episode_work_dir(store_path, job)
    dialogue_plan_path = work_dir / "import" / "dialogue-plan.jsonl"
    rows = _read_jsonl(dialogue_plan_path)
    expected_ids = {row["segment_id"] for row in rows}
    assignments = mapping.get("assignments", [])
    assignment_ids = [item.get("segment_id") for item in assignments]
    if len(assignment_ids) != len(set(assignment_ids)):
        raise JobStateError("Role mapping contains duplicate segment IDs")
    if set(assignment_ids) != expected_ids:
        missing = sorted(expected_ids - set(assignment_ids))
        extra = sorted(set(assignment_ids) - expected_ids)
        raise JobStateError(
            f"Role mapping must cover every segment; missing={missing[:5]}, extra={extra[:5]}"
        )

    permitted = {
        grant.character_id
        for grant in load_rights(Path(job["rights_path"])).voice_grants
    }
    by_segment: dict[str, str] = {}
    for assignment in assignments:
        character_id = assignment.get("approved_character_id")
        if character_id not in permitted:
            raise JobStateError(
                f"Segment {assignment.get('segment_id')} uses unauthorized character "
                f"{character_id!r}"
            )
        by_segment[assignment["segment_id"]] = character_id

    approved_rows = [
        {**row, "character_id": by_segment[row["segment_id"]]}
        for row in rows
    ]
    approvals_dir = work_dir / "approvals"
    canonical_mapping = approvals_dir / "role-mapping.v1.json"
    approvals_dir.mkdir(parents=True, exist_ok=True)
    canonical_mapping.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    approved_plan = work_dir / "timeline" / "dialogue-plan.roles-approved.jsonl"
    _write_jsonl(approved_plan, approved_rows)

    translation_rows = [
        {
            "utterance_id": row["segment_id"],
            "character_id": row["character_id"],
            "start_ms": row["target_start_ms"],
            "end_ms": row["target_start_ms"] + row["target_duration_ms"],
            "target_duration_ms": row["target_duration_ms"],
            "source_text": row["reference_text_zh"],
            "draft_target_text": row.get("translation_en_draft", ""),
            "approved_target_text": None,
            "emotion": None,
            "emotion_intensity": None,
            "speaking_rate": None,
            "pause_boundaries_ms": [],
            "breath_boundaries_ms": [],
            "performance_reference_path": row["reference_path"],
            "status": "pending",
        }
        for row in approved_rows
    ]
    translation_worklist = work_dir / "translations" / "worklist.jsonl"
    _write_jsonl(translation_worklist, translation_rows)

    advance_episode_job(
        store_path,
        job_id,
        "roles_approved",
        {"mapping": str(canonical_mapping), "segments": len(approved_rows)},
    )
    updated = advance_episode_job(
        store_path,
        job_id,
        "awaiting_translation_approval",
        {"translation_worklist": str(translation_worklist)},
    )
    return {
        "ok": True,
        "job_id": job_id,
        "status": updated["status"],
        "assignment_count": len(approved_rows),
        "character_count": len(set(by_segment.values())),
        "approved_mapping": str(canonical_mapping),
        "approved_dialogue_plan": str(approved_plan),
        "translation_worklist": str(translation_worklist),
    }
