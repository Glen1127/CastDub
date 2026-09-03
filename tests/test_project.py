from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from castdub.project import JOB_DIRECTORIES, RightsError, RightsManifest, create_project


def authorised_rights() -> RightsManifest:
    return RightsManifest.from_mapping(
        {
            "source_title": "Pilot",
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


class RightsManifestTests(unittest.TestCase):
    def test_rejects_missing_project_rights(self) -> None:
        rights = RightsManifest.from_mapping(
            {
                "source_title": "Pilot",
                "translation_approved": True,
                "dubbing_approved": False,
                "overseas_distribution_approved": True,
                "voice_grants": [],
            }
        )
        with self.assertRaisesRegex(RightsError, "dubbing"):
            rights.assert_authorized("en-US")

    def test_rejects_unapproved_target_language(self) -> None:
        with self.assertRaisesRegex(RightsError, "en-GB"):
            authorised_rights().assert_authorized("en-GB")


class ProjectCreationTests(unittest.TestCase):
    def test_creates_private_job_structure_after_rights_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = create_project(
                workspace=Path(directory),
                slug="pilot-001",
                target_language="en-US",
                rights=authorised_rights(),
            )
            self.assertTrue((project / "project.json").is_file())
            for expected in JOB_DIRECTORIES:
                self.assertTrue((project / expected).is_dir())

    def test_does_not_overwrite_existing_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            create_project(workspace, "pilot-001", "en-US", authorised_rights())
            with self.assertRaises(FileExistsError):
                create_project(workspace, "pilot-001", "en-US", authorised_rights())


if __name__ == "__main__":
    unittest.main()
