from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from castdub.jobs import advance_episode_job, create_episode_job, episode_work_dir
from castdub.synthesis import synthesize_episode


class FakeTTS:
    name = "fake-tts"
    model_revision = "test-revision"

    def __init__(self, raw_duration_ms: int) -> None:
        self.raw_duration_ms = raw_duration_ms

    def synthesize_many(self, requests: list[dict[str, object]]) -> list[Path]:
        paths = []
        for request in requests:
            path = Path(str(request["output_path"]))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            paths.append(path)
        return paths


def _create_job(root: Path) -> tuple[Path, dict[str, object]]:
    rights = root / "rights.json"
    rights.write_text(
        json.dumps(
            {
                "source_title": "Synthetic",
                "translation_approved": True,
                "dubbing_approved": True,
                "overseas_distribution_approved": True,
                "voice_grants": [
                    {
                        "character_id": "lead",
                        "voice_cloning_approved": True,
                        "cross_language_approved": True,
                        "permitted_target_languages": ["en-US"],
                    }
                ],
            }
        )
    )
    draft = root / "draft"
    draft.mkdir()
    video = root / "clean.mp4"
    video.touch()
    store = root / "jobs.sqlite3"
    job = create_episode_job(store, "series", "EP01", "en-US", rights, draft, video)
    for status in (
        "inputs_verified",
        "draft_imported",
        "awaiting_role_approval",
        "roles_approved",
        "awaiting_translation_approval",
        "translation_approved",
        "awaiting_voice_profile_approval",
        "voice_profiles_approved",
        "performance_analysed",
    ):
        advance_episode_job(store, job["job_id"], status)
    work_dir = episode_work_dir(store, job)
    stable = root / "stable.wav"
    performance = root / "performance.wav"
    stable.touch()
    performance.touch()
    profile = work_dir / "voice-profiles" / "lead" / "profile.json"
    profile.parent.mkdir(parents=True)
    profile.write_text(
        json.dumps(
            {
                "character_id": "lead",
                "stable_reference": str(stable),
                "approved": True,
            }
        )
    )
    timeline = work_dir / "performance" / "analysed.v1.jsonl"
    timeline.parent.mkdir(parents=True)
    timeline.write_text(
        json.dumps(
            {
                "utterance_id": "line-1",
                "character_id": "lead",
                "target_duration_ms": 2000,
                "approved_target_text": "Hello.",
                "source_text": "你好",
                "performance_reference_path": str(performance),
                "emotion": "warm",
                "emotion_intensity": 0.6,
            }
        )
        + "\n"
    )
    return store, job


class SynthesisTests(unittest.TestCase):
    @patch("castdub.synthesis._fit_duration")
    @patch("castdub.synthesis._duration_ms", return_value=2100)
    def test_generates_fitted_takes_and_resumes(self, duration: object, fit: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job = _create_job(Path(directory))
            result = synthesize_episode(store, job["job_id"], FakeTTS(2100))
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "synthesis_completed")
            self.assertTrue(Path(result["approval_template"]).is_file())
            fit.assert_called_once()
            rows = [json.loads(line) for line in Path(result["takes"]).read_text().splitlines()]
            self.assertEqual(rows[0]["status"], "generated")
            self.assertAlmostEqual(rows[0]["tempo_ratio"], 1.05)
            self.assertTrue(synthesize_episode(store, job["job_id"], FakeTTS(2100))["cache_hit"])

    @patch("castdub.synthesis._duration_ms", return_value=2500)
    def test_overlong_take_requires_text_adaptation_without_advancing(self, duration: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job = _create_job(Path(directory))
            result = synthesize_episode(store, job["job_id"], FakeTTS(2500))
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "performance_analysed")
            self.assertEqual(result["needs_text_adaptation"], 1)


if __name__ == "__main__":
    unittest.main()
