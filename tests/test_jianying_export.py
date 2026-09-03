import copy
import json
import unittest

from castdub.jianying_export import (
    _replace_dialogue_audio,
    _replace_english_subtitles,
)


class JianyingExportTests(unittest.TestCase):
    def setUp(self):
        text_content = json.dumps(
            {"text": "Old", "styles": [{"range": [0, 3], "size": 5}]}
        )
        self.draft = {
            "duration": 5_000_000,
            "materials": {
                "texts": [{"id": "text-old", "type": "subtitle", "content": text_content}],
                "audios": [
                    {"id": "speech", "type": "extract_music", "name": "old.wav", "path": "##/materials/audio/old.wav"},
                    {"id": "music", "type": "music", "name": "music.mp3", "path": "##/materials/audio/music.mp3"},
                ],
            },
            "tracks": [
                {
                    "id": "text-track",
                    "type": "text",
                    "segments": [
                        {
                            "id": "old-segment",
                            "material_id": "text-old",
                            "target_timerange": {"start": 0, "duration": 1_000_000},
                            "render_index": 10,
                        }
                    ],
                },
                {
                    "id": "audio-track",
                    "type": "audio",
                    "segments": [
                        {
                            "id": "speech-segment",
                            "material_id": "speech",
                            "target_timerange": {"start": 0, "duration": 2_000_000},
                            "source_timerange": {"start": 0, "duration": 2_000_000},
                        },
                        {
                            "id": "music-segment",
                            "material_id": "music",
                            "target_timerange": {"start": 0, "duration": 5_000_000},
                            "source_timerange": {"start": 0, "duration": 5_000_000},
                        },
                    ],
                },
            ],
        }
        self.utterances = [
            {
                "id": "u1",
                "role": "lead",
                "start_ms": 0,
                "end_ms": 2000,
                "target_duration_ms": 2000,
                "speech_duration_ms": 1800,
                "applied_tempo_ratio": 1.0,
                "en": "New exact subtitle.",
            }
        ]

    def test_replaces_english_text_with_final_speech_cues(self):
        track_index, count = _replace_english_subtitles(self.draft, self.utterances)
        self.assertEqual(track_index, 0)
        self.assertEqual(count, 1)
        material_id = self.draft["tracks"][0]["segments"][0]["material_id"]
        material = next(
            item for item in self.draft["materials"]["texts"] if item["id"] == material_id
        )
        self.assertEqual(json.loads(material["content"])["text"], "New exact subtitle.")

    def test_replaces_speech_but_preserves_music(self):
        track_index, removed, preserved = _replace_dialogue_audio(
            self.draft, self.utterances, "dialogue.wav"
        )
        self.assertEqual(track_index, 1)
        self.assertEqual(removed, 1)
        self.assertEqual(preserved, 1)
        segments = self.draft["tracks"][1]["segments"]
        self.assertEqual(len(segments), 2)
        material_types = {
            material["id"]: material["type"]
            for material in self.draft["materials"]["audios"]
        }
        self.assertIn("music", {material_types[item["material_id"]] for item in segments})


if __name__ == "__main__":
    unittest.main()
