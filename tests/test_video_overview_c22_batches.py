import json
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


class TestAdaptiveBatchedContinuationC22(unittest.TestCase):
    def test_01_exceeds_24_scenes_without_discarding_concepts(self):
        from backend.ai_engine import generateVideoStoryboard

        # Build a massive multi-section source with 28 distinct concepts
        chunks = []
        for i in range(1, 29):
            chunks.append(
                {
                    "chunk_id": f"chk_{i}",
                    "source_id": "src_mega",
                    "source_title": "Comprehensive Systems & Science Textbook",
                    "section_title": f"Section {i}: Module {i}",
                    "page_number": i,
                    "content": (
                        f"Module{i}Token defines principle number {i} in quantitative systems analysis. "
                        f"It governs stability parameter alpha{i} across distributed workloads."
                    ),
                }
            )

        batch1 = generateVideoStoryboard(
            chunks,
            {"topic": "Comprehensive Systems & Science", "language": "English"},
            {},
            source_ids=["src_mega"],
        )
        m1 = batch1["planning_metrics"]
        print("BATCH1_METRICS:", json.dumps(m1))

        self.assertEqual(len(batch1["scenes"]), 24)
        self.assertGreaterEqual(m1["total_planned_scenes"], 28)
        self.assertTrue(m1["has_more_batches"])
        self.assertEqual(m1["next_batch_offset"], 24)
        self.assertEqual(m1["remaining_scenes"], m1["total_planned_scenes"] - 24)
        self.assertEqual(m1["coverage_ratio"], 1.0)

        batches = [batch1]
        cur_metrics = m1
        while cur_metrics["has_more_batches"]:
            nxt = generateVideoStoryboard(
                chunks,
                {
                    "topic": "Comprehensive Systems & Science",
                    "language": "English",
                    "batch_offset": cur_metrics["next_batch_offset"],
                },
                {},
                source_ids=["src_mega"],
            )
            batches.append(nxt)
            cur_metrics = nxt["planning_metrics"]
            print(f"BATCH{len(batches)}_METRICS:", json.dumps(cur_metrics))

        self.assertFalse(cur_metrics["has_more_batches"])
        self.assertIsNone(cur_metrics["next_batch_offset"])
        self.assertEqual(cur_metrics["remaining_scenes"], 0)
        self.assertEqual(
            sum(len(b["scenes"]) for b in batches),
            m1["total_planned_scenes"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
