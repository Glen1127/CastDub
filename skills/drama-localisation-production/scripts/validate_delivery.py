#!/usr/bin/env python3
"""Validate required episode deliverables without modifying them."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def duration_ms(path: Path) -> int:
    value = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return round(float(value) * 1000)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--episode", required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--duration-tolerance-ms", type=int, default=1000)
    args = parser.parse_args()

    base = args.work_dir.resolve()
    stem = f"{args.episode}.{args.language}"
    required = {
        "dialogue": base / "deliverables" / "editor" / f"{stem}.dialogue-only.wav",
        "mix": base / "deliverables" / "editor" / f"{stem}.full-mix.wav",
        "subtitle": base / "deliverables" / "editor" / f"{stem}.srt",
        "timeline": base / "deliverables" / "editor" / f"{stem}.timeline.jsonl",
        "qc": base / "deliverables" / "final" / f"{stem}.qc.json",
    }
    videos = list((base / "deliverables" / "final").glob(f"{stem}*.mp4"))
    missing = [name for name, path in required.items() if not path.is_file()]
    if not videos:
        missing.append("video")
    errors = [f"missing {name}" for name in missing]
    qc = {}
    if required["qc"].is_file():
        qc = json.loads(required["qc"].read_text(encoding="utf-8"))
        if qc.get("timing_review_count", 0):
            errors.append(f"timing reviews: {qc['timing_review_count']}")
    durations = {}
    for name in ("dialogue", "mix"):
        if required[name].is_file():
            durations[name] = duration_ms(required[name])
    if videos:
        durations["video"] = duration_ms(videos[0])
    if durations and max(durations.values()) - min(durations.values()) > args.duration_tolerance_ms:
        errors.append(f"delivery duration mismatch: {durations}")
    report = {
        "ok": not errors,
        "episode": args.episode,
        "language": args.language,
        "durations_ms": durations,
        "video": str(videos[0]) if videos else None,
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
