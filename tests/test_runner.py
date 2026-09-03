from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from castdub.jobs import advance_episode_job, create_episode_job, get_episode_job
from castdub.runner import import_registered_draft


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


class DraftImportRunnerTests(unittest.TestCase):
    @patch("castdub.runner.import_draft")
    def test_imports_verified_job_and_stops_for_role_approval(self, importer) -> None:
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
                store,
                "synthetic-series",
                "EP01",
                "en-US",
                rights,
                draft,
                video,
            )
            advance_episode_job(store, job["job_id"], "inputs_verified")

            def fake_import(**kwargs):
                output_dir = kwargs["output_dir"]
                output_dir.mkdir(parents=True)
                report = {"spoken_dialogue_segment_count": 3}
                (output_dir / "import-report.json").write_text(
                    json.dumps(report), encoding="utf-8"
                )
                (output_dir / "timeline.jsonl").touch()
                (output_dir / "dialogue-plan.jsonl").touch()
                return report

            importer.side_effect = fake_import
            result = import_registered_draft(store, job["job_id"])

            self.assertEqual(result["status"], "awaiting_role_approval")
            self.assertEqual(
                get_episode_job(store, job["job_id"])["status"],
                "awaiting_role_approval",
            )

            resumed = import_registered_draft(store, job["job_id"])
            self.assertTrue(resumed["cache_hit"])
            self.assertEqual(importer.call_count, 1)


if __name__ == "__main__":
    unittest.main()
