from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


LANGUAGE_CODES = {
    "en": "english",
    "es": "spanish",
    "fr": "french",
    "de": "german",
    "it": "italian",
    "ja": "japanese",
    "ko": "korean",
    "pt": "portuguese",
    "ru": "russian",
    "zh": "chinese",
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    args = parser.parse_args(argv)
    requests = json.load(sys.stdin)
    if not isinstance(requests, list):
        raise ValueError("Worker input must be a JSON list")

    import mlx.core as mx
    import numpy as np
    from mlx_audio.audio_io import write as audio_write
    from mlx_audio.tts.utils import load_model

    model = load_model(str(args.model_path.resolve()))
    outputs: list[str] = []
    for request in requests:
        output_path = Path(request["output_path"]).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        language = LANGUAGE_CODES.get(
            str(request["target_language"]).split("-", 1)[0].lower(), "auto"
        )
        chunks = [
            result.audio
            for result in model.generate(
                text=request["target_text"],
                lang_code=language,
                ref_audio=request["performance_reference"],
                ref_text=request["reference_text"],
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.5,
                verbose=False,
            )
        ]
        if not chunks:
            raise RuntimeError(f"No audio generated for {request['utterance_id']}")
        audio = mx.concatenate(chunks) if len(chunks) > 1 else chunks[0]
        audio_write(str(output_path), np.array(audio), model.sample_rate, format="wav")
        outputs.append(str(output_path))
    json.dump(outputs, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
