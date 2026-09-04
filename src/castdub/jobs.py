from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from castdub.project import load_rights


class JobStateError(ValueError):
    """Raised when an episode job or transition is invalid."""


STAGES = (
    "ready_for_preflight",
    "inputs_verified",
    "draft_imported",
    "awaiting_role_approval",
    "roles_approved",
    "awaiting_translation_approval",
    "translation_approved",
    "awaiting_voice_profile_approval",
    "voice_profiles_approved",
    "performance_analysed",
    "synthesis_completed",
    "voice_approved",
    "mix_completed",
    "render_completed",
    "qc_passed",
    "completed",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _connect(store_path: Path) -> sqlite3.Connection:
    store_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(store_path)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS episode_jobs (
            job_id TEXT PRIMARY KEY,
            series_id TEXT NOT NULL,
            episode_id TEXT NOT NULL,
            target_language TEXT NOT NULL,
            output_mode TEXT NOT NULL,
            status TEXT NOT NULL,
            draft_root TEXT NOT NULL,
            source_video TEXT,
            rights_path TEXT NOT NULL,
            rights_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS job_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL REFERENCES episode_jobs(job_id),
            previous_status TEXT,
            status TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    return connection


def _validate_identifier(label: str, value: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", value):
        raise JobStateError(f"Invalid {label}: {value!r}")


def create_episode_job(
    store_path: Path,
    series_id: str,
    episode_id: str,
    target_language: str,
    rights_path: Path,
    draft_root: Path,
    source_video: Path | None = None,
    output_mode: str = "final",
) -> dict[str, Any]:
    _validate_identifier("series ID", series_id)
    _validate_identifier("episode ID", episode_id)
    if not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", target_language):
        raise JobStateError(f"Invalid target language: {target_language!r}")
    if output_mode not in {"editor", "final"}:
        raise JobStateError(f"Invalid output mode: {output_mode!r}")

    rights_path = rights_path.expanduser().resolve()
    draft_root = draft_root.expanduser().resolve()
    source_video = source_video.expanduser().resolve() if source_video else None
    if not rights_path.is_file():
        raise FileNotFoundError(f"Rights manifest not found: {rights_path}")
    if not draft_root.is_dir():
        raise FileNotFoundError(f"Draft directory not found: {draft_root}")
    if output_mode == "final" and source_video is None:
        raise JobStateError("Final output mode requires a clean no-subtitle video")
    if source_video is not None and not source_video.is_file():
        raise FileNotFoundError(f"Source video not found: {source_video}")

    load_rights(rights_path).assert_authorized(target_language)
    job_id = f"{series_id}:{episode_id}:{target_language}"
    timestamp = _utc_now()
    record = {
        "job_id": job_id,
        "series_id": series_id,
        "episode_id": episode_id,
        "target_language": target_language,
        "output_mode": output_mode,
        "status": STAGES[0],
        "draft_root": str(draft_root),
        "source_video": str(source_video) if source_video else None,
        "rights_path": str(rights_path),
        "rights_sha256": _sha256(rights_path),
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    with _connect(store_path) as connection:
        try:
            connection.execute(
                """
                INSERT INTO episode_jobs (
                    job_id, series_id, episode_id, target_language, output_mode,
                    status, draft_root, source_video, rights_path, rights_sha256,
                    created_at, updated_at
                ) VALUES (
                    :job_id, :series_id, :episode_id, :target_language,
                    :output_mode, :status, :draft_root, :source_video,
                    :rights_path, :rights_sha256, :created_at, :updated_at
                )
                """,
                record,
            )
        except sqlite3.IntegrityError as error:
            raise JobStateError(f"Episode job already exists: {job_id}") from error
        connection.execute(
            """
            INSERT INTO job_events (
                job_id, previous_status, status, evidence_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, None, STAGES[0], "{}", timestamp),
        )
    return record


def get_episode_job(store_path: Path, job_id: str) -> dict[str, Any]:
    with _connect(store_path) as connection:
        row = connection.execute(
            "SELECT * FROM episode_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
    if row is None:
        raise JobStateError(f"Episode job not found: {job_id}")
    return dict(row)


def episode_work_dir(store_path: Path, job: dict[str, Any]) -> Path:
    return (
        store_path.expanduser().resolve().parent
        / "artifacts"
        / job["series_id"]
        / job["episode_id"]
        / job["target_language"]
    )


def advance_episode_job(
    store_path: Path,
    job_id: str,
    next_status: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if next_status not in STAGES:
        raise JobStateError(f"Unknown job status: {next_status}")
    with _connect(store_path) as connection:
        row = connection.execute(
            "SELECT status FROM episode_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row is None:
            raise JobStateError(f"Episode job not found: {job_id}")
        current = str(row["status"])
        if current == next_status:
            return get_episode_job(store_path, job_id)
        expected = STAGES[STAGES.index(current) + 1] if current != STAGES[-1] else None
        if next_status != expected:
            raise JobStateError(
                f"Cannot transition {job_id} from {current} to {next_status}; "
                f"expected {expected or 'no further transition'}"
            )
        timestamp = _utc_now()
        connection.execute(
            "UPDATE episode_jobs SET status = ?, updated_at = ? WHERE job_id = ?",
            (next_status, timestamp, job_id),
        )
        connection.execute(
            """
            INSERT INTO job_events (
                job_id, previous_status, status, evidence_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                job_id,
                current,
                next_status,
                json.dumps(evidence or {}, ensure_ascii=False, sort_keys=True),
                timestamp,
            ),
        )
    return get_episode_job(store_path, job_id)
