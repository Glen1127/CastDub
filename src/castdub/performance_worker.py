from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
from pathlib import Path
from typing import Any


TAG = re.compile(r"<\|([^|]+)\|>")
EMOTIONS = {
    "ANGRY": "angry",
    "DISGUSTED": "disgusted",
    "FEARFUL": "fearful",
    "HAPPY": "happy",
    "NEUTRAL": "neutral",
    "SAD": "sad",
    "SURPRISED": "surprised",
}
EVENTS = {
    "Applause": "applause",
    "BGM": "background_music",
    "Cough": "cough",
    "Cry": "crying",
    "Laughter": "laughter",
    "Sneeze": "sneeze",
}


def _normalize(raw: str) -> dict[str, Any]:
    tags = TAG.findall(raw)
    emotion = next((EMOTIONS[tag] for tag in tags if tag in EMOTIONS), "unknown")
    events = [EVENTS[tag] for tag in tags if tag in EVENTS]
    return {
        "emotion": emotion,
        "emotion_intensity": 0.5,
        "speaking_rate": None,
        "pause_boundaries_ms": [],
        "breath_boundaries_ms": [],
        "vocal_events": events,
        "raw": raw,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    args = parser.parse_args(argv)
    references = json.load(sys.stdin)
    if not isinstance(references, list):
        raise ValueError("Worker input must be a JSON list")

    output: list[dict[str, Any]] = []
    with contextlib.redirect_stdout(sys.stderr):
        from funasr import AutoModel

        model = AutoModel(
            model=str(args.model_path.resolve()),
            device="mps",
            disable_update=True,
        )
        for reference in references:
            response = model.generate(
                input=str(Path(reference).resolve()),
                language="auto",
                use_itn=False,
                batch_size=1,
            )
            raw = str(response[0].get("text", "")) if response else ""
            output.append(_normalize(raw))
    json.dump(output, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
