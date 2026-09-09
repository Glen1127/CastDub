from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from castdub.jianying import import_draft, resolve_material_path


def text_material(material_id: str, text: str) -> dict[str, object]:
    return {
        "id": material_id,
        "type": "subtitle",
        "content": json.dumps({"text": text}),
    }


class JianyingImportTests(unittest.TestCase):
    def test_resolves_packaged_placeholder_path(self) -> None:
        root = Path("/tmp/draft")
        stored = "##_draftpath_placeholder_ABCD_##/materials/audio/line.wav"
        self.assertEqual(
            resolve_material_path(root, stored),
            root / "materials/audio/line.wav",
        )

    def test_imports_subtitles_and_dialogue_segments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "draft"
            output = Path(directory) / "output"
            audio = root / "materials/audio/lead.wav"
            audio.parent.mkdir(parents=True)
            audio.write_bytes(b"test")
            draft = {
                "id": "draft-1",
                "version": 1,
                "duration": 3_000_000,
                "materials": {
                    "texts": [
                        text_material("zh-1", "你好"),
                        text_material("en-1", "Hello"),
                    ],
                    "audios": [
                        {
                            "id": "audio-1",
                            "name": "lead.wav",
                            "type": "text_to_audio",
                            "path": "##_draftpath_placeholder_X_##/materials/audio/lead.wav",
                        }
                    ],
                },
                "tracks": [
                    {
                        "type": "text",
                        "segments": [
                            {
                                "id": "zh-segment",
                                "material_id": "zh-1",
                                "target_timerange": {"start": 0, "duration": 1_000_000},
                            }
                        ],
                    },
                    {
                        "type": "text",
                        "segments": [
                            {
                                "id": "en-segment",
                                "material_id": "en-1",
                                "target_timerange": {"start": 0, "duration": 1_000_000},
                            }
                        ],
                    },
                    {
                        "type": "audio",
                        "segments": [
                            {
                                "id": "audio-segment",
                                "material_id": "audio-1",
                                "source_timerange": {"start": 0, "duration": 1_200_000},
                                "target_timerange": {"start": 0, "duration": 1_000_000},
                                "speed": 1.2,
                                "volume": 0.8,
                            }
                        ],
                    },
                ],
            }
            (root / "draft_content.json").write_text(
                json.dumps(draft), encoding="utf-8"
            )

            report = import_draft(root, output)

            self.assertEqual(report["subtitle_counts"], {"zh": 1, "en": 1})
            self.assertEqual(report["dialogue_track_indexes"], [2])
            self.assertEqual(report["unmatched_zh_cues"], 0)
            row = json.loads((output / "timeline.jsonl").read_text().splitlines()[0])
            self.assertEqual(row["translation_en_draft"], "Hello")
            self.assertEqual(row["dialogue_segment_ids"], ["audio-segment"])
            plan = json.loads(
                (output / "dialogue-plan.jsonl").read_text().splitlines()[0]
            )
            self.assertEqual(plan["reference_text_zh"], "你好")
            self.assertEqual(plan["target_duration_ms"], 1000)

    def test_combines_split_fragments_of_one_recorded_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "draft"
            output = Path(directory) / "output"
            audio = root / "materials/audio/line.wav"
            audio.parent.mkdir(parents=True)
            audio.write_bytes(b"test")
            draft = {
                "id": "draft-split",
                "duration": 4_000_000,
                "materials": {
                    "texts": [text_material("zh-1", "完整的一句话")],
                    "audios": [{
                        "id": "audio-1", "name": "line.wav", "type": "text_to_audio",
                        "path": "##_draftpath_placeholder_X_##/materials/audio/line.wav",
                    }],
                },
                "tracks": [
                    {"type": "text", "segments": [{
                        "id": "zh-segment", "material_id": "zh-1",
                        "target_timerange": {"start": 1_000_000, "duration": 2_500_000},
                    }]},
                    {"type": "audio", "segments": [
                        {
                            "id": "line-head", "material_id": "audio-1",
                            "source_timerange": {"start": 0, "duration": 1_000_000},
                            "target_timerange": {"start": 1_000_000, "duration": 900_000},
                        },
                        {
                            "id": "line-body", "material_id": "audio-1",
                            "source_timerange": {"start": 1_000_000, "duration": 2_000_000},
                            "target_timerange": {"start": 2_000_000, "duration": 1_500_000},
                        },
                    ]},
                ],
            }
            (root / "draft_content.json").write_text(json.dumps(draft))

            import_draft(root, output)

            plan = json.loads((output / "dialogue-plan.jsonl").read_text())
            self.assertEqual(plan["segment_id"], "line-body")
            self.assertEqual(plan["target_start_ms"], 1000)
            self.assertEqual(plan["target_duration_ms"], 2500)
            self.assertEqual(plan["reference_start_ms"], 0)
            self.assertEqual(plan["reference_duration_ms"], 3000)

    def test_does_not_steal_a_fragment_claimed_by_the_next_cue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "draft"
            output = Path(directory) / "output"
            audio = root / "materials/audio/lines.wav"
            audio.parent.mkdir(parents=True)
            audio.write_bytes(b"test")
            draft = {
                "id": "draft-two-lines", "duration": 4_000_000,
                "materials": {
                    "texts": [text_material("zh-1", "第一句"), text_material("zh-2", "第二句")],
                    "audios": [{
                        "id": "audio-1", "name": "lines.wav", "type": "text_to_audio",
                        "path": "##_draftpath_placeholder_X_##/materials/audio/lines.wav",
                    }],
                },
                "tracks": [
                    {"type": "text", "segments": [
                        {"id": "cue-1", "material_id": "zh-1", "target_timerange": {"start": 1_000_000, "duration": 1_500_000}},
                        {"id": "cue-2", "material_id": "zh-2", "target_timerange": {"start": 2_000_000, "duration": 1_500_000}},
                    ]},
                    {"type": "audio", "segments": [
                        {"id": "line-1", "material_id": "audio-1", "source_timerange": {"start": 0, "duration": 900_000}, "target_timerange": {"start": 1_000_000, "duration": 900_000}},
                        {"id": "line-2", "material_id": "audio-1", "source_timerange": {"start": 900_000, "duration": 1_500_000}, "target_timerange": {"start": 2_000_000, "duration": 1_500_000}},
                    ]},
                ],
            }
            (root / "draft_content.json").write_text(json.dumps(draft))

            import_draft(root, output)

            plans = [json.loads(line) for line in (output / "dialogue-plan.jsonl").read_text().splitlines()]
            self.assertEqual(
                [(row["segment_id"], row["target_duration_ms"]) for row in plans],
                [("line-1", 900), ("line-2", 1500)],
            )


if __name__ == "__main__":
    unittest.main()
