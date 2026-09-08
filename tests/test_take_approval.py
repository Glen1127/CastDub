from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from castdub.jobs import advance_episode_job, create_episode_job, episode_work_dir
from castdub.take_approval import approve_synthesized_takes


def _create_job(root: Path) -> tuple[Path, dict[str, object], Path]:
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
        "synthesis_completed",
    ):
        advance_episode_job(store, job["job_id"], status)
    work_dir = episode_work_dir(store, job)
    fitted = work_dir / "synthesis" / "fitted" / "line-1.wav"
    fitted.parent.mkdir(parents=True)
    fitted.touch()
    takes = work_dir / "synthesis" / "takes.v1.jsonl"
    takes.write_text(
        json.dumps(
            {
                "utterance_id": "line-1",
                "character_id": "lead",
                "target_text": "Hello.",
                "fitted_path": str(fitted),
                "status": "generated",
            }
        )
        + "\n"
    )
    approval = work_dir / "approvals" / "takes.candidate.json"
    approval.parent.mkdir(parents=True)
    approval.write_text(
        json.dumps(
            {
                "job_id": job["job_id"],
                "approved": True,
                "takes": [
                    {
                        "utterance_id": "line-1",
                        "character_id": "lead",
                        "target_text": "Hello.",
                        "fitted_path": str(fitted),
                        "decision": "approved",
                        "review_notes": "",
                    }
                ],
            }
        )
    )
    return store, job, approval


class TakeApprovalTests(unittest.TestCase):
    def test_approves_complete_unchanged_take_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job, approval = _create_job(Path(directory))
            result = approve_synthesized_takes(store, job["job_id"], approval)
            self.assertEqual(result["status"], "voice_approved")
            self.assertTrue(Path(result["approved_takes"]).is_file())
            self.assertTrue(
                approve_synthesized_takes(store, job["job_id"], approval)["cache_hit"]
            )

    def test_rejects_changed_spoken_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job, approval = _create_job(Path(directory))
            payload = json.loads(approval.read_text())
            payload["takes"][0]["target_text"] = "Different words."
            approval.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "locked field target_text"):
                approve_synthesized_takes(store, job["job_id"], approval)


if __name__ == "__main__":
    unittest.main()
