from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


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

IDENTITY_MINIMUM_AUDIO_MS = 1200
IDENTITY_MINIMUM_SIMILARITY = 0.95
IDENTITY_RETRY_TEMPERATURES = (0.7, 0.55, 0.65, 0.45, 0.35)


def _voice_identity_prompt(request: dict[str, object]) -> tuple[str, str]:
    reference = str(request.get("stable_voice_reference") or "").strip()
    transcript = str(request.get("stable_reference_text") or "").strip()
    if not reference or not transcript:
        raise ValueError("Stable voice reference and its transcript are required")
    return reference, transcript


def _identity_sidecar_path(output_path: Path) -> Path:
    return output_path.with_suffix(".identity.json")


def _rank_identity_candidate(candidate: dict[str, Any]) -> tuple[float, float]:
    return (
        float(candidate["target_similarity"]),
        float(candidate.get("target_margin") or 0.0),
    )


def _select_identity_candidate(
    candidates: list[dict[str, Any]],
    *,
    minimum_similarity: float = IDENTITY_MINIMUM_SIMILARITY,
) -> dict[str, Any]:
    """Select a generated take only when its target voice is the best match."""
    passing = [
        candidate
        for candidate in candidates
        if float(candidate["target_similarity"]) >= minimum_similarity
        and (
            candidate.get("target_margin") is None
            or float(candidate["target_margin"]) > 0
        )
    ]
    if not passing:
        raise ValueError("No generated candidate passed speaker identity QC")
    return max(passing, key=_rank_identity_candidate)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    args = parser.parse_args(argv)
    requests = json.load(sys.stdin)
    if not isinstance(requests, list):
        raise ValueError("Worker input must be a JSON list")

    with contextlib.redirect_stdout(sys.stderr):
        import mlx.core as mx
        import numpy as np
        from mlx_audio.audio_io import write as audio_write
        from mlx_audio.tts.utils import load_model
        from mlx_audio.utils import load_audio

        model = load_model(str(args.model_path.resolve()))
        profile_embeddings: dict[str, object] = {}
        for request in requests:
            identity_audio, _ = _voice_identity_prompt(request)
            references = request.get("identity_profile_references") or {
                str(request["character_id"]): identity_audio
            }
            if not isinstance(references, dict):
                raise ValueError("identity_profile_references must be an object")
            for character_id, reference_path in references.items():
                character_id = str(character_id)
                if character_id in profile_embeddings:
                    continue
                reference_audio = load_audio(str(reference_path), sample_rate=24000)
                embedding = model.extract_speaker_embedding(reference_audio)
                mx.eval(embedding)
                profile_embeddings[character_id] = np.asarray(embedding).reshape(-1)

        def cosine_similarity(left: object, right: object) -> float:
            left_array = np.asarray(left).reshape(-1)
            right_array = np.asarray(right).reshape(-1)
            denominator = np.linalg.norm(left_array) * np.linalg.norm(right_array)
            if denominator == 0:
                return 0.0
            return float(np.dot(left_array, right_array) / denominator)

        outputs: list[str] = []
        for request in requests:
            identity_audio, identity_text = _voice_identity_prompt(request)
            output_path = Path(request["output_path"]).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            language = LANGUAGE_CODES.get(
                str(request["target_language"]).split("-", 1)[0].lower(), "auto"
            )
            utterance_id = str(request["utterance_id"])
            character_id = str(request["character_id"])
            candidate_dir = (
                output_path.parent / "identity-candidates" / utterance_id
            )
            candidate_dir.mkdir(parents=True, exist_ok=True)
            candidates: list[dict[str, Any]] = []
            selected: dict[str, Any] | None = None
            for attempt, temperature in enumerate(IDENTITY_RETRY_TEMPERATURES, 1):
                chunks = [
                    result.audio
                    for result in model.generate(
                        text=request["target_text"],
                        lang_code=language,
                        ref_audio=identity_audio,
                        ref_text=identity_text,
                        temperature=temperature,
                        top_p=0.9,
                        repetition_penalty=1.5,
                        verbose=False,
                    )
                ]
                if not chunks:
                    raise RuntimeError(f"No audio generated for {utterance_id}")
                audio = mx.concatenate(chunks) if len(chunks) > 1 else chunks[0]
                candidate_path = candidate_dir / f"candidate-{attempt:02d}.wav"
                audio_write(
                    str(candidate_path), np.array(audio), model.sample_rate, format="wav"
                )
                duration_ms = round(len(audio) / model.sample_rate * 1000)
                candidate: dict[str, Any] = {
                    "attempt": attempt,
                    "temperature": temperature,
                    "path": str(candidate_path),
                    "duration_ms": duration_ms,
                }
                if duration_ms < IDENTITY_MINIMUM_AUDIO_MS:
                    candidate.update(
                        {
                            "status": "not_evaluated_short",
                            "target_similarity": None,
                            "target_margin": None,
                        }
                    )
                    candidates.append(candidate)
                    selected = candidate
                    break

                generated_embedding = model.extract_speaker_embedding(audio)
                mx.eval(generated_embedding)
                similarities = {
                    profile_id: cosine_similarity(generated_embedding, embedding)
                    for profile_id, embedding in profile_embeddings.items()
                }
                target_similarity = similarities[character_id]
                competing = [
                    similarity
                    for profile_id, similarity in similarities.items()
                    if profile_id != character_id
                ]
                target_margin = (
                    target_similarity - max(competing) if competing else None
                )
                candidate.update(
                    {
                        "status": "evaluated",
                        "target_similarity": round(target_similarity, 6),
                        "target_margin": (
                            round(target_margin, 6)
                            if target_margin is not None
                            else None
                        ),
                        "similarities": {
                            key: round(value, 6)
                            for key, value in similarities.items()
                        },
                    }
                )
                candidates.append(candidate)
                try:
                    selected = _select_identity_candidate(candidates)
                except ValueError:
                    continue
                break

            sidecar = {
                "schema_version": 1,
                "utterance_id": utterance_id,
                "character_id": character_id,
                "minimum_audio_ms": IDENTITY_MINIMUM_AUDIO_MS,
                "minimum_similarity": IDENTITY_MINIMUM_SIMILARITY,
                "candidates": candidates,
                "selected": selected,
                "passed": selected is not None
                and selected["status"] in {"evaluated", "not_evaluated_short"},
                "evaluation": (
                    "not_evaluated_short"
                    if selected is not None
                    and selected["status"] == "not_evaluated_short"
                    else "passed"
                    if selected is not None
                    else "failed"
                ),
            }
            sidecar_path = _identity_sidecar_path(output_path)
            sidecar_path.write_text(
                json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            if selected is None:
                raise RuntimeError(
                    f"Speaker identity QC failed for {utterance_id}; see {sidecar_path}"
                )
            shutil.copyfile(str(selected["path"]), output_path)
            outputs.append(str(output_path))
    json.dump(outputs, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
