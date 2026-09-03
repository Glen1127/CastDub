from __future__ import annotations

import copy
import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from castdub.jianying import load_main_draft
from castdub.production import build_subtitle_cues


class JianyingExportError(RuntimeError):
    pass


def _new_id() -> str:
    return str(uuid.uuid4()).upper()


def _overlaps_dialogue(segment: dict[str, Any], utterances: list[dict[str, Any]]) -> bool:
    timerange = segment.get("target_timerange", {})
    start_ms = round(timerange.get("start", 0) / 1000)
    end_ms = start_ms + round(timerange.get("duration", 0) / 1000)
    return any(
        max(start_ms, item["start_ms"]) < min(end_ms, item["end_ms"])
        for item in utterances
    )


def _english_text_track_index(draft: dict[str, Any]) -> int:
    materials = {
        item["id"]: item for item in draft.get("materials", {}).get("texts", [])
    }
    candidates: list[tuple[int, int]] = []
    for index, track in enumerate(draft.get("tracks", [])):
        if track.get("type") != "text":
            continue
        english = 0
        for segment in track.get("segments", []):
            material = materials.get(segment.get("material_id"), {})
            try:
                text = json.loads(material.get("content", "{}")).get("text", "")
            except json.JSONDecodeError:
                text = ""
            english += bool(text and not re.search(r"[\u3400-\u9fff]", text))
        candidates.append((english, index))
    if not candidates or max(candidates)[0] == 0:
        raise JianyingExportError("No English subtitle track found")
    return max(candidates)[1]


def _replace_english_subtitles(
    draft: dict[str, Any], utterances: list[dict[str, Any]]
) -> tuple[int, int]:
    track_index = _english_text_track_index(draft)
    track = draft["tracks"][track_index]
    # Jianying stores track visibility in ``attribute`` (and mirrors it on
    # segments).  The source English reference track is hidden, so explicitly
    # show the rebuilt target-language track and hide the source-language
    # subtitle track for the final localized render.
    for index, text_track in enumerate(draft.get("tracks", [])):
        if text_track.get("type") != "text":
            continue
        if index == track_index:
            text_track.pop("attribute", None)
            for text_segment in text_track.get("segments", []):
                text_segment.pop("track_attribute", None)
        else:
            text_track["attribute"] = 2
            for text_segment in text_track.get("segments", []):
                text_segment["track_attribute"] = 2
    old_segments = track.get("segments", [])
    if not old_segments:
        raise JianyingExportError("English subtitle track has no template segment")
    text_materials = draft["materials"]["texts"]
    materials_by_id = {item["id"]: item for item in text_materials}
    old_material_ids = {item.get("material_id") for item in old_segments}
    template_material = materials_by_id[old_segments[0]["material_id"]]
    cues = build_subtitle_cues(utterances)
    new_materials: list[dict[str, Any]] = []
    new_segments: list[dict[str, Any]] = []
    base_render_index = min(item.get("render_index", 0) for item in old_segments)
    for index, cue in enumerate(cues):
        material = copy.deepcopy(template_material)
        material["id"] = _new_id()
        content = json.loads(material["content"])
        content["text"] = cue["text"]
        for style in content.get("styles", []):
            style["range"] = [0, len(cue["text"])]
        material["content"] = json.dumps(
            content, ensure_ascii=False, separators=(",", ":")
        )
        material["group_id"] = f"castdub-{cue['utterance_id']}"
        segment = copy.deepcopy(old_segments[index % len(old_segments)])
        segment["id"] = _new_id()
        segment["material_id"] = material["id"]
        segment["target_timerange"] = {
            "start": cue["start_ms"] * 1000,
            "duration": (cue["end_ms"] - cue["start_ms"]) * 1000,
        }
        segment["render_index"] = base_render_index + index
        segment["track_render_index"] = track_index
        segment.pop("track_attribute", None)
        new_materials.append(material)
        new_segments.append(segment)
    draft["materials"]["texts"] = [
        item for item in text_materials if item["id"] not in old_material_ids
    ] + new_materials
    track["segments"] = new_segments
    return track_index, len(cues)


def _replace_dialogue_audio(
    draft: dict[str, Any], utterances: list[dict[str, Any]], dialogue_name: str
) -> tuple[int, int, int]:
    audio_materials = draft["materials"]["audios"]
    materials_by_id = {item["id"]: item for item in audio_materials}
    scored_tracks: list[tuple[int, int]] = []
    for index, track in enumerate(draft.get("tracks", [])):
        if track.get("type") != "audio":
            continue
        dialogue_count = sum(
            _overlaps_dialogue(segment, utterances)
            and materials_by_id.get(segment.get("material_id"), {}).get("type")
            not in {"sound", "music"}
            for segment in track.get("segments", [])
        )
        scored_tracks.append((dialogue_count, index))
    if not scored_tracks or max(scored_tracks)[0] == 0:
        raise JianyingExportError("No dialogue audio track found")
    dialogue_track_index = max(scored_tracks)[1]
    removed = 0
    preserved = 0
    for track in draft["tracks"]:
        if track.get("type") != "audio":
            continue
        kept = []
        for segment in track.get("segments", []):
            material_type = materials_by_id.get(segment.get("material_id"), {}).get(
                "type"
            )
            if material_type in {"sound", "music"} or not _overlaps_dialogue(
                segment, utterances
            ):
                kept.append(segment)
                preserved += 1
            else:
                removed += 1
        track["segments"] = kept

    template_material = copy.deepcopy(audio_materials[0])
    material_id = _new_id()
    duration_us = int(draft["duration"])
    placeholder_prefix = template_material.get("path", "").split("##/", 1)[0]
    if placeholder_prefix:
        stored_path = f"{placeholder_prefix}##/materials/audio/{dialogue_name}"
    else:
        stored_path = f"materials/audio/{dialogue_name}"
    template_material.update(
        {
            "id": material_id,
            "type": "extract_music",
            "name": dialogue_name,
            "duration": duration_us,
            "path": stored_path,
            "music_id": "",
            "resource_id": "",
            "local_material_id": _new_id(),
        }
    )
    draft["materials"]["audios"].append(template_material)
    target_track = draft["tracks"][dialogue_track_index]
    segment_template = copy.deepcopy(
        target_track["segments"][0]
        if target_track["segments"]
        else next(
            track["segments"][0]
            for track in draft["tracks"]
            if track.get("type") == "audio" and track.get("segments")
        )
    )
    segment_template.update(
        {
            "id": _new_id(),
            "source_timerange": {"start": 0, "duration": duration_us},
            "target_timerange": {"start": 0, "duration": duration_us},
            "speed": 1.0,
            "volume": 1.0,
            "material_id": material_id,
            "extra_material_refs": [],
            "track_render_index": dialogue_track_index,
        }
    )
    target_track["segments"].append(segment_template)
    target_track["segments"].sort(
        key=lambda item: item.get("target_timerange", {}).get("start", 0)
    )
    return dialogue_track_index, removed, preserved


def export_localized_draft(
    source_draft_root: Path,
    output_draft_root: Path,
    dialogue_wav: Path,
    qc_report: Path,
) -> dict[str, Any]:
    source_draft_root = source_draft_root.resolve()
    output_draft_root = output_draft_root.resolve()
    dialogue_wav = dialogue_wav.resolve()
    if output_draft_root.exists():
        raise JianyingExportError(f"Output already exists: {output_draft_root}")
    report = json.loads(qc_report.read_text(encoding="utf-8"))
    utterances = report["utterances"]
    shutil.copytree(source_draft_root, output_draft_root)
    draft, _ = load_main_draft(output_draft_root)
    source_draft_id = draft.get("id")
    draft["id"] = _new_id()
    audio_dir = output_draft_root / "materials" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    localized_audio = audio_dir / dialogue_wav.name
    shutil.copy2(dialogue_wav, localized_audio)
    text_track, subtitle_count = _replace_english_subtitles(draft, utterances)
    audio_track, removed_audio, preserved_audio = _replace_dialogue_audio(
        draft, utterances, localized_audio.name
    )
    draft_path = output_draft_root / "draft_content.json"
    draft_path.write_text(
        json.dumps(draft, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    export_report = {
        "schema_version": 1,
        "source_draft": str(source_draft_root),
        "source_draft_id": source_draft_id,
        "localized_draft_id": draft["id"],
        "output_draft": str(output_draft_root),
        "dialogue_audio": str(localized_audio),
        "dialogue_track_index": audio_track,
        "removed_dialogue_audio_segments": removed_audio,
        "preserved_music_effect_segments": preserved_audio,
        "english_text_track_index": text_track,
        "english_subtitle_segments": subtitle_count,
    }
    (output_draft_root / "castdub-export-report.json").write_text(
        json.dumps(export_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return export_report
