import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gearman_demo.gearman.codec import decode_payload, decode_result, encode_payload


class GearmanCodecTestCase(unittest.TestCase):
    def test_payload_roundtrip(self) -> None:
        encoded = encode_payload({"text": "hola"})
        self.assertEqual(decode_payload(encoded)["text"], "hola")

    def test_decode_result(self) -> None:
        result = json.dumps({"ok": True}).encode("utf-8")
        self.assertEqual(decode_result(result)["ok"], True)


if __name__ == "__main__":
    unittest.main()
