"""
Regression tests for PDF binary-stream contamination and source-fact quality validation.
Covers Audio Overview and Video Overview narration integrity.
"""

import unittest
import zlib

from backend.ai_engine import (
    _extract_source_facts,
    generateAudioScript,
    generateVideoStoryboard,
)
from backend.doc_processor import (
    extract_text_from_pdf_bytes,
    is_plausible_source_sentence,
)


def _build_synthetic_pdf(objects_bytes: bytes) -> bytes:
    return b"%PDF-1.4\n" + objects_bytes + b"\n%%EOF\n"


class NarrationCorruptionRegressionTests(unittest.TestCase):
    def test_01_synthetic_binary_font_stream_produces_no_text(self):
        # Simulated FlateDecode TrueType font stream (/FontFile2 /Length1) containing parenthesized binary bytes
        font_binary = b"\x00\x01\x00\x00(DA@$ 3V@ >@F'DzC>Y7vG\"4#> y*> FEG*C}D?X74VA!=@F' \"*<T!m:+X # !)\x00\x02"
        compressed = zlib.compress(font_binary)
        obj = (
            b"10 0 obj\n<</Filter/FlateDecode/Length1 79660/Length "
            + str(len(compressed)).encode()
            + b">>stream\n"
            + compressed
            + b"\nendstream\nendobj\n"
        )
        pdf = _build_synthetic_pdf(obj)
        pages, err = extract_text_from_pdf_bytes(pdf)
        self.assertEqual(pages, [])
        self.assertIsNotNone(err)
        self.assertIn("OCR", err)

    def test_02_synthetic_jbig2_and_image_streams_produce_no_text(self):
        # Simulated JBIG2Decode image stream containing parenthesized binary noise (actual reported pattern)
        jbig2_binary = (
            b"\x97\x4a\x42\x32(^G-\xcd\xb6\xc8\x8e$K.1#OLhi}\\;KQg?3\xd4\xaf"
            b"fK\xd6\xb0lg_\xca\xbaTv IU/YP\"Erh8\xda\x93Eo>v[:\xcd\xab'h;/min 7[.)\xff\xd9"
        )
        obj = (
            b"3 0 obj<</Subtype/Image/Length "
            + str(len(jbig2_binary)).encode()
            + b"/Filter/JBIG2Decode/BitsPerComponent 1/Width 2550/Height 3299>>stream\n"
            + jbig2_binary
            + b"\nendstream\nendobj\n"
        )
        pdf = _build_synthetic_pdf(obj)
        pages, err = extract_text_from_pdf_bytes(pdf)
        self.assertEqual(pages, [])
        self.assertIsNotNone(err)

    def test_03_legitimate_pdf_text_streams_extract_correctly(self):
        content_stream = (
            b"BT\n/F1 12 Tf\n72 720 Td\n"
            b"(Distributed consensus algorithms ensure safety across unreliable networks. ) Tj\n"
            b"(Raft separates leader election from log replication to simplify reasoning.) Tj\n"
            b"ET\n"
        )
        compressed = zlib.compress(content_stream)
        obj = (
            b"4 0 obj<</Filter/FlateDecode/Length "
            + str(len(compressed)).encode()
            + b">>stream\n"
            + compressed
            + b"\nendstream\nendobj\n"
        )
        pdf = _build_synthetic_pdf(obj)
        pages, err = extract_text_from_pdf_bytes(pdf)
        self.assertIsNone(err)
        self.assertEqual(len(pages), 1)
        self.assertIn("Distributed consensus algorithms", pages[0])
        self.assertIn("Raft separates leader election", pages[0])

    def test_04_parenthesized_strings_in_binary_stream_without_operators_rejected(self):
        # Even without /Subtype/Image, raw binary data with (...) but no BT/ET or Tj/TJ must not be parsed as text
        raw_bin = b"\x00\x05\x10(This looks parenthesized but sits inside raw binary data without PDF operators.)\x00\x03"
        obj = (
            b"5 0 obj<</Length " + str(len(raw_bin)).encode() + b">>stream\n" + raw_bin + b"\nendstream\nendobj\n"
        )
        pdf = _build_synthetic_pdf(obj)
        pages, err = extract_text_from_pdf_bytes(pdf)
        self.assertEqual(pages, [])
        self.assertIsNotNone(err)

    def test_05_reported_corrupted_strings_rejected_by_validator(self):
        corrupted_samples = [
            "^G-\u0376\u020e$K.1#OLhi}\\;KQg?3\u052ffK\u05b0lg_\u02baTv IU/YP\"Erh8\u0693Eo>v[:\u036b'h;/min 7[.",
            "DA@$ 3V@ >@F'DzC>Y7vG\"4#> y*> FEG*C}D?X74VA!=@F' \"*<T!m:+X # !",
            "S#L#]@V?+?+/01L\\@ S#L#]@V?+?+01Y#\".54>324.#\"32>P\u9657KP\u9693M M`aP!",
            "q\"t.4{},V_\u01b7s\u4538\u014dUFV*x3\u04d13Cf_L& G*jV:%k8DyG\\+a\u0488I0D4S Q!i\\=n:fM4g?\u018dU4$Ojkh!wzo2[",
        ]
        for sample in corrupted_samples:
            self.assertFalse(is_plausible_source_sentence(sample), f"Should reject: {sample}")

    def test_06_legitimate_math_code_and_currency_survive_validation(self):
        valid_samples = [
            "E = mc^2 + 3.14 * 10^-5 (J/kg), where \u0394G = \u0394H - T\u0394S \u2248 -42.5 kJ/mol.",
            "const result = items.filter((x) => x.score >= 0.85 && !x.disabled).map((x) => x.id);",
            "Q3 revenue grew +24.5% from $1,250,000 to \u20ac1,480,000 (\u00a31,120,000 / \u20b912,50,000).",
        ]
        for sample in valid_samples:
            self.assertTrue(is_plausible_source_sentence(sample), f"Should accept: {sample}")

    def test_07_valid_multilingual_text_survives_validation(self):
        multilingual_samples = [
            "\u0c07\u0c26\u0c3f \u0c15\u0c02\u0c2a\u0c4d\u0c2f\u0c42\u0c1f\u0c30\u0c4d \u0c38\u0c48\u0c28\u0c4d\u0c38\u0c4d \u0c2e\u0c30\u0c3f\u0c2f\u0c41 \u0c21\u0c47\u0c1f\u0c3e \u0c38\u0c4d\u0c1f\u0c4d\u0c30\u0c15\u0c4d\u0c1a\u0c30\u0c4d\u0c32 \u0c17\u0c41\u0c30\u0c3f\u0c02\u0c1a\u0c3f \u0c2e\u0c41\u0c16\u0c4d\u0c2f\u0c2e\u0c48\u0c28 \u0c38\u0c2e\u0c3e\u0c1a\u0c3e\u0c30\u0c02.",
            "\u092f\u0939 \u0921\u0947\u091f\u093e\u092c\u0947\u0938 \u0907\u0902\u0921\u0947\u0915\u094d\u0938\u093f\u0902\u0917 \u0914\u0930 \u091f\u094d\u0930\u093e\u0902\u091c\u093c\u0948\u0915\u094d\u0936\u0928\u0932 \u0915\u0902\u0938\u093f\u0938\u094d\u091f\u0947\u0902\u0938\u0940 \u0915\u093e \u090f\u0915 \u092e\u0939\u0924\u094d\u0935\u092a\u0942\u0930\u094d\u0923 \u0909\u0926\u093e\u0939\u0930\u0923 \u0939\u0948\u0964",
            "\u0c87\u0ca6\u0cc1 \u0cb8\u0cbe\u0cab\u0ccd\u0c9f\u0ccd\u200c\u0cb5\u0cc7\u0cb0\u0ccd \u0c86\u0cb0\u0ccd\u0c95\u0cbf\u0c9f\u0cc6\u0c95\u0ccd\u0c9a\u0cb0\u0ccd \u0cae\u0ca4\u0ccd\u0ca4\u0cc1 \u0cb5\u0cbf\u0ca8\u0ccd\u0caf\u0cbe\u0cb8 \u0ca4\u0ca4\u0ccd\u0cb5\u0c97\u0cb3 \u0c95\u0cc1\u0cb0\u0cbf\u0ca4\u0cc1 \u0caa\u0ccd\u0cb0\u0cae\u0cc1\u0c96 \u0cae\u0cbe\u0cb9\u0cbf\u0ca4\u0cbf\u0caf\u0cbe\u0c97\u0cbf\u0ca6\u0cc6.",
            "\u0b87\u0ba4\u0bc1 \u0bae\u0bc6\u0ba9\u0bcd\u0baa\u0bca\u0bb0\u0bc1\u0bb3\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bb0\u0bb5\u0bc1\u0ba4\u0bcd\u0ba4\u0bb3 \u0bae\u0bc7\u0bb2\u0bbe\u0ba3\u0bcd\u0bae\u0bc8 \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf\u0bae\u0bbe\u0ba9 \u0ba4\u0b95\u0bb5\u0bb2\u0bbe\u0b95\u0bc1\u0bae\u0bcd.",
            "\u0939\u0947 \u0938\u0949\u092b\u094d\u091f\u0935\u0947\u0905\u0930 \u0906\u0930\u094d\u0915\u093f\u091f\u0947\u0915\u094d\u091a\u0930 \u0906\u0923\u093f \u0921\u0947\u091f\u093e\u092c\u0947\u0938 \u0938\u093f\u0938\u094d\u091f\u0940\u092e\u092c\u0926\u094d\u0926\u0932 \u092e\u0939\u0924\u094d\u0924\u094d\u0935\u093e\u091a\u0947 \u0938\u094d\u092a\u0937\u094d\u091f\u0940\u0915\u0930\u0923 \u0906\u0939\u0947.",
        ]
        for sample in multilingual_samples:
            self.assertTrue(is_plausible_source_sentence(sample), f"Should accept multilingual: {sample}")

    def test_08_audio_overview_excludes_corrupted_facts(self):
        chunks = [
            {
                "source_id": "src_test_1",
                "source_title": "World War I Notes",
                "page_number": 1,
                "section_title": "Chapter 1",
                "content": (
                    "^G-\u0376\u020e$K.1#OLhi}\\;KQg?3\u052ffK\u05b0lg_\u02baTv IU/YP\"Erh8\u0693Eo>v[:\u036b'h;/min 7[. "
                    "The Treaty of Versailles formally ended the state of war between Germany and the Allied Powers in 1919."
                ),
            }
        ]
        audio_res = generateAudioScript(chunks, {"topic": "World War I", "language": "English"})
        joined = " ".join(turn["text"] for turn in audio_res["dialogue"])
        self.assertNotIn("OLhi", joined)
        self.assertNotIn("^G-", joined)
        self.assertIn("Treaty of Versailles", joined)

    def test_09_video_overview_excludes_corrupted_facts(self):
        chunks = [
            {
                "source_id": "src_test_2",
                "source_title": "JS Variables",
                "page_number": 1,
                "section_title": "Variables",
                "content": (
                    "DA@$ 3V@ >@F'DzC>Y7vG\"4#> y*> FEG*C}D?X74VA!=@F' \"*<T!m:+X # ! "
                    "JavaScript variables declared with let and const are block-scoped to their enclosing block."
                ),
            }
        ]
        video_res = generateVideoStoryboard(chunks, {"topic": "JS Variables", "language": "English"})
        joined = " ".join(scene["narration"] for scene in video_res["scenes"])
        self.assertNotIn("DA@$", joined)
        self.assertNotIn("FEG*C", joined)
        self.assertIn("block-scoped", joined)

    def test_10_source_attribution_and_normal_extraction_intact(self):
        chunks = [
            {
                "source_id": "src_attr_1",
                "source_title": "Database Internals",
                "page_number": 4,
                "section_title": "WAL Logging",
                "content": "Write-Ahead Logging records changes sequentially before updating B-Tree pages on disk.",
            }
        ]
        topic, facts, refs = _extract_source_facts(chunks, "Databases")
        self.assertEqual(topic, "Database Internals")
        self.assertIn("Write-Ahead Logging records changes sequentially before updating B-Tree pages on disk.", facts)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["source_id"], "src_attr_1")
        self.assertEqual(refs[0]["page_number"], 4)
        self.assertEqual(refs[0]["section_title"], "WAL Logging")


if __name__ == "__main__":
    unittest.main(verbosity=2)

