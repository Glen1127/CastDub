from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from castdub.jobs import JobStateError, advance_episode_job, create_episode_job


def write_rights(path: Path, approved: bool = True) -> None:
    path.write_text(
        json.dumps(
            {
                "source_title": "Synthetic test series",
                "translation_approved": approved,
                "dubbing_approved": approved,
                "overseas_distribution_approved": approved,
                "voice_grants": [
                    {
                        "character_id": "character-a",
                        "voice_cloning_approved": approved,
                        "cross_language_approved": approved,
                        "permitted_target_languages": ["en-US"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


class EpisodeJobTests(unittest.TestCase):
    def test_creates_rights_gated_resumable_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rights = root / "rights.json"
            draft = root / "draft"
            video = root / "clean.mp4"
            draft.mkdir()
            video.touch()
            write_rights(rights)

            job = create_episode_job(
                root / "jobs.sqlite3",
                "test-series",
                "EP01",
                "en-US",
                rights,
                draft,
                video,
            )

            self.assertEqual(job["status"], "ready_for_preflight")
            self.assertEqual(len(job["rights_sha256"]), 64)

    def test_rejects_stage_skipping_and_allows_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rights = root / "rights.json"
            draft = root / "draft"
            video = root / "clean.mp4"
            draft.mkdir()
            video.touch()
            write_rights(rights)
            store = root / "jobs.sqlite3"
            job = create_episode_job(
                store, "test-series", "EP01", "en-US", rights, draft, video
            )

            with self.assertRaisesRegex(JobStateError, "expected inputs_verified"):
                advance_episode_job(store, job["job_id"], "draft_imported")

            advanced = advance_episode_job(
                store, job["job_id"], "inputs_verified", {"preflight": "pass"}
            )
            resumed = advance_episode_job(store, job["job_id"], "inputs_verified")
            self.assertEqual(advanced["status"], "inputs_verified")
            self.assertEqual(resumed["status"], "inputs_verified")


if __name__ == "__main__":
    unittest.main()
