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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _srt_time(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _vtt_time(milliseconds: int) -> str:
    return _srt_time(milliseconds).replace(",", ".")


def _ass_time(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, centiseconds = divmod(remainder, 10)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _bounds(row: dict[str, Any]) -> tuple[int, int]:
    start = int(row["start_ms"])
    duration = int(row.get("fitted_duration_ms") or row["target_duration_ms"])
    return start, start + duration


def _write_subtitles(
    takes: list[dict[str, Any]], output_dir: Path, episode: str, language: str
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    target_srt = output_dir / f"{episode}.{language}.srt"
    bilingual_srt = output_dir / f"{episode}.zh-{language}.srt"
    target_vtt = output_dir / f"{episode}.{language}.vtt"
    target_ass = output_dir / f"{episode}.{language}.ass"

    target_blocks: list[str] = []
    bilingual_blocks: list[str] = []
    vtt_blocks = ["WEBVTT\n"]
    ass_lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
        "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,"
        "Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,"
        "MarginV,Encoding",
        "Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
        "0,0,0,0,100,100,0,0,1,2,1,2,24,24,18,1",
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    for index, row in enumerate(takes, start=1):
        start, end = _bounds(row)
        target = str(row["target_text"]).strip()
        source = str(row.get("reference_text", "")).strip()
        target_blocks.append(
            f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n{target}\n"
        )
        bilingual_blocks.append(
            f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n"
            f"{source}\n{target}\n"
        )
        vtt_blocks.append(f"{_vtt_time(start)} --> {_vtt_time(end)}\n{target}\n")
        escaped = target.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        ass_lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{escaped}"
        )
    target_srt.write_text("\n".join(target_blocks), encoding="utf-8")
    bilingual_srt.write_text("\n".join(bilingual_blocks), encoding="utf-8")
    target_vtt.write_text("\n".join(vtt_blocks), encoding="utf-8")
    target_ass.write_text("\n".join(ass_lines) + "\n", encoding="utf-8")
    return {
        "target_srt": target_srt,
        "bilingual_srt": bilingual_srt,
        "target_vtt": target_vtt,
        "target_ass": target_ass,
    }


def _filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def render_delivery(store_path: Path, job_id: str) -> dict[str, Any]:
    job = get_episode_job(store_path, job_id)
    work_dir = episode_work_dir(store_path, job)
    manifest_path = work_dir / "deliverables" / "manifest.json"
    if job["status"] == "render_completed" and manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {"ok": True, "cache_hit": True, "status": job["status"], **manifest}
    if job["status"] != "mix_completed":
        raise JobStateError(
            f"Cannot render delivery for {job_id} from {job['status']}; "
            "expected mix_completed"
        )

    takes = _read_jsonl(work_dir / "synthesis" / "takes.approved.v1.jsonl")
    if not takes:
        raise JobStateError("Cannot render delivery with no approved takes")
    editor_dir = work_dir / "deliverables" / "editor"
    subtitle_paths = _write_subtitles(
        takes, editor_dir, job["episode_id"], job["target_language"]
    )
    mix_manifest = json.loads(
        (work_dir / "mix" / "manifest.json").read_text(encoding="utf-8")
    )
    dialogue_source = Path(mix_manifest["dialogue_only"])
    mix_source = Path(mix_manifest["full_mix"])
    if not dialogue_source.is_file() or not mix_source.is_file():
        raise JobStateError("Mix masters are missing")
    dialogue_delivery = editor_dir / dialogue_source.name
    mix_delivery = editor_dir / mix_source.name
    shutil.copy2(dialogue_source, dialogue_delivery)
    shutil.copy2(mix_source, mix_delivery)
    timeline_delivery = editor_dir / f"{job['episode_id']}.{job['target_language']}.timeline.jsonl"
    timeline_delivery.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in takes),
        encoding="utf-8",
    )

    final_video: Path | None = None
    if job["output_mode"] == "final":
        source_video = Path(job["source_video"])
        if not source_video.is_file():
            raise JobStateError(f"Clean no-subtitle master is missing: {source_video}")
        final_dir = work_dir / "deliverables" / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        final_video = final_dir / f"{job['episode_id']}.{job['target_language']}.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source_video),
                "-i",
                str(mix_source),
                "-vf",
                f"ass='{_filter_path(subtitle_paths['target_ass'])}'",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                "-movflags",
                "+faststart",
                str(final_video),
            ],
            check=True,
        )
        for path in subtitle_paths.values():
            shutil.copy2(path, final_dir / path.name)

    manifest = {
        "job_id": job_id,
        "output_mode": job["output_mode"],
        "utterance_count": len(takes),
        "dialogue_only": str(dialogue_delivery),
        "full_mix": str(mix_delivery),
        "timeline": str(timeline_delivery),
        **{name: str(path) for name, path in subtitle_paths.items()},
        "final_video": str(final_video) if final_video else None,
        "subtitle_style": {
            "font": "Arial",
            "font_size": 20,
            "alignment": 2,
            "margin_v": 18,
            "outline": 2,
            "shadow": 1,
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    updated = advance_episode_job(
        store_path, job_id, "render_completed", {"manifest": str(manifest_path)}
    )
    return {"ok": True, "cache_hit": False, "status": updated["status"], **manifest}
