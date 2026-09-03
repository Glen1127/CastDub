from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def target_text(utterance: dict[str, Any]) -> str:
    """Return the localized line while keeping legacy English configs valid."""
    return utterance.get("target_text", utterance.get("en", ""))


def _split_caption_text(text: str, max_characters: int = 42) -> list[str]:
    sentences = re.split(r"(?<=[.!?…])\s+", text.strip())
    chunks: list[str] = []
    for sentence in sentences:
        words = sentence.split()
        current: list[str] = []
        for word in words:
            candidate = " ".join([*current, word])
            if current and len(candidate) > max_characters:
                chunks.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            chunks.append(" ".join(current))
    return chunks or [text.strip()]


def build_subtitle_cues(utterances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    for utterance in utterances:
        chunks = _split_caption_text(target_text(utterance))
        audible_duration_ms = min(
            utterance["target_duration_ms"],
            round(
                utterance["speech_duration_ms"]
                / utterance["applied_tempo_ratio"]
            ),
        )
        weights = [max(1, len(re.sub(r"\W", "", chunk))) for chunk in chunks]
        total_weight = sum(weights)
        cursor = utterance["start_ms"]
        utterance_end = cursor + audible_duration_ms
        for index, (chunk, weight) in enumerate(zip(chunks, weights)):
            if index == len(chunks) - 1:
                end_ms = utterance_end
            else:
                share = round(audible_duration_ms * weight / total_weight)
                end_ms = min(utterance_end, cursor + max(300, share))
            cues.append(
                {
                    "utterance_id": utterance["id"],
                    "role": utterance["role"],
                    "start_ms": cursor,
                    "end_ms": end_ms,
                    "text": chunk,
                }
            )
            cursor = end_ms
    return [cue for cue in cues if cue["end_ms"] > cue["start_ms"]]


def _run(args: list[str]) -> None:
    subprocess.run(args, check=True)


def render_dialogue_only(
    utterances: list[dict[str, Any]], duration_ms: int, output_path: Path
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filter_path = output_path.parent / "dialogue-filter.txt"
    inputs: list[str] = []
    chains: list[str] = []
    labels: list[str] = []
    for index, item in enumerate(utterances):
        inputs.extend(["-i", item["fitted_path"]])
        label = f"d{index}"
        chains.append(
            f"[{index}:a]adelay={item['start_ms']}|{item['start_ms']}[{label}]"
        )
        labels.append(f"[{label}]")
    chains.append(
        "".join(labels)
        + f"amix=inputs={len(labels)}:duration=longest:normalize=0,"
        f"alimiter=limit=0.95,aresample=48000,apad,atrim=duration={duration_ms / 1000:.3f}[dialogue]"
    )
    filter_path.write_text(";\n".join(chains) + "\n", encoding="utf-8")
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *inputs,
            "-filter_complex_script",
            str(filter_path),
            "-map",
            "[dialogue]",
            "-c:a",
            "pcm_s24le",
            str(output_path),
        ]
    )
    return output_path


def sync_voice_library(
    project_root: Path,
    config: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
) -> Path:
    series_root = project_root / "asset-library" / "series" / config["series_id"]
    characters_root = series_root / "characters"
    episode_id = config["episode_id"]
    for role_id, profile in profiles.items():
        character_root = characters_root / role_id
        references_root = character_root / "references"
        references_root.mkdir(parents=True, exist_ok=True)
        candidate_path = references_root / f"{episode_id}.wav"
        shutil.copy2(profile["reference_path"], candidate_path)
        selected_path = character_root / "selected.wav"
        selected_was_missing = not selected_path.exists()
        if selected_was_missing:
            shutil.copy2(candidate_path, selected_path)
        profile_path = character_root / "profile.json"
        existing: dict[str, Any] = {}
        if profile_path.is_file():
            existing = json.loads(profile_path.read_text(encoding="utf-8"))
        episodes_seen = sorted(set(existing.get("episodes_seen", [])) | {episode_id})
        candidates = dict(existing.get("candidates", {}))
        candidates[episode_id] = {
            "path": str(candidate_path),
            "source_path": profile["source_path"],
            "source_filename": Path(profile["source_path"]).name,
            "source_start_ms": profile["source_start_ms"],
            "source_duration_ms": profile["source_duration_ms"],
            "transcript": profile["reference_transcript"],
            "status": "selected" if selected_was_missing else "candidate",
        }
        library_profile = {
            "schema_version": 1,
            "series_id": config["series_id"],
            "character_id": role_id,
            "display_name": profile["display_name"],
            "aliases": sorted(
                set(existing.get("aliases", [])) | {profile["display_name"]}
            ),
            "episodes_seen": episodes_seen,
            "selected_reference": str(selected_path),
            "selection_requires_approval": True,
            "candidates": candidates,
        }
        profile_path.write_text(
            json.dumps(library_profile, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    series_path = series_root / "series.json"
    series_episodes: set[str] = {config["episode_id"]}
    if series_path.is_file():
        series_episodes.update(
            json.loads(series_path.read_text(encoding="utf-8")).get(
                "episodes_registered", []
            )
        )
    series_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "series_id": config["series_id"],
                "episodes_registered": sorted(series_episodes),
                "character_count": len(profiles),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return series_root


def build_usage_report(
    config: dict[str, Any],
    utterances: list[dict[str, Any]],
    stage_seconds: dict[str, float],
) -> dict[str, Any]:
    source_chars = sum(len(item["zh"]) for item in utterances)
    target_chars = sum(len(target_text(item)) for item in utterances)
    target_words = sum(len(target_text(item).split()) for item in utterances)
    raw_audio_seconds = sum(item["raw_duration_ms"] for item in utterances) / 1000
    cache_hits = sum(bool(item.get("tts_cache_hit")) for item in utterances)
    generated = len(utterances) - cache_hits
    shared_seconds = sum(
        stage_seconds.get(key, 0.0)
        for key in (
            "voice_profiles_and_library",
            "tts_and_timing_fit",
            "audio_render",
        )
    )
    final_increment_seconds = stage_seconds.get("final_video_mux_and_qc", 0.0)
    estimated_translation_tokens = math.ceil(
        source_chars / 1.5 + target_words * 1.35
    )
    estimated_acoustic_tokens = math.ceil(raw_audio_seconds * 12.5)
    return {
        "schema_version": 1,
        "series_id": config["series_id"],
        "episode_id": config["episode_id"],
        "target_language": config["target_language"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "text": {
            "source_characters": source_chars,
            "target_characters": target_chars,
            "target_words": target_words,
            "estimated_translation_tokens": estimated_translation_tokens,
            "estimate_note": "Heuristic only; the local production pipeline does not expose billed LLM tokens.",
        },
        "tts": {
            "provider": "Qwen3-TTS via MLX-Audio",
            "local_model": True,
            "billed_api_tokens": 0,
            "utterance_count": len(utterances),
            "generated_utterances_this_run": generated,
            "cache_hits_this_run": cache_hits,
            "raw_audio_seconds": round(raw_audio_seconds, 3),
            "estimated_acoustic_tokens_12hz": estimated_acoustic_tokens,
        },
        "orchestration": {
            "codex_tokens": None,
            "note": "Codex application token usage is not available to this local process.",
        },
        "wall_clock_seconds": {
            key: round(value, 3) for key, value in stage_seconds.items()
        },
        "route_comparison": {
            "shared_work": [
                "draft import and character mapping",
                "translation/adaptation",
                "voice profile selection",
                "TTS and timing fit",
                "dialogue-only render",
                "background mix render",
                "subtitles and QC",
            ],
            "editor_package": {
                "additional_work": "package WAV, subtitles, and editable timeline",
                "manual_export_time": "not measured",
                "measured_automated_seconds_this_run": round(shared_seconds, 3),
                "estimated_translation_tokens": estimated_translation_tokens,
                "estimated_acoustic_tokens_12hz": estimated_acoustic_tokens,
            },
            "final_package": {
                "additional_work": "mux mixed audio with unchanged source picture",
                "video_encode_cost": "none; source video stream is copied",
                "measured_automated_seconds_this_run": round(
                    shared_seconds + final_increment_seconds, 3
                ),
                "incremental_seconds_over_editor_route": round(
                    final_increment_seconds, 3
                ),
                "estimated_translation_tokens": estimated_translation_tokens,
                "estimated_acoustic_tokens_12hz": estimated_acoustic_tokens,
            },
        },
    }


def _file_record(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def export_delivery_packages(
    config: dict[str, Any],
    work_dir: Path,
    dialogue_path: Path,
    mix_path: Path,
    outputs: dict[str, str],
    usage_report: dict[str, Any],
) -> dict[str, str]:
    episode = config["episode_id"]
    language = config["target_language"]
    root = work_dir / "deliverables"
    editor_root = root / "editor"
    final_root = root / "final"
    reports_root = root / "reports"
    for path in (editor_root, final_root, reports_root):
        path.mkdir(parents=True, exist_ok=True)

    editor_files = {
        f"{episode}.{language}.dialogue-only.wav": dialogue_path,
        f"{episode}.{language}.full-mix.wav": mix_path,
        f"{episode}.{language}.srt": Path(outputs["english_srt"]),
        f"{episode}.zh-{language}.srt": Path(outputs["bilingual_srt"]),
        f"{episode}.{language}.timeline.jsonl": Path(outputs["timeline"]),
    }
    final_files = {
        f"{episode}.{language}.dub.mp4": Path(outputs["video"]),
        f"{episode}.{language}.srt": Path(outputs["english_srt"]),
        f"{episode}.zh-{language}.srt": Path(outputs["bilingual_srt"]),
        f"{episode}.{language}.qc.json": Path(outputs["qc"]),
    }
    editor_records = []
    for name, source in editor_files.items():
        destination = editor_root / name
        shutil.copy2(source, destination)
        editor_records.append(_file_record(destination))
    final_records = []
    for name, source in final_files.items():
        destination = final_root / name
        shutil.copy2(source, destination)
        final_records.append(_file_record(destination))
    (editor_root / "manifest.json").write_text(
        json.dumps({"purpose": "manual editor replacement", "files": editor_records}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (final_root / "manifest.json").write_text(
        json.dumps({"purpose": "ready-to-review final delivery", "files": final_records}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    usage_path = reports_root / f"{episode}.{language}.usage.json"
    usage_path.write_text(
        json.dumps(usage_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "editor_package": str(editor_root),
        "final_package": str(final_root),
        "usage_report": str(usage_path),
    }
