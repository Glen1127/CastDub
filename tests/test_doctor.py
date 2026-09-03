from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from castdub.doctor import inspect_environment


class DoctorTests(unittest.TestCase):
    @patch("castdub.doctor._ffmpeg_filters", return_value="rubberband subtitles")
    @patch("castdub.doctor.shutil.which")
    def test_reports_core_and_never_downloads(self, which, _filters) -> None:
        which.side_effect = lambda name: f"/usr/local/bin/{name}"

        report = inspect_environment()

        self.assertTrue(report["core_ready"])
        self.assertTrue(report["core"]["rubberband_filter"])
        self.assertTrue(report["core"]["subtitle_filter"])
        self.assertFalse(report["downloads_performed"])

    @patch("castdub.doctor._ffmpeg_filters", return_value="")
    @patch("castdub.doctor.shutil.which", return_value=None)
    def test_missing_media_tools_fail_only_the_core_gate(self, _which, _filters) -> None:
        report = inspect_environment(model_path=Path("/missing/model"))

        self.assertFalse(report["core_ready"])
        self.assertFalse(report["model"]["available"])


if __name__ == "__main__":
    unittest.main()
