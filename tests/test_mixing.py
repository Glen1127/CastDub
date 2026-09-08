from __future__ import annotations

import json
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from castdub.jobs import advance_episode_job, create_episode_job, episode_work_dir
from castdub.mixing import prepare_mix_approval, render_episode_mix


def _tone(path: Path, duration_ms: int, frequency: float) -> None:
    sample_rate = 24000
    frames = round(sample_rate * duration_ms / 1000)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(
            b"".join(
                struct.pack("<h", round(4000 * math.sin(2 * math.pi * frequency * i / sample_rate)))
                for i in range(frames)
            )
        )


def _create_job(root: Path) -> tuple[Path, dict[str, object], Path]:
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
        "synthesis_completed",
        "voice_approved",
    ):
        advance_episode_job(store, job["job_id"], status)
    work_dir = episode_work_dir(store, job)
    dialogue = root / "line.wav"
    background = root / "background.wav"
    _tone(dialogue, 1000, 440)
    _tone(background, 3000, 220)
    takes = work_dir / "synthesis" / "takes.approved.v1.jsonl"
    takes.parent.mkdir(parents=True)
    takes.write_text(
        json.dumps(
            {
                "utterance_id": "line-1",
                "character_id": "lead",
                "start_ms": 500,
                "end_ms": 1500,
                "fitted_path": str(dialogue),
            }
        )
        + "\n"
    )
    import_dir = work_dir / "import"
    import_dir.mkdir(parents=True)
    (import_dir / "import-report.json").write_text(
        json.dumps({"draft_duration_ms": 3000, "dialogue_track_indexes": [1]})
    )
    (import_dir / "audio-segments.jsonl").write_text(
        json.dumps(
            {
                "segment_id": "background-1",
                "track_index": 2,
                "source_path": str(background),
                "source_start_ms": 0,
                "source_duration_ms": 3000,
                "target_start_ms": 0,
                "target_duration_ms": 3000,
                "speed": 1.0,
                "volume": 0.4,
                "material_name": "music.wav",
                "material_type": "music",
            }
        )
        + "\n"
    )
    return store, job, background


class MixingTests(unittest.TestCase):
    def test_requires_background_approval_and_renders_masters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job, background = _create_job(Path(directory))
            prepared = prepare_mix_approval(store, job["job_id"])
            approval = json.loads(Path(prepared["approval_template"]).read_text())
            approval["approved"] = True
            approval["draft_candidates"][0].update(
                {
                    "include": True,
                    "background_kind": "music",
                    "confirmed_no_source_dialogue": True,
                }
            )
            approval_path = Path(prepared["approval_template"]).with_name(
                "background.approved.json"
            )
            approval_path.write_text(json.dumps(approval))

            result = render_episode_mix(store, job["job_id"], approval_path)

            self.assertEqual(result["status"], "mix_completed")
            self.assertEqual(result["background_segment_count"], 1)
            self.assertTrue(Path(result["dialogue_only"]).is_file())
            self.assertTrue(Path(result["full_mix"]).is_file())
            self.assertTrue(render_episode_mix(store, job["job_id"], approval_path)["cache_hit"])

    def test_rejects_unconfirmed_background_segment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store, job, background = _create_job(Path(directory))
            prepared = prepare_mix_approval(store, job["job_id"])
            approval = json.loads(Path(prepared["approval_template"]).read_text())
            approval["approved"] = True
            approval["draft_candidates"][0].update(
                {"include": True, "background_kind": "music"}
            )
            approval_path = Path(prepared["approval_template"]).with_name(
                "background.approved.json"
            )
            approval_path.write_text(json.dumps(approval))
            with self.assertRaisesRegex(ValueError, "may contain source dialogue"):
                render_episode_mix(store, job["job_id"], approval_path)


if __name__ == "__main__":
    unittest.main()
