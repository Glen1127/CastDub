from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from castdub.jobs import (
    JobStateError,
    advance_episode_job,
    episode_work_dir,
    get_episode_job,
)

MIN_REFERENCE_MS = 1000
RECOMMENDED_REFERENCE_MS = 3000


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def prepare_voice_profile_approval(
    store_path: Path,
    job_id: str,
    library_root: Path,
) -> dict[str, Any]:
    job = get_episode_job(store_path, job_id)
    work_dir = episode_work_dir(store_path, job)
    output_path = work_dir / "voice-profiles" / "approval.template.json"
    if job["status"] == "awaiting_voice_profile_approval" and output_path.is_file():
        template = json.loads(output_path.read_text(encoding="utf-8"))
        return {
            "ok": True,
            "cache_hit": True,
            "job_id": job_id,
            "status": job["status"],
            "character_count": len(template["characters"]),
            "approval_template": str(output_path),
        }
    if job["status"] != "translation_approved":
        raise JobStateError(
            f"Cannot prepare voices for {job_id} from {job['status']}; "
            "expected translation_approved"
        )

    approved_plan = work_dir / "timeline" / "dialogue-plan.roles-approved.jsonl"
    rows = _read_jsonl(approved_plan)
    characters: list[dict[str, Any]] = []
    series_root = library_root.expanduser().resolve() / "series" / job["series_id"]
    for character_id in sorted({row["character_id"] for row in rows}):
        profile_path = series_root / "characters" / character_id / "profile.json"
        existing_profile = None
        if profile_path.is_file():
            existing_profile = json.loads(profile_path.read_text(encoding="utf-8"))
            if existing_profile.get("character_id") != character_id:
                raise JobStateError(
                    f"Voice profile identity mismatch for {character_id}: {profile_path}"
                )
        candidates = sorted(
            (
                row
                for row in rows
                if row["character_id"] == character_id
                and MIN_REFERENCE_MS
                <= row.get("reference_duration_ms", row["target_duration_ms"])
                <= 10000
            ),
            key=lambda row: row["target_duration_ms"],
            reverse=True,
        )[:5]
        selected_reference_value = (
            existing_profile.get("selected_reference") if existing_profile else None
        )
        selected_reference_text = (
            existing_profile.get("selected_reference_text") if existing_profile else None
        )
        selected_reference = None
        if selected_reference_value:
            selected_path = Path(selected_reference_value).expanduser()
            if not selected_path.is_absolute():
                selected_path = profile_path.parent / selected_path
            selected_reference = str(selected_path.resolve())
        if selected_reference and not Path(selected_reference).is_file():
            raise JobStateError(
                f"Selected voice reference is missing for {character_id}: "
                f"{selected_reference}"
            )
        characters.append(
            {
                "character_id": character_id,
                "existing_profile_path": str(profile_path) if existing_profile else None,
                "existing_selected_reference": selected_reference,
                "existing_selected_reference_text": selected_reference_text,
                "episode_candidates": [
                    {
                        "segment_id": row["segment_id"],
                        "duration_ms": row["target_duration_ms"],
                        "source_text": row["reference_text_zh"],
                        "source_path": row["reference_path"],
                        "source_start_ms": row.get("reference_start_ms", 0),
                        "source_duration_ms": row.get(
                            "reference_duration_ms", row["target_duration_ms"]
                        ),
                        "quality_warning": (
                            "short_voice_reference"
                            if row.get(
                                "reference_duration_ms", row["target_duration_ms"]
                            )
                            < RECOMMENDED_REFERENCE_MS
                            else None
                        ),
                    }
                    for row in candidates
                ],
                "selection": {
                    "mode": "reuse_existing" if existing_profile else "episode_reference",
                    "segment_id": None,
                },
                "approved": False,
            }
        )
    template = {
        "schema_version": 1,
        "job_id": job_id,
        "library_root": str(library_root.expanduser().resolve()),
        "approved": False,
        "characters": characters,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    updated = advance_episode_job(
        store_path,
        job_id,
        "awaiting_voice_profile_approval",
        {"approval_template": str(output_path), "characters": len(characters)},
    )
    return {
        "ok": True,
        "cache_hit": False,
        "job_id": job_id,
        "status": updated["status"],
        "character_count": len(characters),
        "existing_profile_count": sum(
            item["existing_profile_path"] is not None for item in characters
        ),
        "approval_template": str(output_path),
    }


def _extract_reference(candidate: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{candidate['source_start_ms'] / 1000:.3f}",
            "-t",
            f"{candidate['source_duration_ms'] / 1000:.3f}",
            "-i",
            candidate["source_path"],
            "-ac",
            "1",
            "-ar",
            "24000",
            str(output_path),
        ],
        check=True,
    )


def approve_voice_profiles(
    store_path: Path, job_id: str, approval_path: Path
) -> dict[str, Any]:
    job = get_episode_job(store_path, job_id)
    if job["status"] != "awaiting_voice_profile_approval":
        raise JobStateError(
            f"Cannot approve voices for {job_id} from {job['status']}; "
            "expected awaiting_voice_profile_approval"
        )
    work_dir = episode_work_dir(store_path, job)
    template_path = work_dir / "voice-profiles" / "approval.template.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if approval.get("job_id") != job_id or approval.get("approved") is not True:
        raise JobStateError("Voice approval must match the job and set approved to true")

    expected = {item["character_id"]: item for item in template["characters"]}
    approved_items = approval.get("characters", [])
    by_character = {item.get("character_id"): item for item in approved_items}
    if len(approved_items) != len(by_character) or set(by_character) != set(expected):
        raise JobStateError("Voice approval must contain every character exactly once")

    library_root = Path(template["library_root"])
    manifests: list[str] = []
    stable_references: dict[str, str] = {}
    for character_id, source in expected.items():
        item = by_character[character_id]
        if item.get("approved") is not True:
            raise JobStateError(f"Voice profile is not approved for {character_id}")
        selection = item.get("selection", {})
        mode = selection.get("mode")
        character_work = work_dir / "voice-profiles" / character_id
        if mode == "reuse_existing":
            if not source["existing_profile_path"]:
                raise JobStateError(f"No existing profile for {character_id}")
            stable_reference = Path(source["existing_selected_reference"])
            stable_reference_text = str(
                source.get("existing_selected_reference_text") or ""
            ).strip()
            if not stable_reference.is_file():
                raise JobStateError(
                    f"Selected voice reference is missing for {character_id}"
                )
            if not stable_reference_text:
                raise JobStateError(
                    f"Selected voice reference transcript is missing for {character_id}"
                )
        elif mode == "episode_reference":
            if source["existing_profile_path"]:
                raise JobStateError(
                    f"Cannot replace the selected stable voice for {character_id} "
                    "during episode approval"
                )
            candidates = {
                candidate["segment_id"]: candidate
                for candidate in source["episode_candidates"]
            }
            segment_id = selection.get("segment_id")
            if segment_id not in candidates:
                raise JobStateError(
                    f"Invalid episode voice reference for {character_id}: {segment_id!r}"
                )
            candidate = candidates[segment_id]
            stable_reference_text = candidate["source_text"]
            if not Path(candidate["source_path"]).is_file():
                raise JobStateError(
                    f"Voice source is missing for {character_id}: {candidate['source_path']}"
                )
            episode_reference = character_work / "reference.wav"
            _extract_reference(candidate, episode_reference)
            stable_reference = episode_reference
            reference_duration_ms = candidate["source_duration_ms"]
            quality_warning = candidate.get("quality_warning")
            character_library = (
                library_root
                / "series"
                / job["series_id"]
                / "characters"
                / character_id
            )
            selected = character_library / "selected.wav"
            if not selected.exists():
                selected.parent.mkdir(parents=True, exist_ok=True)
                references = character_library / "references"
                references.mkdir(parents=True, exist_ok=True)
                library_candidate = references / f"{job['episode_id']}.wav"
                shutil.copy2(episode_reference, library_candidate)
                shutil.copy2(library_candidate, selected)
                stable_reference = selected
                profile_path = character_library / "profile.json"
                profile_path.write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "series_id": job["series_id"],
                            "character_id": character_id,
                            "display_name": character_id,
                            "episodes_seen": [job["episode_id"]],
                            "selected_reference": str(selected),
                            "selected_reference_text": stable_reference_text,
                            "selection_requires_approval": True,
                            "candidates": {
                                job["episode_id"]: {
                                    "path": str(library_candidate),
                                    "status": "selected",
                                }
                            },
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
        else:
            raise JobStateError(f"Unknown voice selection mode for {character_id}: {mode!r}")

        reference_key = str(stable_reference.resolve())
        if reference_key in stable_references:
            raise JobStateError(
                f"Characters {stable_references[reference_key]} and {character_id} "
                "cannot share one stable voice reference"
            )
        stable_references[reference_key] = character_id
        character_work.mkdir(parents=True, exist_ok=True)
        manifest_path = character_work / "profile.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "job_id": job_id,
                    "character_id": character_id,
                    "stable_reference": str(stable_reference),
                    "stable_reference_text": stable_reference_text,
                    "selection_mode": mode,
                    "reference_duration_ms": (
                        reference_duration_ms
                        if mode == "episode_reference"
                        else None
                    ),
                    "quality_warning": (
                        quality_warning if mode == "episode_reference" else None
                    ),
                    "approved": True,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        manifests.append(str(manifest_path))

    canonical_approval = work_dir / "approvals" / "voice-profiles.v1.json"
    canonical_approval.parent.mkdir(parents=True, exist_ok=True)
    canonical_approval.write_text(
        json.dumps(approval, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    updated = advance_episode_job(
        store_path,
        job_id,
        "voice_profiles_approved",
        {"approval": str(canonical_approval), "characters": len(manifests)},
    )
    return {
        "ok": True,
        "job_id": job_id,
        "status": updated["status"],
        "character_count": len(manifests),
        "approval": str(canonical_approval),
        "profile_manifests": manifests,
    }
