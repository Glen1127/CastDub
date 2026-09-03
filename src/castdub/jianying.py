from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


class JianyingImportError(ValueError):
    """Raised when a Jianying draft cannot be imported safely."""


@dataclass(frozen=True)
class SubtitleCue:
    cue_id: str
    track_index: int
    start_ms: int
    end_ms: int
    text: str
    language: str


@dataclass(frozen=True)
class AudioSegment:
    segment_id: str
    track_index: int
    material_id: str
    material_name: str
    material_type: str
    source_path: str
    source_start_ms: int
    source_duration_ms: int
    target_start_ms: int
    target_duration_ms: int
    speed: float
    volume: float

    @property
    def target_end_ms(self) -> int:
        return self.target_start_ms + self.target_duration_ms


def _milliseconds(microseconds: int | float | None) -> int:
    return round((microseconds or 0) / 1000)


def _language(text: str) -> str:
    return "zh" if re.search(r"[\u3400-\u9fff]", text) else "en"


def _overlaps(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return max(start_a, start_b) < min(end_a, end_b)


def _overlap_ms(start_a: int, end_a: int, start_b: int, end_b: int) -> int:
    return max(0, min(end_a, end_b) - max(start_a, start_b))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise JianyingImportError(f"Invalid Jianying JSON: {path}") from error
    if not isinstance(value, dict):
        raise JianyingImportError(f"Expected a JSON object: {path}")
    return value


def load_main_draft(draft_root: Path) -> tuple[dict[str, Any], Path]:
    draft_root = draft_root.expanduser().resolve()
    candidates = (draft_root / "draft_content.json", draft_root / "draft_content.json.bak")
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            return _read_json(candidate), candidate
        except JianyingImportError:
            continue
    raise JianyingImportError(f"No valid root draft_content.json in {draft_root}")


def resolve_material_path(draft_root: Path, stored_path: str) -> Path:
    marker = "##/"
    if marker in stored_path:
        stored_path = stored_path.split(marker, 1)[1]
    candidate = Path(stored_path)
    if candidate.is_absolute():
        return candidate
    return draft_root / candidate


def extract_subtitles(draft: dict[str, Any]) -> list[SubtitleCue]:
    material_map: dict[str, tuple[str, str]] = {}
    for material in draft.get("materials", {}).get("texts", []):
        try:
            content = json.loads(material.get("content", "{}"))
        except json.JSONDecodeError:
            continue
        material_map[material["id"]] = (
            str(content.get("text", "")),
            str(material.get("type", "")),
        )

    cues: list[SubtitleCue] = []
    for track_index, track in enumerate(draft.get("tracks", [])):
        if track.get("type") != "text":
            continue
        for segment in track.get("segments", []):
            text, material_type = material_map.get(segment.get("material_id"), ("", ""))
            if material_type != "subtitle" or not text.strip():
                continue
            timerange = segment.get("target_timerange", {})
            start_ms = _milliseconds(timerange.get("start"))
            cues.append(
                SubtitleCue(
                    cue_id=str(segment["id"]),
                    track_index=track_index,
                    start_ms=start_ms,
                    end_ms=start_ms + _milliseconds(timerange.get("duration")),
                    text=text.strip(),
                    language=_language(text),
                )
            )
    return sorted(cues, key=lambda cue: (cue.start_ms, cue.end_ms, cue.track_index))


def extract_audio_segments(
    draft_root: Path, draft: dict[str, Any]
) -> tuple[list[AudioSegment], list[int]]:
    materials = {
        material["id"]: material
        for material in draft.get("materials", {}).get("audios", [])
    }
    all_segments: list[AudioSegment] = []
    track_scores: dict[int, int] = {}

    for track_index, track in enumerate(draft.get("tracks", [])):
        if track.get("type") != "audio":
            continue
        explicit_tts = 0
        dialogue_like = 0
        for segment in track.get("segments", []):
            material = materials.get(segment.get("material_id"))
            if not material:
                continue
            material_type = str(material.get("type", ""))
            explicit_tts += material_type == "text_to_audio"
            dialogue_like += material_type in {
                "text_to_audio",
                "extract_music",
                "video_original_sound",
            }
            source_range = segment.get("source_timerange", {})
            target_range = segment.get("target_timerange", {})
            stored_path = str(material.get("path", ""))
            resolved_path = resolve_material_path(draft_root, stored_path)
            all_segments.append(
                AudioSegment(
                    segment_id=str(segment["id"]),
                    track_index=track_index,
                    material_id=str(material["id"]),
                    material_name=str(material.get("name", "")),
                    material_type=material_type,
                    source_path=str(resolved_path),
                    source_start_ms=_milliseconds(source_range.get("start")),
                    source_duration_ms=_milliseconds(source_range.get("duration")),
                    target_start_ms=_milliseconds(target_range.get("start")),
                    target_duration_ms=_milliseconds(target_range.get("duration")),
                    speed=float(segment.get("speed", 1.0)),
                    volume=float(segment.get("volume", 1.0)),
                )
            )
        if dialogue_like:
            track_scores[track_index] = explicit_tts * 1000 + dialogue_like

    if not track_scores:
        raise JianyingImportError("No dialogue-like audio track found")
    best_score = max(track_scores.values())
    dialogue_tracks = [index for index, score in track_scores.items() if score == best_score]
    return all_segments, dialogue_tracks


def _joined_text(cues: Iterable[SubtitleCue]) -> str:
    return " ".join(cue.text for cue in cues).strip()


def import_draft(
    draft_root: Path,
    output_dir: Path,
    source_video: Path | None = None,
) -> dict[str, Any]:
    draft_root = draft_root.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    draft, draft_path = load_main_draft(draft_root)
    subtitles = extract_subtitles(draft)
    audio_segments, dialogue_tracks = extract_audio_segments(draft_root, draft)

    zh_cues = [cue for cue in subtitles if cue.language == "zh"]
    en_cues = [cue for cue in subtitles if cue.language == "en"]
    dialogue_segments = [
        segment for segment in audio_segments if segment.track_index in dialogue_tracks
    ]

    missing_dialogue = [
        segment.source_path
        for segment in dialogue_segments
        if not Path(segment.source_path).is_file()
    ]
    if missing_dialogue:
        raise JianyingImportError(
            f"{len(missing_dialogue)} dialogue material files are missing"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    timeline_rows: list[dict[str, Any]] = []
    for index, cue in enumerate(zh_cues, start=1):
        overlapping_en = [
            item
            for item in en_cues
            if _overlaps(cue.start_ms, cue.end_ms, item.start_ms, item.end_ms)
        ]
        ranked_audio = sorted(
            dialogue_segments,
            key=lambda item: _overlap_ms(
                cue.start_ms,
                cue.end_ms,
                item.target_start_ms,
                item.target_end_ms,
            ),
            reverse=True,
        )
        assigned_audio = (
            [ranked_audio[0].segment_id]
            if ranked_audio
            and _overlap_ms(
                cue.start_ms,
                cue.end_ms,
                ranked_audio[0].target_start_ms,
                ranked_audio[0].target_end_ms,
            )
            else []
        )
        timeline_rows.append(
            {
                "cue_index": index,
                "cue_id": cue.cue_id,
                "start_ms": cue.start_ms,
                "end_ms": cue.end_ms,
                "source_zh": cue.text,
                "translation_en_draft": _joined_text(overlapping_en),
                "dialogue_segment_ids": assigned_audio,
                "character_id": None,
                "translation_status": "draft",
            }
        )

    _write_jsonl(output_dir / "timeline.jsonl", timeline_rows)
    _write_jsonl(
        output_dir / "audio-segments.jsonl",
        [asdict(segment) for segment in audio_segments],
    )
    _write_timeline_csv(output_dir / "timeline.csv", timeline_rows)

    rows_by_segment: dict[str, list[dict[str, Any]]] = {}
    for row in timeline_rows:
        for segment_id in row["dialogue_segment_ids"]:
            rows_by_segment.setdefault(segment_id, []).append(row)
    dialogue_plan: list[dict[str, Any]] = []
    for segment in dialogue_segments:
        rows = rows_by_segment.get(segment.segment_id, [])
        if not rows:
            continue
        overlapping_en = [
            cue
            for cue in en_cues
            if _overlaps(
                segment.target_start_ms,
                segment.target_end_ms,
                cue.start_ms,
                cue.end_ms,
            )
        ]
        dialogue_plan.append(
            {
                "segment_id": segment.segment_id,
                "target_start_ms": segment.target_start_ms,
                "target_duration_ms": segment.target_duration_ms,
                "reference_path": segment.source_path,
                "reference_start_ms": segment.source_start_ms,
                "reference_duration_ms": segment.source_duration_ms,
                "reference_text_zh": " ".join(row["source_zh"] for row in rows),
                "translation_en_draft": _joined_text(overlapping_en),
                "cue_ids": [row["cue_id"] for row in rows],
                "character_id": None,
                "synthesis_status": "pending",
            }
        )
    _write_jsonl(output_dir / "dialogue-plan.jsonl", dialogue_plan)

    report = {
        "schema_version": 1,
        "draft_root": str(draft_root),
        "draft_file": str(draft_path),
        "draft_id": draft.get("id"),
        "draft_version": draft.get("version"),
        "draft_duration_ms": _milliseconds(draft.get("duration")),
        "source_video": str(source_video.resolve()) if source_video else None,
        "subtitle_counts": {"zh": len(zh_cues), "en": len(en_cues)},
        "audio_track_count": sum(
            track.get("type") == "audio" for track in draft.get("tracks", [])
        ),
        "dialogue_track_indexes": dialogue_tracks,
        "dialogue_segment_count": len(dialogue_segments),
        "spoken_dialogue_segment_count": len(dialogue_plan),
        "missing_dialogue_materials": missing_dialogue,
        "unmatched_zh_cues": sum(
            not row["dialogue_segment_ids"] for row in timeline_rows
        ),
        "untranslated_zh_cues": sum(
            not row["translation_en_draft"] for row in timeline_rows
        ),
    }
    (output_dir / "import-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_timeline_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "cue_index",
        "cue_id",
        "start_ms",
        "end_ms",
        "source_zh",
        "translation_en_draft",
        "dialogue_segment_ids",
        "character_id",
        "translation_status",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            csv_row = dict(row)
            csv_row["dialogue_segment_ids"] = "|".join(row["dialogue_segment_ids"])
            writer.writerow(csv_row)
