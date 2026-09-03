from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from castdub.jobs import create_episode_job, get_episode_job
from castdub.preflight import inspect_episode_inputs, preflight_registered_job


def write_draft(path: Path, duration_ms: int = 10_000) -> None:
    path.mkdir()
    (path / "draft_content.json").write_text(
        json.dumps(
            {
                "duration": duration_ms * 1000,
                "tracks": [
                    {"type": "video"},
                    {"type": "audio"},
                    {"type": "text"},
                ],
            }
        ),
        encoding="utf-8",
    )


def write_rights(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "source_title": "Synthetic series",
                "translation_approved": True,
                "dubbing_approved": True,
                "overseas_distribution_approved": True,
                "voice_grants": [
                    {
                        "character_id": "character-a",
                        "voice_cloning_approved": True,
                        "cross_language_approved": True,
                        "permitted_target_languages": ["en-US"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


class InputInspectionTests(unittest.TestCase):
    def test_editor_mode_passes_without_clean_master(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            draft = Path(directory) / "draft"
            write_draft(draft)

            report = inspect_episode_inputs(draft, "editor")

            self.assertTrue(report["ok"])
            self.assertIsNone(report["video_duration_ms"])

    @patch("castdub.preflight.probe_duration_ms", return_value=10_026)
    def test_final_mode_compares_clean_master_duration(self, _probe) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft = root / "draft"
            video = root / "clean.mp4"
            write_draft(draft)
            video.touch()

            report = inspect_episode_inputs(draft, "final", video)

            self.assertTrue(report["ok"])
            self.assertEqual(report["duration_delta_ms"], 26)

    @patch("castdub.preflight.probe_duration_ms", return_value=12_000)
    def test_failed_preflight_does_not_advance_job(self, _probe) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            draft = root / "draft"
            video = root / "clean.mp4"
            rights = root / "rights.json"
            store = root / "jobs.sqlite3"
            write_draft(draft)
            write_rights(rights)
            video.touch()
            job = create_episode_job(
                store,
                "synthetic-series",
                "EP01",
                "en-US",
                rights,
                draft,
                video,
            )

            report = preflight_registered_job(store, job["job_id"])

            self.assertFalse(report["ok"])
            self.assertEqual(
                get_episode_job(store, job["job_id"])["status"],
                "ready_for_preflight",
            )


if __name__ == "__main__":
    unittest.main()
