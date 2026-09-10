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
from castdub.voices import approve_voice_profiles, prepare_voice_profile_approval


def write_rights(path: Path, character_ids: tuple[str, ...] = ("lead",)) -> None:
    path.write_text(
        json.dumps(
            {
                "source_title": "Synthetic",
                "translation_approved": True,
                "dubbing_approved": True,
                "overseas_distribution_approved": True,
                "voice_grants": [
                    {
                        "character_id": character_id,
                        "voice_cloning_approved": True,
                        "cross_language_approved": True,
                        "permitted_target_languages": ["en-US"],
                    }
                    for character_id in character_ids
                ],
            }
        )
    )


class VoicePreparationTests(unittest.TestCase):
    def test_allows_short_same_character_reference_with_warning(self) -> None:
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
            for status in (
                "inputs_verified",
                "draft_imported",
                "awaiting_role_approval",
                "roles_approved",
                "awaiting_translation_approval",
                "translation_approved",
            ):
                advance_episode_job(store, job["job_id"], status)
            work_dir = episode_work_dir(store, job)
            plan = work_dir / "timeline" / "dialogue-plan.roles-approved.jsonl"
            plan.parent.mkdir(parents=True)
            plan.write_text(
                json.dumps(
                    {
                        "segment_id": "short-line",
                        "character_id": "lead",
                        "target_duration_ms": 1400,
                        "reference_text_zh": "你好",
                        "reference_path": "/private/short.wav",
                        "reference_start_ms": 0,
                        "reference_duration_ms": 1800,
                    }
                )
                + "\n"
            )

            result = prepare_voice_profile_approval(
                store, job["job_id"], root / "library"
            )
            template = json.loads(Path(result["approval_template"]).read_text())
            candidate = template["characters"][0]["episode_candidates"][0]
            self.assertEqual(candidate["segment_id"], "short-line")
            self.assertEqual(candidate["quality_warning"], "short_voice_reference")

    def test_suggests_existing_profile_without_approving_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rights = root / "rights.json"
            draft = root / "draft"
            video = root / "clean.mp4"
            store = root / "jobs.sqlite3"
            library = root / "library"
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
                "translation_approved",
            ):
                advance_episode_job(store, job["job_id"], status)
            work_dir = episode_work_dir(store, job)
            plan = work_dir / "timeline" / "dialogue-plan.roles-approved.jsonl"
            plan.parent.mkdir(parents=True)
            plan.write_text(
                json.dumps(
                    {
                        "segment_id": "segment-1",
                        "character_id": "lead",
                        "target_duration_ms": 3000,
                        "reference_text_zh": "你好",
                        "reference_path": "/private/synthetic.wav",
                        "reference_start_ms": 0,
                        "reference_duration_ms": 3200,
                    }
                )
                + "\n"
            )
            profile_dir = library / "series" / "series" / "characters" / "lead"
            profile_dir.mkdir(parents=True)
            selected = profile_dir / "selected.wav"
            selected.touch()
            (profile_dir / "profile.json").write_text(
                json.dumps(
                    {
                        "character_id": "lead",
                        "selected_reference": str(selected),
                        "selected_reference_text": "你好",
                    }
                )
            )

            result = prepare_voice_profile_approval(
                store, job["job_id"], library
            )

            self.assertEqual(result["status"], "awaiting_voice_profile_approval")
            self.assertEqual(result["existing_profile_count"], 1)
            template = json.loads(Path(result["approval_template"]).read_text())
            self.assertFalse(template["approved"])
            self.assertFalse(template["characters"][0]["approved"])
            self.assertEqual(
                template["characters"][0]["selection"]["mode"],
                "reuse_existing",
            )

            template["approved"] = True
            template["characters"][0]["approved"] = True
            approval = Path(result["approval_template"]).with_name("approved.json")
            approval.write_text(json.dumps(template))
            approved = approve_voice_profiles(store, job["job_id"], approval)
            self.assertEqual(approved["status"], "voice_profiles_approved")
            self.assertTrue(Path(approved["profile_manifests"][0]).is_file())

    def test_rejects_cross_character_stable_reference_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rights = root / "rights.json"
            draft = root / "draft"
            video = root / "clean.mp4"
            store = root / "jobs.sqlite3"
            library = root / "library"
            draft.mkdir()
            video.touch()
            write_rights(rights, ("lead", "support"))
            job = create_episode_job(
                store, "series", "EP01", "en-US", rights, draft, video
            )
            for status in (
                "inputs_verified",
                "draft_imported",
                "awaiting_role_approval",
                "roles_approved",
                "awaiting_translation_approval",
                "translation_approved",
            ):
                advance_episode_job(store, job["job_id"], status)
            work_dir = episode_work_dir(store, job)
            plan = work_dir / "timeline" / "dialogue-plan.roles-approved.jsonl"
            plan.parent.mkdir(parents=True)
            plan.write_text(
                "".join(
                    json.dumps(
                        {
                            "segment_id": f"segment-{index}",
                            "character_id": character_id,
                            "target_duration_ms": 3000,
                            "reference_text_zh": "你好",
                            "reference_path": f"/private/{character_id}.wav",
                            "reference_start_ms": 0,
                            "reference_duration_ms": 3200,
                        }
                    )
                    + "\n"
                    for index, character_id in enumerate(("lead", "support"), 1)
                )
            )
            shared = root / "shared.wav"
            shared.touch()
            for character_id in ("lead", "support"):
                profile_dir = (
                    library / "series" / "series" / "characters" / character_id
                )
                profile_dir.mkdir(parents=True)
                (profile_dir / "profile.json").write_text(
                    json.dumps(
                        {
                            "character_id": character_id,
                            "selected_reference": str(shared),
                            "selected_reference_text": "你好",
                        }
                    )
                )
            prepared = prepare_voice_profile_approval(
                store, job["job_id"], library
            )
            template = json.loads(Path(prepared["approval_template"]).read_text())
            template["approved"] = True
            for item in template["characters"]:
                item["approved"] = True
            approval = Path(prepared["approval_template"]).with_name("approved.json")
            approval.write_text(json.dumps(template))

            with self.assertRaisesRegex(JobStateError, "cannot share"):
                approve_voice_profiles(store, job["job_id"], approval)


if __name__ == "__main__":
    unittest.main()
