from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import wave
from array import array
from pathlib import Path
from unittest.mock import patch

from castdub.jobs import advance_episode_job, create_episode_job, episode_work_dir
from castdub.synthesis import (
    QwenMlxSubprocessProvider,
    _fit_duration,
    synthesize_episode,
)
from castdub.synthesis_worker import (
    _identity_sidecar_path,
    _select_identity_candidate,
    _voice_identity_prompt,
)


class FakeTTS:
    name = "fake-tts"
    model_revision = "test-revision"

    def __init__(self, raw_duration_ms: int) -> None:
        self.raw_duration_ms = raw_duration_ms
        self.calls: list[list[dict[str, object]]] = []

    def synthesize_many(self, requests: list[dict[str, object]]) -> list[Path]:
        self.calls.append(requests)
        paths = []
        for request in requests:
            path = Path(str(request["output_path"]))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            paths.append(path)
        return paths


def _create_job(root: Path) -> tuple[Path, dict[str, object]]:
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
    ):
        advance_episode_job(store, job["job_id"], status)
    work_dir = episode_work_dir(store, job)
    stable = root / "stable.wav"
    performance = root / "performance.wav"
    stable.touch()
    performance.touch()
    profile = work_dir / "voice-profiles" / "lead" / "profile.json"
    profile.parent.mkdir(parents=True)
    profile.write_text(
        json.dumps(
            {
                "character_id": "lead",
                "stable_reference": str(stable),
                "stable_reference_text": "我是固定角色声音",
                "approved": True,
            }
        )
    )
    timeline = work_dir / "performance" / "analysed.v1.jsonl"
    timeline.parent.mkdir(parents=True)
    timeline.write_text(
        json.dumps(
            {
                "utterance_id": "line-1",
                "character_id": "lead",
                "start_ms": 1000,
                "end_ms": 3000,
                "target_duration_ms": 2000,
                "approved_target_text": "Hello.",
                "source_text": "你好",
                "performance_reference_path": str(performance),
                "emotion": "warm",
                "emotion_intensity": 0.6,
            }
        )
        + "\n"
    )
    return store, job


class SynthesisTests(unittest.TestCase):
    def test_duration_fit_caps_generated_leading_silence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wav"
            output = root / "fitted.wav"
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-t", "0.6", "-i",
                    "anullsrc=r=24000:cl=mono",
                    "-f", "lavfi", "-t", "0.6", "-i",
                    "sine=frequency=440:sample_rate=24000",
                    "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]",
                    "-map", "[a]", str(source),
                ],
                check=True,
            )

            _fit_duration(source, output, 1200, 1.0)

            with wave.open(str(output), "rb") as fitted:
                samples = array("h", fitted.readframes(fitted.getnframes()))
                onset = next(
                    index for index, value in enumerate(samples) if abs(value) > 100
                )
                onset_seconds = onset / fitted.getframerate()
            self.assertLessEqual(onset_seconds, 0.16)
            self.assertGreaterEqual(onset_seconds, 0.06)

    def test_preserves_virtual_environment_python_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            worker_python = root / "venv-python"
            worker_python.symlink_to(sys.executable)
            model = root / "model"
            model.mkdir()
            provider = QwenMlxSubprocessProvider(
                worker_python, model, "test-revision"
            )
            self.assertEqual(provider.worker_python, worker_python.absolute())

    @patch("castdub.synthesis._fit_duration")
    @patch("castdub.synthesis._duration_ms", return_value=2100)
    def test_generates_fitted_takes_and_resumes(self, duration: object, fit: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job = _create_job(Path(directory))
            result = synthesize_episode(store, job["job_id"], FakeTTS(2100))
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "synthesis_completed")
            self.assertTrue(Path(result["approval_template"]).is_file())
            fit.assert_called_once()
            rows = [json.loads(line) for line in Path(result["takes"]).read_text().splitlines()]
            self.assertEqual(rows[0]["status"], "generated")
            self.assertAlmostEqual(rows[0]["tempo_ratio"], 1.05)
            request = rows[0]
            self.assertEqual(request["stable_reference_text"], "我是固定角色声音")
            self.assertEqual(
                request["identity_profile_references"],
                {"lead": request["stable_voice_reference"]},
            )
            self.assertTrue(synthesize_episode(store, job["job_id"], FakeTTS(2100))["cache_hit"])

    def test_worker_uses_stable_identity_reference_not_line_performance(self) -> None:
        request = {
            "stable_voice_reference": "/voices/lead.wav",
            "stable_reference_text": "我是固定角色声音",
            "performance_reference": "/performances/angry-line.wav",
            "reference_text": "当句台词",
        }

        self.assertEqual(
            _voice_identity_prompt(request),
            ("/voices/lead.wav", "我是固定角色声音"),
        )

    def test_worker_rejects_missing_stable_identity_transcript(self) -> None:
        with self.assertRaisesRegex(ValueError, "transcript"):
            _voice_identity_prompt(
                {
                    "stable_voice_reference": "/voices/lead.wav",
                    "stable_reference_text": None,
                }
            )

    def test_identity_qc_rejects_candidate_closer_to_another_character(self) -> None:
        with self.assertRaisesRegex(ValueError, "identity QC"):
            _select_identity_candidate(
                [
                    {
                        "target_similarity": 0.97,
                        "target_margin": -0.01,
                    }
                ]
            )

    def test_identity_qc_selects_best_passing_candidate(self) -> None:
        selected = _select_identity_candidate(
            [
                {"attempt": 1, "target_similarity": 0.94, "target_margin": 0.02},
                {"attempt": 2, "target_similarity": 0.96, "target_margin": 0.01},
                {"attempt": 3, "target_similarity": 0.97, "target_margin": 0.03},
            ]
        )
        self.assertEqual(selected["attempt"], 3)

    def test_identity_sidecar_does_not_replace_audio_extension_twice(self) -> None:
        self.assertEqual(
            _identity_sidecar_path(Path("line.wav")), Path("line.identity.json")
        )

    @patch("castdub.synthesis._fit_duration")
    @patch("castdub.synthesis._duration_ms", return_value=2100)
    def test_approved_timing_correction_survives_resynthesis(
        self, duration: object, fit: object
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job = _create_job(Path(directory))
            work_dir = episode_work_dir(store, job)
            approvals = work_dir / "approvals"
            approvals.mkdir(parents=True, exist_ok=True)
            (approvals / "timing-corrections.v1.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "job_id": job["job_id"],
                        "approved": True,
                        "corrections": [
                            {
                                "utterance_id": "line-1",
                                "new_start_ms": 125,
                                "reason": "restore complete utterance boundary",
                            }
                        ],
                    }
                )
            )

            result = synthesize_episode(store, job["job_id"], FakeTTS(2100))
            row = json.loads(Path(result["takes"]).read_text().splitlines()[0])
            self.assertEqual(row["start_ms"], 125)
            self.assertEqual(row["end_ms"], 2125)
            self.assertEqual(row["timing_correction"]["new_start_ms"], 125)

    @patch("castdub.synthesis._duration_ms", return_value=2500)
    def test_overlong_take_requires_text_adaptation_without_advancing(self, duration: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job = _create_job(Path(directory))
            result = synthesize_episode(store, job["job_id"], FakeTTS(2500))
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "performance_analysed")
            self.assertEqual(result["needs_text_adaptation"], 1)

    @patch("castdub.synthesis._duration_ms", return_value=2500)
    def test_reuses_unchanged_raw_take_during_adaptation(self, duration: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job = _create_job(Path(directory))
            provider = FakeTTS(2500)
            self.assertFalse(synthesize_episode(store, job["job_id"], provider)["ok"])

            result = synthesize_episode(store, job["job_id"], provider)

            self.assertFalse(result["ok"])
            self.assertEqual(len(provider.calls), 1)
            manifest = json.loads(Path(result["manifest"]).read_text())
            self.assertEqual(manifest["reused_raw_takes"], 1)


if __name__ == "__main__":
    unittest.main()
