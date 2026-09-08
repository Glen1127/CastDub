from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import ANY, patch

from castdub.cli import main


class CliTests(unittest.TestCase):
    @patch("castdub.cli.analyse_episode_performance")
    @patch("castdub.cli.SenseVoiceSubprocessProvider")
    def test_analyse_performance_executes_provider(self, provider, analyse) -> None:
        provider.return_value = object()
        analyse.return_value = {"ok": True, "status": "performance_analysed"}
        output = io.StringIO()

        with redirect_stdout(output):
            main(
                [
                    "analyse-performance",
                    "--store",
                    "jobs.sqlite3",
                    "--job-id",
                    "series:EP02:en-US",
                    "--worker-python",
                    "worker-python",
                    "--model-path",
                    "model",
                    "--model-revision",
                    "revision",
                ]
            )

        analyse.assert_called_once_with(
            ANY, "series:EP02:en-US", provider.return_value
        )
        self.assertEqual(json.loads(output.getvalue())["status"], "performance_analysed")


if __name__ == "__main__":
    unittest.main()
