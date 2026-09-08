from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from castdub.jobs import advance_episode_job, create_episode_job, episode_work_dir
from castdub.performance import analyse_episode_performance


class FakeProvider:
    name = "fake-performance"
    model_revision = "test-revision"

    def analyse_many(self, references: list[Path]) -> list[dict[str, object]]:
        return [
            {
                "emotion": "sad",
                "emotion_intensity": 0.7,
                "vocal_events": ["crying"],
                "raw": "<|SAD|><|Cry|>",
            }
            for _ in references
        ]


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
    ):
        advance_episode_job(store, job["job_id"], status)
    work_dir = episode_work_dir(store, job)
    approved = work_dir / "translations" / "approved.v1.jsonl"
    approved.parent.mkdir(parents=True)
    approved.write_text(
        json.dumps(
            {
                "utterance_id": "line-1",
                "character_id": "lead",
                "start_ms": 1000,
                "end_ms": 2200,
                "target_duration_ms": 1200,
                "source_text": "你好",
                "approved_target_text": "Hello.",
                "emotion": None,
                "emotion_intensity": None,
                "speaking_rate": None,
                "pause_boundaries_ms": [],
                "breath_boundaries_ms": [],
                "performance_reference_path": str(root / "source.wav"),
                "performance_reference_start_ms": 500,
                "performance_reference_duration_ms": 1200,
                "status": "approved",
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    return store, job


class PerformanceAnalysisTests(unittest.TestCase):
    @patch("castdub.performance.subprocess.run")
    def test_writes_traceable_results_and_resumes(self, run: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store, job = _create_job(root)
            (root / "source.wav").touch()
            run.return_value = subprocess.CompletedProcess([], 0)

            result = analyse_episode_performance(store, job["job_id"], FakeProvider())

            self.assertEqual(result["status"], "performance_analysed")
            rows = [
                json.loads(line)
                for line in Path(result["performance_timeline"])
                .read_text()
                .splitlines()
            ]
            self.assertEqual(rows[0]["emotion"], "sad")
            self.assertEqual(rows[0]["vocal_events"], ["crying"])
            ffmpeg_args = run.call_args.args[0]
            self.assertIn("0.500", ffmpeg_args)
            self.assertIn("1.200", ffmpeg_args)

            resumed = analyse_episode_performance(store, job["job_id"], FakeProvider())
            self.assertTrue(resumed["cache_hit"])

    def test_missing_reference_does_not_advance_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store, job = _create_job(root)

            with self.assertRaisesRegex(ValueError, "reference is missing"):
                analyse_episode_performance(store, job["job_id"], FakeProvider())


if __name__ == "__main__":
    unittest.main()
