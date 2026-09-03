from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path
from typing import Any


SAMPLE_RATE = 48_000
DURATION_SECONDS = 6
LINES = (
    ("character-a", 500, 1500, 220.0, "Synthetic voice A", "合成角色 A"),
    ("character-b", 2200, 3200, 330.0, "Synthetic voice B", "合成角色 B"),
    ("character-c", 3900, 4900, 440.0, "Synthetic voice C", "合成角色 C"),
)


def _timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def _write_srt(path: Path, bilingual: bool = False) -> None:
    blocks = []
    for index, (_role, start, end, _frequency, target, source) in enumerate(LINES, 1):
        text = f"{source}\n{target}" if bilingual else target
        blocks.append(
            f"{index}\n{_timestamp(start)} --> {_timestamp(end)}\n{text}\n"
        )
    path.write_text("\n".join(blocks), encoding="utf-8")


def _write_audio(path: Path, include_background: bool) -> None:
    frames = bytearray()
    for sample_index in range(SAMPLE_RATE * DURATION_SECONDS):
        time_seconds = sample_index / SAMPLE_RATE
        value = 0.025 * math.sin(2 * math.pi * 110 * time_seconds) if include_background else 0.0
        time_ms = sample_index * 1000 / SAMPLE_RATE
        for _role, start, end, frequency, _target, _source in LINES:
            if start <= time_ms < end:
                value += 0.16 * math.sin(2 * math.pi * frequency * time_seconds)
        pcm = max(-32768, min(32767, round(value * 32767)))
        frames.extend(struct.pack("<hh", pcm, pcm))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(frames)


def _write_ass(path: Path) -> None:
    events = []
    for _role, start, end, _frequency, target, _source in LINES:
        start_s = start / 1000
        end_s = end / 1000
        start_ass = f"0:{int(start_s // 60):02}:{start_s % 60:05.2f}"
        end_ass = f"0:{int(end_s // 60):02}:{end_s % 60:05.2f}"
        events.append(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{target}")
    path.write_text(
        """[Script Info]
ScriptType: v4.00+
PlayResX: 640
PlayResY: 360

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Default,Arial,20,&H00FFFFFF,&H00000000,0,1,2,1,2,20,20,18

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        + "\n".join(events)
        + "\n",
        encoding="utf-8",
    )


def _render_video(audio_path: Path, subtitle_path: Path, output_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to render the synthetic demo")
    escaped_subtitle = str(subtitle_path).replace("\\", "\\\\").replace("'", "\\'")
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x18202a:s=640x360:r=24:d={DURATION_SECONDS}",
            "-i",
            str(audio_path),
            "-vf",
            f"ass='{escaped_subtitle}'",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ],
        check=True,
    )


def render_synthetic_demo(output_dir: Path) -> dict[str, Any]:
    root = output_dir.expanduser().resolve()
    editor = root / "editor"
    final = root / "final"
    reports = root / "reports"
    for directory in (editor, final, reports):
        directory.mkdir(parents=True, exist_ok=True)

    dialogue = editor / "EP00.en-US.dialogue-only.wav"
    full_mix = editor / "EP00.en-US.full-mix.wav"
    target_srt = editor / "EP00.en-US.srt"
    bilingual_srt = editor / "EP00.zh-en-US.srt"
    timeline = editor / "EP00.en-US.timeline.jsonl"
    ass = final / "EP00.en-US.ass"
    video = final / "EP00.en-US.dub.mp4"
    qc = reports / "EP00.en-US.qc.json"

    _write_audio(dialogue, include_background=False)
    _write_audio(full_mix, include_background=True)
    _write_srt(target_srt)
    _write_srt(bilingual_srt, bilingual=True)
    timeline.write_text(
        "".join(
            json.dumps(
                {
                    "utterance_id": f"u{index:03}",
                    "role": role,
                    "start_ms": start,
                    "end_ms": end,
                    "source_text": source,
                    "target_text": target,
                    "provider": "synthetic-tone",
                },
                ensure_ascii=False,
            )
            + "\n"
            for index, (role, start, end, _frequency, target, source) in enumerate(LINES, 1)
        ),
        encoding="utf-8",
    )
    _write_ass(ass)
    _render_video(full_mix, ass, video)
    qc.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "synthetic_demo": True,
                "status": "pass",
                "characters": 3,
                "duration_ms": DURATION_SECONDS * 1000,
                "subtitle_alignment": 2,
                "subtitle_margin_v": 18,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "demo_ok": True,
        "synthetic_only": True,
        "output_dir": str(root),
        "dialogue": str(dialogue),
        "mix": str(full_mix),
        "target_srt": str(target_srt),
        "bilingual_srt": str(bilingual_srt),
        "timeline": str(timeline),
        "video": str(video),
        "qc": str(qc),
    }
