import json
import tempfile
import unittest
from pathlib import Path

from castdub.production import (
    build_subtitle_cues,
    build_usage_report,
    sync_voice_library,
)


class ProductionTests(unittest.TestCase):
    def test_long_final_utterance_becomes_readable_exact_text_cues(self):
        utterance = {
            "id": "u1",
            "role": "lead",
            "start_ms": 1000,
            "target_duration_ms": 5000,
            "speech_duration_ms": 4500,
            "applied_tempo_ratio": 1.0,
            "target_text": "This is a rather long first sentence. This is the second sentence.",
        }
        cues = build_subtitle_cues([utterance])
        self.assertGreater(len(cues), 1)
        self.assertEqual(
            " ".join(cue["text"] for cue in cues), utterance["target_text"]
        )
        self.assertEqual(cues[0]["start_ms"], 1000)
        self.assertEqual(cues[-1]["end_ms"], 5500)

    def test_library_keeps_selected_voice_and_adds_episode_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.wav"
            second = root / "second.wav"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            base_profile = {
                "display_name": "Lead",
                "reference_path": str(first),
                "source_path": "/source/odd-name.wav",
                "source_start_ms": 0,
                "source_duration_ms": 1000,
                "reference_transcript": "hello",
            }
            config = {"series_id": "show", "episode_id": "EP01"}
            sync_voice_library(root, config, {"lead": base_profile})
            selected = root / "asset-library/series/show/characters/lead/selected.wav"
            self.assertEqual(selected.read_bytes(), b"first")

            config["episode_id"] = "EP02"
            next_profile = {**base_profile, "reference_path": str(second)}
            sync_voice_library(root, config, {"lead": next_profile})
            self.assertEqual(selected.read_bytes(), b"first")
            profile = json.loads(selected.with_name("profile.json").read_text())
            self.assertEqual(profile["episodes_seen"], ["EP01", "EP02"])
            self.assertEqual(profile["candidates"]["EP02"]["status"], "candidate")

    def test_usage_report_separates_local_tts_and_unknown_codex_tokens(self):
        report = build_usage_report(
            {"series_id": "show", "episode_id": "EP01", "target_language": "en-US"},
            [
                {
                    "zh": "你好",
                    "en": "Hello there",
                    "raw_duration_ms": 1000,
                    "tts_cache_hit": True,
                }
            ],
            {"tts_and_timing_fit": 2.5},
        )
        self.assertEqual(report["tts"]["billed_api_tokens"], 0)
        self.assertEqual(report["tts"]["cache_hits_this_run"], 1)
        self.assertIsNone(report["orchestration"]["codex_tokens"])


if __name__ == "__main__":
    unittest.main()
