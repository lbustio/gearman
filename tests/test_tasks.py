import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gearman_demo.domain.text_tasks import (
    analyze_text,
    compress_text,
    shard_text,
)


class TasksTestCase(unittest.TestCase):
    def test_shard_text(self) -> None:
        text = "abcdefghi"
        shards = shard_text(text, shard_size=4)
        self.assertEqual(shards, ["abcd", "efgh", "i"])

    def test_shard_size_invalid(self) -> None:
        with self.assertRaises(ValueError):
            shard_text("abc", shard_size=0)

    def test_compress_text(self) -> None:
        compressed = compress_text("hola hola hola mundo")
        self.assertEqual(compressed, "hola:3|mundo:1")

    def test_analyze_text(self) -> None:
        result = analyze_text("excelente excelente terrible bug")
        self.assertEqual(result["tokens"], 4)
        self.assertEqual(result["sentiment"]["score"], 0)
        self.assertEqual(result["top_tokens"][0][0], "excelente")


if __name__ == "__main__":
    unittest.main()
