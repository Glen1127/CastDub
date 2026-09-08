from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from castdub.jobs import advance_episode_job, create_episode_job
from castdub.orchestrator import continue_episode


def _job(root: Path) -> tuple[Path, dict[str, object]]:
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
    return store, create_episode_job(
        store, "series", "EP01", "en-US", rights, draft, video
    )


class OrchestratorTests(unittest.TestCase):
    def test_stops_at_role_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job = _job(Path(directory))
            for status in (
                "inputs_verified",
                "draft_imported",
                "awaiting_role_approval",
            ):
                advance_episode_job(store, job["job_id"], status)
            result = continue_episode(store, job["job_id"])
            self.assertEqual(result["next_action"], "approve-roles")
            self.assertEqual(result["actions"], [])

    def test_reports_missing_performance_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job = _job(Path(directory))
            for status in (
                "inputs_verified", "draft_imported", "awaiting_role_approval",
                "roles_approved", "awaiting_translation_approval", "translation_approved",
                "awaiting_voice_profile_approval", "voice_profiles_approved",
            ):
                advance_episode_job(store, job["job_id"], status)
            result = continue_episode(store, job["job_id"])
            self.assertEqual(result["next_action"], "continue-episode")
            self.assertIn("--performance-python", result["required_configuration"])

    def test_completed_job_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job = _job(Path(directory))
            for status in (
                "inputs_verified", "draft_imported", "awaiting_role_approval",
                "roles_approved", "awaiting_translation_approval", "translation_approved",
                "awaiting_voice_profile_approval", "voice_profiles_approved",
                "performance_analysed", "synthesis_completed", "voice_approved",
                "mix_completed", "render_completed", "qc_passed", "completed",
            ):
                advance_episode_job(store, job["job_id"], status)
            result = continue_episode(store, job["job_id"])
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "completed")
            self.assertIsNone(result["next_action"])


if __name__ == "__main__":
    unittest.main()
