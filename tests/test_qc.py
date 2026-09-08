from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from castdub.delivery import render_delivery
from castdub.qc import complete_episode, run_delivery_qc
from tests.test_delivery import _create_job


class QualityControlTests(unittest.TestCase):
    def test_passes_editor_delivery_and_completes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job = _create_job(Path(directory), "editor")
            render_delivery(store, job["job_id"])
            result = run_delivery_qc(store, job["job_id"])
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "qc_passed")
            completed = complete_episode(store, job["job_id"])
            self.assertEqual(completed["status"], "completed")
            self.assertTrue(complete_episode(store, job["job_id"])["cache_hit"])

    def test_rejects_subtitle_text_that_differs_from_spoken_take(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job = _create_job(Path(directory), "editor")
            delivered = render_delivery(store, job["job_id"])
            subtitle = Path(delivered["target_srt"])
            subtitle.write_text(subtitle.read_text().replace("Actual spoken words.", "Other text."))
            result = run_delivery_qc(store, job["job_id"])
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "render_completed")
            self.assertIn("approved spoken text", result["failures"][0])


if __name__ == "__main__":
    unittest.main()
