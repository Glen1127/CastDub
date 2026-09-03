#!/usr/bin/env python3
"""Portable, read-only preflight for a draft + clean-master episode pair."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def duration_ms(path: Path) -> int:
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


def one(items: list[Path], label: str) -> Path:
    if len(items) != 1:
        names = [str(item) for item in items[:5]]
        raise ValueError(f"Expected one {label}; found {len(items)}: {names}")
    return items[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--episode", required=True)
    parser.add_argument("--draft", type=Path)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--rights-confirmed", action="store_true")
    parser.add_argument("--duration-tolerance-ms", type=int, default=1000)
    args = parser.parse_args()

    root = args.project_root.resolve()
    episode = args.episode.strip()
    errors: list[str] = []
    try:
        draft_root = args.draft.resolve() if args.draft else one(
            [
                path
                for path in (root / "resource" / "剧集Project").iterdir()
                if path.is_dir() and path.name.strip().casefold() == episode.casefold()
            ],
            "matching draft directory",
        )
        video = args.video.resolve() if args.video else one(
            [
                path
                for path in (root / "resource" / "剧集").iterdir()
                if path.is_file()
                and episode.casefold() in path.name.casefold()
                and "无字幕" in path.name
            ],
            "matching no-subtitle video",
        )
        draft_file = one(list(draft_root.glob("draft_content.json")), "draft_content.json")
        draft = json.loads(draft_file.read_text(encoding="utf-8"))
        draft_duration = round(int(draft.get("duration", 0)) / 1000)
        video_duration = duration_ms(video)
        delta = abs(draft_duration - video_duration)
        if delta > args.duration_tolerance_ms:
            errors.append(f"duration mismatch: {delta} ms")
        if not args.rights_confirmed:
            errors.append("rights not explicitly confirmed")
        tracks = draft.get("tracks", [])
        report = {
            "ok": not errors,
            "episode": episode,
            "draft_root": str(draft_root),
            "draft_file": str(draft_file),
            "clean_video": str(video),
            "draft_duration_ms": draft_duration,
            "video_duration_ms": video_duration,
            "duration_delta_ms": delta,
            "track_counts": {
                kind: sum(track.get("type") == kind for track in tracks)
                for kind in ("video", "audio", "text", "effect")
            },
            "rights_confirmed": args.rights_confirmed,
            "errors": errors,
        }
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        report = {"ok": False, "episode": episode, "errors": [str(exc)]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
