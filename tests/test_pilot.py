import json
import tempfile
import unittest
from pathlib import Path

from castdub.pilot import PilotError, _synthesis_fingerprint, load_pilot_config


class PilotConfigTests(unittest.TestCase):
    def test_accepts_known_roles_and_positive_ranges(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pilot.json"
            path.write_text(
                json.dumps(
                    {
                        "roles": {"lead": {}},
                        "utterances": [
                            {
                                "id": "u1",
                                "role": "lead",
                                "start_ms": 10,
                                "end_ms": 20,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(load_pilot_config(path)["utterances"][0]["id"], "u1")

    def test_rejects_cross_role_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pilot.json"
            path.write_text(
                json.dumps(
                    {
                        "roles": {"lead": {}},
                        "utterances": [
                            {
                                "id": "u1",
                                "role": "other",
                                "start_ms": 10,
                                "end_ms": 20,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(PilotError):
                load_pilot_config(path)

    def test_synthesis_fingerprint_changes_with_emotion_or_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / "reference.wav"
            reference.write_bytes(b"voice-a")
            item = {"target_text": "Hola", "role": "lead", "emotion": "calm"}
            calm = _synthesis_fingerprint(item, str(reference), "你好")
            excited = _synthesis_fingerprint(
                {**item, "emotion": "excited"}, str(reference), "你好"
            )
            reference.write_bytes(b"voice-b")
            different_voice = _synthesis_fingerprint(item, str(reference), "你好")
            self.assertNotEqual(calm, excited)
            self.assertNotEqual(calm, different_voice)


if __name__ == "__main__":
    unittest.main()
