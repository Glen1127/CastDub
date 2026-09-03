from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from castdub.jianying import extract_audio_segments, load_main_draft
from castdub.production import (
    build_subtitle_cues,
    build_usage_report,
    export_delivery_packages,
    render_dialogue_only,
    sync_voice_library,
    target_text,
)


class PilotError(RuntimeError):
    pass


def _run(args: list[str], cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def _duration_ms(path: Path) -> int:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return round(float(result.stdout.strip()) * 1000)


def load_pilot_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    role_ids = set(config["roles"])
    for item in config["utterances"]:
        if item["role"] not in role_ids:
            raise PilotError(f"Unknown role {item['role']} in {item['id']}")
        if item["end_ms"] <= item["start_ms"]:
            raise PilotError(f"Invalid time range in {item['id']}")
    return config


def _resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else project_root / path


def prepare_voice_profiles(
    project_root: Path, config: dict[str, Any], work_dir: Path
) -> dict[str, dict[str, Any]]:
    draft_root = _resolve_project_path(project_root, config["draft_root"])
    profiles: dict[str, dict[str, Any]] = {}
    for role_id, role in config["roles"].items():
        role_dir = work_dir / "voice-profiles" / role_id
        role_dir.mkdir(parents=True, exist_ok=True)
        reference_path = role_dir / "reference.wav"
        source_path = draft_root / role["source"]
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{role['start_ms'] / 1000:.3f}",
                "-t",
                f"{role['duration_ms'] / 1000:.3f}",
                "-i",
                str(source_path),
                "-ac",
                "1",
                "-ar",
                "24000",
                str(reference_path),
            ]
        )
        profile = {
            "role_id": role_id,
            "display_name": role["display_name"],
            "reference_path": str(reference_path),
            "reference_transcript": role["transcript"],
            "source_path": str(source_path),
            "source_start_ms": role["start_ms"],
            "source_duration_ms": role["duration_ms"],
            "voice_reuse_scope": role_id,
        }
        (role_dir / "profile.json").write_text(
            json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        profiles[role_id] = profile
    return profiles


def prepare_performance_references(
    project_root: Path, config: dict[str, Any], work_dir: Path
) -> dict[str, dict[str, str]]:
    draft_root = _resolve_project_path(project_root, config["draft_root"])
    reference_dir = work_dir / "performance-references"
    reference_dir.mkdir(parents=True, exist_ok=True)
    references: dict[str, dict[str, str]] = {}
    for utterance in config["utterances"]:
        source = utterance.get("performance_reference")
        if not source:
            continue
        output_path = reference_dir / f"{utterance['id']}.wav"
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{source['start_ms'] / 1000:.3f}",
                "-t",
                f"{source['duration_ms'] / 1000:.3f}",
                "-i",
                str(draft_root / source["source"]),
                "-ac",
                "1",
                "-ar",
                "24000",
                str(output_path),
            ]
        )
        references[utterance["id"]] = {
            "path": str(output_path),
            "transcript": source["transcript"],
        }
    return references


def _synthesis_fingerprint(
    utterance: dict[str, Any], reference_path: str, reference_text: str
) -> str:
    reference_digest = hashlib.sha256(Path(reference_path).read_bytes()).hexdigest()
    payload = {
        "version": 2,
        "text": target_text(utterance),
        "role": utterance["role"],
        "emotion": utterance.get("emotion"),
        "reference_sha256": reference_digest,
        "reference_text": reference_text,
        "temperature": 0.65,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def synthesize_dialogue(
    config: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    performance_references: dict[str, dict[str, str]],
    work_dir: Path,
) -> list[dict[str, Any]]:
    mlx_root = Path(config["mlx_audio_root"])
    import sys

    sys.path.insert(0, str(mlx_root))
    from mlx_audio.tts.generate import generate_audio
    from mlx_audio.tts.utils import load_model

    raw_dir = work_dir / "synthesis" / "raw"
    cleaned_dir = work_dir / "synthesis" / "cleaned"
    fitted_dir = work_dir / "synthesis" / "fitted"
    raw_dir.mkdir(parents=True, exist_ok=True)
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    fitted_dir.mkdir(parents=True, exist_ok=True)
    fingerprints: dict[str, str] = {}
    selected_references: dict[str, tuple[str, str]] = {}
    missing_raw: set[str] = set()
    for item in config["utterances"]:
        role = profiles[item["role"]]
        performance = performance_references.get(item["id"])
        reference_path = performance["path"] if performance else role["reference_path"]
        reference_text = (
            performance["transcript"]
            if performance
            else role["reference_transcript"]
        )
        selected_references[item["id"]] = (reference_path, reference_text)
        fingerprint = _synthesis_fingerprint(item, reference_path, reference_text)
        fingerprints[item["id"]] = fingerprint
        raw_path = raw_dir / f"{item['id']}_000.wav"
        metadata_path = raw_dir / f"{item['id']}.json"
        cached_fingerprint = None
        if metadata_path.is_file():
            cached_fingerprint = json.loads(
                metadata_path.read_text(encoding="utf-8")
            ).get("fingerprint")
        if not raw_path.is_file() or cached_fingerprint != fingerprint:
            missing_raw.add(item["id"])
    model = load_model(config["model_path"]) if missing_raw else None
    results: list[dict[str, Any]] = []
    for utterance in config["utterances"]:
        raw_path = raw_dir / f"{utterance['id']}_000.wav"
        metadata_path = raw_dir / f"{utterance['id']}.json"
        reference_path, reference_text = selected_references[utterance["id"]]
        if utterance["id"] in missing_raw:
            if model is None:
                raise PilotError("TTS model was not loaded for a cache miss")
            if raw_path.is_file():
                revisions = work_dir / "synthesis" / "revisions" / "pre-fingerprint"
                revisions.mkdir(parents=True, exist_ok=True)
                destination = revisions / raw_path.name
                if destination.exists():
                    destination = revisions / f"{utterance['id']}-{time.time_ns()}.wav"
                shutil.move(raw_path, destination)
            generate_audio(
                text=target_text(utterance),
                model=model,
                max_tokens=max(80, round((utterance["end_ms"] - utterance["start_ms"]) / 35)),
                lang_code=config.get("tts_language", "english"),
                ref_audio=reference_path,
                ref_text=reference_text,
                output_path=str(raw_dir),
                file_prefix=utterance["id"],
                audio_format="wav",
                verbose=False,
                temperature=0.65,
            )
            metadata_path.write_text(
                json.dumps(
                    {
                        "fingerprint": fingerprints[utterance["id"]],
                        "text": target_text(utterance),
                        "role": utterance["role"],
                        "emotion": utterance.get("emotion"),
                        "reference_path": reference_path,
                        "reference_text": reference_text,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        if not raw_path.is_file():
            raise PilotError(f"TTS did not produce {raw_path}")
        raw_duration = _duration_ms(raw_path)
        cleaned_path = cleaned_dir / f"{utterance['id']}.wav"
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(raw_path),
                "-af",
                "silenceremove=start_periods=1:start_duration=0.02:start_threshold=-45dB:stop_periods=-1:stop_duration=0.04:stop_threshold=-45dB",
                str(cleaned_path),
            ]
        )
        speech_duration = _duration_ms(cleaned_path)
        target_duration = utterance["end_ms"] - utterance["start_ms"]
        tempo = speech_duration / target_duration
        applied_tempo = max(1.0, tempo)
        fitted_path = fitted_dir / f"{utterance['id']}.wav"
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(cleaned_path),
                "-af",
                f"rubberband=tempo={applied_tempo:.8f}:formant=preserved,apad,atrim=duration={target_duration / 1000:.3f}",
                "-ar",
                "48000",
                "-ac",
                "2",
                str(fitted_path),
            ]
        )
        results.append(
            {
                **utterance,
                "target_duration_ms": target_duration,
                "raw_path": str(raw_path),
                "raw_duration_ms": raw_duration,
                "cleaned_path": str(cleaned_path),
                "speech_duration_ms": speech_duration,
                "fitted_path": str(fitted_path),
                "tempo_ratio": round(tempo, 4),
                "applied_tempo_ratio": round(applied_tempo, 4),
                "duration_fit_status": "pass" if tempo <= 1.25 else "review",
                "tts_cache_hit": utterance["id"] not in missing_raw,
                "emotion": utterance.get("emotion"),
                "synthesis_reference_path": reference_path,
                "synthesis_reference_mode": (
                    "episode_performance"
                    if utterance["id"] in performance_references
                    else "stable_character"
                ),
            }
        )
    return results


def _is_background_segment(segment: Any) -> bool:
    if segment.material_type in {"sound", "music"}:
        return True
    return segment.track_index == 6 and segment.target_start_ms == 2467


def render_mix(
    project_root: Path,
    config: dict[str, Any],
    utterances: list[dict[str, Any]],
    work_dir: Path,
) -> Path:
    draft_root = _resolve_project_path(project_root, config["draft_root"])
    draft, _ = load_main_draft(draft_root)
    audio_segments, _ = extract_audio_segments(draft_root, draft)
    background = [item for item in audio_segments if _is_background_segment(item)]
    source_duration_ms = _duration_ms(
        _resolve_project_path(project_root, config["source_video"])
    )
    filter_path = work_dir / "logs" / "mix-filter.txt"
    filter_path.parent.mkdir(parents=True, exist_ok=True)
    inputs: list[str] = []
    chains: list[str] = []
    labels: list[str] = []
    for index, item in enumerate(background):
        inputs.extend(["-i", item.source_path])
        tempo = item.source_duration_ms / item.target_duration_ms
        label = f"bg{index}"
        chains.append(
            f"[{index}:a]atrim=start={item.source_start_ms / 1000:.3f}:duration={item.source_duration_ms / 1000:.3f},"
            f"asetpts=PTS-STARTPTS,rubberband=tempo={tempo:.8f},volume={item.volume:.8f},"
            f"apad,atrim=duration={item.target_duration_ms / 1000:.3f},"
            f"adelay={item.target_start_ms}|{item.target_start_ms}[{label}]"
        )
        labels.append(f"[{label}]")
    offset = len(background)
    for index, item in enumerate(utterances):
        inputs.extend(["-i", item["fitted_path"]])
        label = f"dx{index}"
        chains.append(
            f"[{offset + index}:a]adelay={item['start_ms']}|{item['start_ms']}[{label}]"
        )
        labels.append(f"[{label}]")
    chains.append(
        "".join(labels)
        + f"amix=inputs={len(labels)}:duration=longest:normalize=0,"
        f"alimiter=limit=0.95,aresample=48000,apad,atrim=duration={source_duration_ms / 1000:.3f}[mix]"
    )
    filter_path.write_text(";\n".join(chains) + "\n", encoding="utf-8")
    mix_path = (
        work_dir
        / "mix"
        / f"{config['episode_id']}.{config['target_language']}.full-mix.wav"
    )
    mix_path.parent.mkdir(parents=True, exist_ok=True)
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
            "[mix]",
            "-c:a",
            "pcm_s24le",
            str(mix_path),
        ]
    )
    return mix_path


def _srt_timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def write_deliverables(
    project_root: Path,
    config: dict[str, Any],
    utterances: list[dict[str, Any]],
    mix_path: Path,
    work_dir: Path,
) -> dict[str, str]:
    subtitles_dir = work_dir / "subtitles"
    output_dir = work_dir / "output"
    qc_dir = work_dir / "qc"
    subtitles_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    qc_dir.mkdir(parents=True, exist_ok=True)
    episode = config["episode_id"]
    language = config["target_language"]
    en_srt = subtitles_dir / f"{episode}.{language}.srt"
    bilingual_srt = subtitles_dir / f"{episode}.zh-{language}.srt"
    en_blocks: list[str] = []
    bilingual_blocks: list[str] = []
    subtitle_cues = build_subtitle_cues(utterances)
    for index, cue in enumerate(subtitle_cues, start=1):
        timing = f"{_srt_timestamp(cue['start_ms'])} --> {_srt_timestamp(cue['end_ms'])}"
        en_blocks.append(f"{index}\n{timing}\n{cue['text']}\n")
    for index, item in enumerate(utterances, start=1):
        audible_duration_ms = min(
            item["target_duration_ms"],
            round(item["speech_duration_ms"] / item["applied_tempo_ratio"]),
        )
        audible_end_ms = item["start_ms"] + audible_duration_ms
        timing = f"{_srt_timestamp(item['start_ms'])} --> {_srt_timestamp(audible_end_ms)}"
        bilingual_blocks.append(
            f"{index}\n{timing}\n{item['zh']}\n{target_text(item)}\n"
        )
    en_srt.write_text("\n".join(en_blocks), encoding="utf-8")
    bilingual_srt.write_text("\n".join(bilingual_blocks), encoding="utf-8")
    final_video = output_dir / f"{episode}.{language}.dub.mp4"
    source_video = _resolve_project_path(project_root, config["source_video"])
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source_video),
            "-i",
            str(mix_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "256k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(final_video),
        ]
    )
    report = {
        "project_id": config["project_id"],
        "target_language": config["target_language"],
        "source_video": str(source_video),
        "output_video": str(final_video),
        "utterance_count": len(utterances),
        "character_count": len(config["roles"]),
        "timing_review_count": sum(
            item["duration_fit_status"] != "pass" for item in utterances
        ),
        "subtitle_cue_count": len(subtitle_cues),
        "subtitle_timing_basis": "final synthesized speech bounds with proportional intra-utterance allocation",
        "utterances": utterances,
    }
    qc_path = qc_dir / "qc-report.json"
    qc_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    timeline_path = work_dir / f"timeline.{language}.jsonl"
    timeline_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in utterances),
        encoding="utf-8",
    )
    return {
        "video": str(final_video),
        "english_srt": str(en_srt),
        "bilingual_srt": str(bilingual_srt),
        "timeline": str(timeline_path),
        "qc": str(qc_path),
    }


def run_pilot(project_root: Path, config_path: Path, work_dir: Path) -> dict[str, str]:
    project_root = project_root.resolve()
    config = load_pilot_config(config_path.resolve())
    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    stage_seconds: dict[str, float] = {}

    started = time.perf_counter()
    profiles = prepare_voice_profiles(project_root, config, work_dir)
    performance_references = prepare_performance_references(
        project_root, config, work_dir
    )
    sync_voice_library(project_root, config, profiles)
    stage_seconds["voice_profiles_and_library"] = time.perf_counter() - started

    started = time.perf_counter()
    utterances = synthesize_dialogue(
        config, profiles, performance_references, work_dir
    )
    stage_seconds["tts_and_timing_fit"] = time.perf_counter() - started

    started = time.perf_counter()
    duration_ms = _duration_ms(
        _resolve_project_path(project_root, config["source_video"])
    )
    dialogue_path = render_dialogue_only(
        utterances,
        duration_ms,
        work_dir / "mix" / f"{config['episode_id']}.{config['target_language']}.dialogue-only.wav",
    )
    mix_path = render_mix(project_root, config, utterances, work_dir)
    stage_seconds["audio_render"] = time.perf_counter() - started

    started = time.perf_counter()
    outputs = write_deliverables(project_root, config, utterances, mix_path, work_dir)
    stage_seconds["final_video_mux_and_qc"] = time.perf_counter() - started

    usage_report = build_usage_report(config, utterances, stage_seconds)
    packages = export_delivery_packages(
        config, work_dir, dialogue_path, mix_path, outputs, usage_report
    )
    return {**outputs, **packages, "voice_library": str(project_root / "asset-library" / "series" / config["series_id"])}
