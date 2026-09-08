from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from castdub.jobs import (
    JobStateError,
    advance_episode_job,
    episode_work_dir,
    get_episode_job,
)


BACKGROUND_KINDS = {"music", "ambience", "effect"}
LOCKED_BACKGROUND_FIELDS = (
    "segment_id",
    "track_index",
    "source_path",
    "source_start_ms",
    "source_duration_ms",
    "target_start_ms",
    "target_duration_ms",
    "speed",
    "volume",
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


def prepare_mix_approval(store_path: Path, job_id: str) -> dict[str, Any]:
    job = get_episode_job(store_path, job_id)
    if job["status"] != "voice_approved":
        raise JobStateError(
            f"Cannot prepare mix for {job_id} from {job['status']}; "
            "expected voice_approved"
        )
    work_dir = episode_work_dir(store_path, job)
    template_path = work_dir / "approvals" / "background.template.json"
    if template_path.is_file():
        template = json.loads(template_path.read_text(encoding="utf-8"))
        return {
            "ok": True,
            "cache_hit": True,
            "job_id": job_id,
            "status": job["status"],
            "candidate_count": len(template["draft_candidates"]),
            "approval_template": str(template_path),
        }

    report = json.loads(
        (work_dir / "import" / "import-report.json").read_text(encoding="utf-8")
    )
    dialogue_tracks = set(report["dialogue_track_indexes"])
    candidates = [
        {
            **{field: row[field] for field in LOCKED_BACKGROUND_FIELDS},
            "material_name": row.get("material_name", ""),
            "material_type": row.get("material_type", ""),
            "include": False,
            "background_kind": None,
            "confirmed_no_source_dialogue": False,
        }
        for row in _read_jsonl(work_dir / "import" / "audio-segments.jsonl")
        if int(row["track_index"]) not in dialogue_tracks
    ]
    template = {
        "schema_version": 1,
        "job_id": job_id,
        "approved": False,
        "official_me_path": None,
        "official_me_confirmed_no_dialogue": False,
        "draft_candidates": candidates,
    }
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "cache_hit": False,
        "job_id": job_id,
        "status": job["status"],
        "candidate_count": len(candidates),
        "approval_template": str(template_path),
    }


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _render_dialogue(takes: list[dict[str, Any]], output: Path, duration_ms: int) -> None:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    filters: list[str] = []
    labels: list[str] = []
    for index, take in enumerate(takes):
        fitted = Path(take["fitted_path"])
        if not fitted.is_file():
            raise JobStateError(f"Approved fitted take is missing: {fitted}")
        command.extend(("-i", str(fitted)))
        label = f"d{index}"
        start = int(take["start_ms"])
        filters.append(f"[{index}:a]adelay={start}|{start}[{label}]")
        labels.append(f"[{label}]")
    if not labels:
        raise JobStateError("Cannot mix an episode with no approved dialogue")
    filters.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:"
        f"dropout_transition=0,apad,atrim=duration={duration_ms / 1000:.3f}[dialogue]"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    command.extend(
        (
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[dialogue]",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-c:a",
            "pcm_s24le",
            str(output),
        )
    )
    _run(command)


def _render_background(
    official_me: Path | None,
    segments: list[dict[str, Any]],
    output: Path,
    duration_ms: int,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if official_me:
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(official_me),
                "-af",
                f"apad,atrim=duration={duration_ms / 1000:.3f}",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-c:a",
                "pcm_s24le",
                str(output),
            ]
        )
        return

    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    filters: list[str] = []
    labels: list[str] = []
    for index, segment in enumerate(segments):
        source = Path(segment["source_path"])
        if not source.is_file():
            raise JobStateError(f"Approved background source is missing: {source}")
        command.extend(("-i", str(source)))
        label = f"b{index}"
        filters.append(
            f"[{index}:a]atrim=start={segment['source_start_ms'] / 1000:.3f}:"
            f"duration={segment['source_duration_ms'] / 1000:.3f},"
            f"asetpts=PTS-STARTPTS,atempo={float(segment['speed']):.6f},"
            f"atrim=duration={segment['target_duration_ms'] / 1000:.3f},"
            f"volume={float(segment['volume']):.6f},"
            f"adelay={int(segment['target_start_ms'])}|{int(segment['target_start_ms'])}"
            f"[{label}]"
        )
        labels.append(f"[{label}]")
    if not labels:
        raise JobStateError("Approve an official M&E track or at least one background segment")
    filters.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:"
        f"dropout_transition=0,apad,atrim=duration={duration_ms / 1000:.3f}[background]"
    )
    command.extend(
        (
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[background]",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-c:a",
            "pcm_s24le",
            str(output),
        )
    )
    _run(command)


def _render_full_mix(background: Path, dialogue: Path, output: Path) -> None:
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(background),
            "-i",
            str(dialogue),
            "-filter_complex",
            "[0:a][1:a]sidechaincompress=threshold=0.03:ratio=4:attack=20:"
            "release=250[ducked];[ducked][1:a]amix=inputs=2:normalize=0,"
            "alimiter=limit=0.95[mix]",
            "-map",
            "[mix]",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-c:a",
            "pcm_s24le",
            str(output),
        ]
    )


def render_episode_mix(
    store_path: Path, job_id: str, approval_path: Path
) -> dict[str, Any]:
    job = get_episode_job(store_path, job_id)
    work_dir = episode_work_dir(store_path, job)
    manifest_path = work_dir / "mix" / "manifest.json"
    if job["status"] == "mix_completed" and manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {"ok": True, "cache_hit": True, "status": job["status"], **manifest}
    if job["status"] != "voice_approved":
        raise JobStateError(
            f"Cannot mix {job_id} from {job['status']}; expected voice_approved"
        )

    template = json.loads(
        (work_dir / "approvals" / "background.template.json").read_text(
            encoding="utf-8"
        )
    )
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if approval.get("job_id") != job_id or approval.get("approved") is not True:
        raise JobStateError("Background approval must match the job and be approved")
    expected = {item["segment_id"]: item for item in template["draft_candidates"]}
    items = approval.get("draft_candidates", [])
    actual = {item.get("segment_id"): item for item in items}
    if len(items) != len(actual) or set(actual) != set(expected):
        raise JobStateError("Background approval must contain every candidate exactly once")

    selected: list[dict[str, Any]] = []
    for segment_id, source in expected.items():
        item = actual[segment_id]
        for field in LOCKED_BACKGROUND_FIELDS:
            if item.get(field) != source.get(field):
                raise JobStateError(
                    f"Background approval changed locked field {field} in {segment_id}"
                )
        if item.get("include"):
            if item.get("background_kind") not in BACKGROUND_KINDS:
                raise JobStateError(f"Background kind is invalid in {segment_id}")
            if item.get("confirmed_no_source_dialogue") is not True:
                raise JobStateError(
                    f"Background segment may contain source dialogue: {segment_id}"
                )
            selected.append(item)

    official_value = approval.get("official_me_path")
    official_me = Path(official_value).expanduser().resolve() if official_value else None
    if official_me:
        if not official_me.is_file():
            raise JobStateError(f"Official M&E track is missing: {official_me}")
        if approval.get("official_me_confirmed_no_dialogue") is not True:
            raise JobStateError("Official M&E track must be confirmed dialogue-free")
        if selected:
            raise JobStateError("Do not combine an official M&E track with Draft candidates")

    report = json.loads(
        (work_dir / "import" / "import-report.json").read_text(encoding="utf-8")
    )
    duration_ms = int(report["draft_duration_ms"])
    takes = _read_jsonl(work_dir / "synthesis" / "takes.approved.v1.jsonl")
    dialogue = work_dir / "mix" / f"{job['episode_id']}.{job['target_language']}.dialogue-only.wav"
    background = work_dir / "mix" / f"{job['episode_id']}.background.wav"
    full_mix = work_dir / "mix" / f"{job['episode_id']}.{job['target_language']}.full-mix.wav"
    _render_dialogue(takes, dialogue, duration_ms)
    _render_background(official_me, selected, background, duration_ms)
    _render_full_mix(background, dialogue, full_mix)

    canonical = work_dir / "approvals" / "background.v1.json"
    canonical.write_text(
        json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "job_id": job_id,
        "duration_ms": duration_ms,
        "dialogue_only": str(dialogue),
        "background": str(background),
        "full_mix": str(full_mix),
        "background_source": "official_me" if official_me else "approved_draft_tracks",
        "background_segment_count": len(selected),
        "sha256": {
            "dialogue_only": _sha256(dialogue),
            "background": _sha256(background),
            "full_mix": _sha256(full_mix),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    updated = advance_episode_job(
        store_path, job_id, "mix_completed", {"manifest": str(manifest_path)}
    )
    return {"ok": True, "cache_hit": False, "status": updated["status"], **manifest}
