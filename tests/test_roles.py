from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from castdub.jobs import (
    JobStateError,
    advance_episode_job,
    create_episode_job,
    episode_work_dir,
)
from castdub.roles import approve_role_mapping, create_role_mapping_template


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
                        "character_id": "lead",
                        "voice_cloning_approved": True,
                        "cross_language_approved": True,
                        "permitted_target_languages": ["en-US"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def dialogue_row() -> dict[str, object]:
    return {
        "segment_id": "segment-1",
        "target_start_ms": 1000,
        "target_duration_ms": 1200,
        "reference_path": "/private/synthetic.wav",
        "reference_text_zh": "你好",
        "translation_en_draft": "Hello",
        "character_id": None,
    }


class RoleApprovalTests(unittest.TestCase):
    def test_approved_mapping_creates_translation_worklist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
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
            advance_episode_job(store, job["job_id"], "inputs_verified")
            advance_episode_job(store, job["job_id"], "draft_imported")
            advance_episode_job(store, job["job_id"], "awaiting_role_approval")
            work_dir = episode_work_dir(store, job)
            dialogue_plan = work_dir / "import" / "dialogue-plan.jsonl"
            dialogue_plan.parent.mkdir(parents=True)
            dialogue_plan.write_text(
                json.dumps(dialogue_row(), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            mapping_path = work_dir / "role-mapping.json"
            template = create_role_mapping_template(
                dialogue_plan, rights, job["job_id"], mapping_path
            )
            template["approved"] = True
            template["assignments"][0]["approved_character_id"] = "lead"
            mapping_path.write_text(json.dumps(template), encoding="utf-8")

            result = approve_role_mapping(store, job["job_id"], mapping_path)

            self.assertEqual(result["status"], "awaiting_translation_approval")
            row = json.loads(
                Path(result["translation_worklist"])
                .read_text(encoding="utf-8")
                .splitlines()[0]
            )
            self.assertEqual(row["character_id"], "lead")
            self.assertEqual(row["draft_target_text"], "Hello")
            self.assertIsNone(row["approved_target_text"])

    def test_rejects_unauthorized_character(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
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
            advance_episode_job(store, job["job_id"], "inputs_verified")
            advance_episode_job(store, job["job_id"], "draft_imported")
            advance_episode_job(store, job["job_id"], "awaiting_role_approval")
            work_dir = episode_work_dir(store, job)
            dialogue_plan = work_dir / "import" / "dialogue-plan.jsonl"
            dialogue_plan.parent.mkdir(parents=True)
            dialogue_plan.write_text(json.dumps(dialogue_row()) + "\n")
            mapping_path = work_dir / "mapping.json"
            mapping_path.write_text(
                json.dumps(
                    {
                        "job_id": job["job_id"],
                        "approved": True,
                        "assignments": [
                            {
                                "segment_id": "segment-1",
                                "approved_character_id": "other-role",
                            }
                        ],
                    }
                )
            )

            with self.assertRaisesRegex(JobStateError, "unauthorized character"):
                approve_role_mapping(store, job["job_id"], mapping_path)


if __name__ == "__main__":
    unittest.main()
