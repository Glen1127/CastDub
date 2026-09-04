from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from castdub.jobs import JobStateError, advance_episode_job, create_episode_job, episode_work_dir
from castdub.translations import approve_translation_worklist


def write_rights(path: Path) -> None:
    path.write_text(
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


def create_translation_job(root: Path) -> tuple[Path, dict[str, object], Path]:
    rights = root / "rights.json"
    draft = root / "draft"
    video = root / "clean.mp4"
    store = root / "jobs.sqlite3"
    draft.mkdir()
    video.touch()
    write_rights(rights)
    job = create_episode_job(
        store, "series", "EP01", "en-US", rights, draft, video
    )
    for status in (
        "inputs_verified",
        "draft_imported",
        "awaiting_role_approval",
        "roles_approved",
        "awaiting_translation_approval",
    ):
        advance_episode_job(store, job["job_id"], status)
    worklist = episode_work_dir(store, job) / "translations" / "worklist.jsonl"
    worklist.parent.mkdir(parents=True)
    row = {
        "utterance_id": "segment-1",
        "character_id": "lead",
        "start_ms": 1000,
        "end_ms": 2200,
        "target_duration_ms": 1200,
        "source_text": "你好",
        "draft_target_text": "Hello",
        "approved_target_text": None,
        "emotion": None,
        "emotion_intensity": None,
        "speaking_rate": None,
        "pause_boundaries_ms": [],
        "breath_boundaries_ms": [],
        "performance_reference_path": "/private/synthetic.wav",
        "status": "pending",
    }
    worklist.write_text(json.dumps(row, ensure_ascii=False) + "\n")
    return store, job, worklist


class TranslationApprovalTests(unittest.TestCase):
    def test_approves_complete_worklist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job, worklist = create_translation_job(Path(directory))
            row = json.loads(worklist.read_text().strip())
            row.update(
                {
                    "approved_target_text": "Hello.",
                    "emotion": "warm",
                    "emotion_intensity": 0.6,
                    "status": "approved",
                }
            )
            candidate = worklist.with_name("candidate.jsonl")
            candidate.write_text(json.dumps(row, ensure_ascii=False) + "\n")

            result = approve_translation_worklist(store, job["job_id"], candidate)

            self.assertEqual(result["status"], "translation_approved")
            self.assertTrue(Path(result["approved_worklist"]).is_file())

    def test_rejects_changed_character(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job, worklist = create_translation_job(Path(directory))
            row = json.loads(worklist.read_text().strip())
            row.update(
                {
                    "character_id": "other",
                    "approved_target_text": "Hello.",
                    "status": "approved",
                }
            )
            candidate = worklist.with_name("candidate.jsonl")
            candidate.write_text(json.dumps(row, ensure_ascii=False) + "\n")

            with self.assertRaisesRegex(JobStateError, "locked field character_id"):
                approve_translation_worklist(store, job["job_id"], candidate)


if __name__ == "__main__":
    unittest.main()
