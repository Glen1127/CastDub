from __future__ import annotations

import json
import math
import struct
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from castdub.delivery import _ass_time, render_delivery
from castdub.jobs import advance_episode_job, create_episode_job, episode_work_dir


def _tone(path: Path, duration_ms: int) -> None:
    sample_rate = 48000
    frames = round(sample_rate * duration_ms / 1000)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        mono = [
            round(2000 * math.sin(2 * math.pi * 220 * i / sample_rate))
            for i in range(frames)
        ]
        output.writeframes(b"".join(struct.pack("<hh", value, value) for value in mono))


def _create_job(root: Path, output_mode: str) -> tuple[Path, dict[str, object]]:
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
    video = None
    if output_mode == "final":
        video = root / "clean.mp4"
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=320x240:d=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video),
            ],
            check=True,
        )
    store = root / "jobs.sqlite3"
    job = create_episode_job(
        store, "series", "EP01", "en-US", rights, draft, video,
        output_mode=output_mode,
    )
    for status in (
        "inputs_verified", "draft_imported", "awaiting_role_approval",
        "roles_approved", "awaiting_translation_approval", "translation_approved",
        "awaiting_voice_profile_approval", "voice_profiles_approved",
        "performance_analysed", "synthesis_completed", "voice_approved", "mix_completed",
    ):
        advance_episode_job(store, job["job_id"], status)
    work_dir = episode_work_dir(store, job)
    takes = work_dir / "synthesis" / "takes.approved.v1.jsonl"
    takes.parent.mkdir(parents=True)
    takes.write_text(
        json.dumps(
            {
                "utterance_id": "line-1", "character_id": "lead",
                "start_ms": 250, "target_duration_ms": 1000,
                "fitted_duration_ms": 1000, "target_text": "Actual spoken words.",
                "reference_text": "实际台词", "fitted_path": str(root / "line.wav"),
            }, ensure_ascii=False,
        ) + "\n"
    )
    mix_dir = work_dir / "mix"
    mix_dir.mkdir(parents=True)
    dialogue = mix_dir / "EP01.en-US.dialogue-only.wav"
    full_mix = mix_dir / "EP01.en-US.full-mix.wav"
    _tone(dialogue, 2000)
    _tone(full_mix, 2000)
    (mix_dir / "manifest.json").write_text(
        json.dumps(
            {
                "duration_ms": 2000,
                "dialogue_only": str(dialogue),
                "full_mix": str(full_mix),
            }
        )
    )
    return store, job


class DeliveryTests(unittest.TestCase):
    def test_ass_time_uses_seconds_and_centiseconds(self) -> None:
        self.assertEqual(_ass_time(41_233), "0:00:41.23")

    def test_editor_package_uses_approved_spoken_text_and_bottom_style(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job = _create_job(Path(directory), "editor")
            result = render_delivery(store, job["job_id"])
            self.assertEqual(result["status"], "render_completed")
            self.assertIsNone(result["final_video"])
            self.assertIn("Actual spoken words.", Path(result["target_srt"]).read_text())
            self.assertIn("实际台词", Path(result["bilingual_srt"]).read_text())
            ass = Path(result["target_ass"]).read_text()
            self.assertIn("Arial,20", ass)
            self.assertIn(",2,24,24,18,1", ass)

    def test_final_package_burns_subtitles_on_clean_master(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job = _create_job(Path(directory), "final")
            result = render_delivery(store, job["job_id"])
            self.assertTrue(Path(result["final_video"]).is_file())
            frame = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", "0.5",
                    "-i", result["final_video"], "-frames:v", "1", "-f", "rawvideo",
                    "-pix_fmt", "gray", "-",
                ],
                capture_output=True,
                check=True,
            ).stdout
            self.assertGreater(max(frame), 100)
            self.assertTrue(render_delivery(store, job["job_id"])["cache_hit"])


if __name__ == "__main__":
    unittest.main()
