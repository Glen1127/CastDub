from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from castdub.demo import render_synthetic_demo


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
class SyntheticDemoTests(unittest.TestCase):
    def test_renders_complete_synthetic_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outputs = render_synthetic_demo(Path(directory))

            self.assertTrue(outputs["demo_ok"])
            self.assertTrue(outputs["synthetic_only"])
            for key in ("dialogue", "mix", "target_srt", "bilingual_srt", "timeline", "video", "qc"):
                self.assertTrue(Path(outputs[key]).is_file(), key)
            report = json.loads(Path(outputs["qc"]).read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["subtitle_margin_v"], 18)
