import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.ai_engine import (
    InsufficientSourceEvidenceError,
    _extract_fact_items,
    _resolve_spoken_topic,
    generateAudioScript,
)
from backend.audio_concept_engine import (
    build_audio_concept_model,
    build_teaching_sequence,
    extract_verified_key_takeaways,
    normalize_spoken_text_for_tts,
    synthesize_concept_dialogue,
    validate_audio_dialogue,
    validate_cross_output_consistency,
)


class AudioConceptDialogueEngineTests(unittest.TestCase):
    def test_01_biology_cellular_respiration_concept_model_cautions_and_gaps(self):
        chunks = [
            {
                "source_id": "src_bio",
                "source_title": "biology pdf",
                "page_number": 1,
                "section_title": "Page 1",
                "content": (
                    "A good way to remember which molecule is being oxidized or reduced is to use the acronym "
                    "\"OIL RIG\" - Oxidation Is Losing, Reduction Is Gaining. "
                    "In this acronym \"gaining\" and \"losing\" refer to electrons being transferred. "
                    "The oxidation and reduction reactions are coupled since, as one compound gains electrons, another must give them up. "
                    "In cellular respiration, glucose and its intermediates are always oxidized. "
                    "It is important to note that because H + are being pulled from NADH and FADH 2, both products, NAD + and FAD +, are the oxidized form of the coenzyme. "
                    "The movement of H + into the intermembrane space creates a concentration gradient and a buildup of pressure. "
                    "To release this pressure, the H + passes through ATP s yntha se. "
                    "T he kinetic energy of H + moving through the enzyme is captured and used to phosphorylate ADP to produce ATP. "
                    "This type of ATP production is called oxidative phosphorylation and is responsible for about 90% of the total ATP produced in cellular respiration."
                ),
            },
            {
                "source_id": "src_bio",
                "source_title": "biology pdf",
                "page_number": 2,
                "section_title": "Page 2",
                "content": (
                    "Pathway ATP Produced NADH Produced FADH 2 Produced Glycolysis 4 2 0 Pyruvate Oxidation 0 2 0 Krebs Cycle 2 6 2 Total 38 10 2 "
                    "The first step, glycolysis, takes place outside the mitochondria, while the other three steps, pyruvate oxidation, Krebs cycle, and electron transport chain, take place inside the mitochondria. "
                    "Fermentation occurs after glycolysis when oxygen is in low concentration or not present, meaning that it is anaerobic respiration. "
                    "No additional ATP is created through fermentation. "
                    "There are two types of fermentation: ethanol fermentation, found in plants, and lactic acid fermentation, found in animals and bacteria. "
                    "In ethanol fermentation, pyruvate is oxidized and turned into ethanol; carbon dioxide is also produced as a byproduct in the reaction."
                ),
            },
        ]

        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            out = generateAudioScript(chunks, {"topic": "Cellular Respiration", "language": "English"}, user_prefs={})

        self.assertEqual(out["generation_provider"], "local_structured_engine")
        self.assertFalse(out["llm_grounded"])
        validation = validate_audio_dialogue(out["dialogue"], source_refs=out["source_references"])
        self.assertTrue(validation["passed"], f"Dialogue validation failed: {validation['issues']}")

        joined = " ".join(t["text"] for t in out["dialogue"])
        # Kerning & notation cleanups applied
        self.assertNotIn("T he", joined)
        self.assertNotIn("s yntha se", joined)
        self.assertNotIn("H +", joined)
        self.assertIn("ATP synthase", joined)
        # Scientific clarification prevents blindly parroting 'pyruvate is oxidized' as unqualified truth
        self.assertIn("acetaldehyde", joined.lower())
        self.assertIn("lactate", joined.lower())
        # Insufficiently explained table/stage topics are honestly flagged
        gap_topics = {g["topic"].lower() for g in out.get("coverage_report", [])}
        self.assertIn("pyruvate oxidation", gap_topics)
        self.assertIn("krebs cycle", gap_topics)

    def test_02_computer_science_concept_driven_dialogue(self):
        chunks = [
            {
                "source_id": "src_cs",
                "source_title": "Operating Systems Notes",
                "page_number": 4,
                "section_title": "Processes and Scheduling",
                "content": (
                    "A process is an executing program instance with its own isolated virtual address space. "
                    "Threads within the same process share memory and open file descriptors, which makes context switching faster than switching processes. "
                    "Because multiple threads can access shared data concurrently, race conditions occur when synchronization primitives such as mutexes are omitted. "
                    "Preemptive CPU scheduling interrupts running tasks after a time quantum expires so interactive workloads remain responsive. "
                    "However, strict priority scheduling without aging can cause starvation for low-priority tasks."
                ),
            }
        ]
        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            out = generateAudioScript(chunks, {"topic": "Operating Systems Scheduling", "language": "English"}, user_prefs={})

        validation = validate_audio_dialogue(out["dialogue"], source_refs=out["source_references"])
        self.assertTrue(validation["passed"], f"CS validation failed: {validation['issues']}")
        joined = " ".join(t["text"] for t in out["dialogue"]).lower()
        self.assertIn("virtual address space", joined)
        self.assertIn("starvation", joined)
        self.assertIn("page 4", joined)

    def test_03_macroeconomics_third_unrelated_subject(self):
        chunks = [
            {
                "source_id": "src_econ",
                "source_title": "Macroeconomics Lecture",
                "page_number": 9,
                "section_title": "Monetary Policy",
                "content": (
                    "Inflation measures the sustained rise in the general price level of goods and services over time. "
                    "Central banks adjust short-term policy interest rates to influence borrowing costs and aggregate demand. "
                    "When interest rates rise, businesses and households typically reduce borrowing, which cools spending and eases inflationary pressure. "
                    "Unlike fiscal policy, which relies on government taxation and spending, monetary policy operates primarily through liquidity and credit conditions."
                ),
            }
        ]
        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            out = generateAudioScript(chunks, {"topic": "Monetary Policy", "language": "English"}, user_prefs={})

        validation = validate_audio_dialogue(out["dialogue"], source_refs=out["source_references"])
        self.assertTrue(validation["passed"], f"Econ validation failed: {validation['issues']}")
        joined = " ".join(t["text"] for t in out["dialogue"]).lower()
        self.assertIn("interest rates", joined)
        self.assertIn("fiscal policy", joined)
        self.assertIn("page 9", joined)

    def test_04_short_pdf_produces_concise_dialogue_without_padding(self):
        short_chunks = [
            {
                "source_id": "src_short",
                "source_title": "Quick Note",
                "page_number": 1,
                "section_title": "Summary",
                "content": (
                    "Photosynthesis converts light energy into chemical energy stored in glucose. "
                    "Chlorophyll pigments inside chloroplasts absorb red and blue wavelengths of light."
                ),
            }
        ]
        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            out = generateAudioScript(short_chunks, {"topic": "Photosynthesis", "language": "English"}, user_prefs={})

        self.assertEqual(len(out["dialogue"]), 3)
        validation = validate_audio_dialogue(out["dialogue"], source_refs=out["source_references"])
        self.assertTrue(validation["passed"], f"Short PDF validation failed: {validation['issues']}")

    def test_05_missing_or_insufficient_evidence_raises(self):
        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            with self.assertRaises(InsufficientSourceEvidenceError):
                generateAudioScript([], {"topic": "Empty", "language": "English"}, user_prefs={})
            with self.assertRaises(InsufficientSourceEvidenceError):
                generateAudioScript(
                    [{"source_id": "s1", "page_number": 1, "content": "2 x ATP 6 x NADH + H."}],
                    {"topic": "Broken", "language": "English"},
                    user_prefs={},
                )

    def test_06_validator_catches_duplicates_repetitive_questions_unsupported_pages_and_grammar(self):
        bad_dialogue = [
            {"speaker": "Alex", "role": "Lead Host", "text": "How does the material explain X?"},
            {"speaker": "Maya", "role": "Subject Expert", "text": "The material notes that No additional ATP is formed on page 99."},
            {"speaker": "Alex", "role": "Lead Host", "text": "How does the material explain Y?"},
            {"speaker": "Maya", "role": "Subject Expert", "text": "The material notes that T he kinetic energy creates ATP on page 1."},
            {"speaker": "Maya", "role": "Subject Expert", "text": "This exact long sentence is duplicated across two separate turns for testing purposes."},
            {"speaker": "Maya", "role": "Subject Expert", "text": "This exact long sentence is duplicated across two separate turns for testing purposes."},
        ]
        report = validate_audio_dialogue(bad_dialogue, source_refs=[{"page_number": 1}])
        self.assertFalse(report["passed"])
        issues_joined = " | ".join(report["issues"]).lower()
        self.assertIn("duplicate alex question prefix", issues_joined)
        self.assertIn("mechanical boilerplate", issues_joined)
        self.assertIn("that no", issues_joined)
        self.assertIn("kerning artifact", issues_joined)
        self.assertIn("unsupported page 99", issues_joined)
        self.assertIn("duplicate factual sentence", issues_joined)

    def test_07_atp_synthase_water_conflation_and_pyruvate_redox_regression(self):
        bio_chunks = [
            {
                "source_id": "src_bio_reg",
                "source_title": "biology pdf",
                "page_number": 1,
                "section_title": "Page 1",
                "content": (
                    "A good way to remember which molecule is being oxidized or reduced is to use the acronym "
                    "\"OIL RIG\" - Oxidation Is Losing, Reduction Is Gaining. "
                    "The oxygen later reacts with H + to form water. "
                    "The movement of H + into the intermembrane space creates a concentration gradient and a buildup of pressure. "
                    "To release this pressure, the H + passes through ATP synthase. "
                    "The kinetic energy of H + moving through the enzyme is captured and used to phosphorylate ADP to produce ATP. "
                    "This type of ATP production is called oxidative phosphorylation and is responsible for about 90% of the total ATP produced in cellular respiration. "
                    "When the H + go through the ATP synthase, they react with oxygen to produce water, H 2 O."
                ),
            },
            {
                "source_id": "src_bio_reg",
                "source_title": "biology pdf",
                "page_number": 2,
                "section_title": "Page 2",
                "content": (
                    "No additional ATP is created through fermentation. "
                    "There are two types of fermentation: ethanol fermentation, found in plants, and lactic acid fermentation, found in animals and bacteria. "
                    "In ethanol fermentation, pyruvate is oxidized and turned into ethanol; carbon dioxide is also produced as a byproduct in the reaction. "
                    "The other form of fermentation is lactic acid fermentation, which is similar to ethanol fermentation in that pyruvate is oxidized again, but this time the pyruvate is converted to lactic acid."
                ),
            },
        ]
        _, fact_items, refs = _extract_fact_items(bio_chunks, "Cellular Respiration", max_facts=40)
        model = build_audio_concept_model("Cellular Respiration", fact_items, chunks=bio_chunks)
        self.assertTrue(model["contradictions"], "Expected redox contradiction to be detected in concept model")

        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            out = generateAudioScript(bio_chunks, {"topic": "Cellular Respiration", "language": "English"}, user_prefs={})

        joined = " ".join(t["text"] for t in out["dialogue"])
        low = joined.lower()
        # Must NOT conflate ATP synthase proton flow with oxygen reduction
        self.assertNotIn("go through the atp synthase, they react with oxygen", low)
        self.assertIn("does not react with oxygen", low)
        self.assertIn("end of the electron transport chain", low)
        # Must NOT present 'pyruvate is oxidized' as an unqualified fact or claim direct pyruvate->ethanol reduction
        self.assertNotIn("pyruvate is oxidized and turned into ethanol", low)
        self.assertNotIn("pyruvate is directly reduced to ethanol", low)
        self.assertIn("decarboxylated to acetaldehyde", low)
        self.assertIn("acetaldehyde is subsequently reduced by nadh to ethanol", low)
        self.assertIn("pyruvate is directly reduced by nadh to lactate", low)
        self.assertIn("regenerating nad+", low)
        self.assertIn("yeast", low)
        self.assertIn("animal muscle cells", low)
        # Causal ordering: ADP phosphorylation precedes 'this type of ATP production'
        self.assertLess(low.find("phosphorylate adp"), low.find("this type of atp production"))

        report = validate_audio_dialogue(out["dialogue"], source_refs=refs)
        self.assertTrue(report["passed"], f"Regression validation failed: {report['issues']}")

    def test_08_semantic_validator_catches_scientific_and_ordering_errors(self):
        flawed_dialogue = [
            {"speaker": "Alex", "role": "Lead Host", "text": "How does ATP synthase work here?"},
            {
                "speaker": "Maya",
                "role": "Subject Expert",
                "text": (
                    "On page 1, this type of ATP production is called oxidative phosphorylation. "
                    "When the H+ go through the ATP synthase, they react with oxygen to produce water, H2O."
                ),
            },
            {"speaker": "Alex", "role": "Lead Host", "text": "What happens in fermentation?"},
            {
                "speaker": "Maya",
                "role": "Subject Expert",
                "text": "On page 2, in ethanol fermentation, pyruvate is oxidized and turned into ethanol.",
            },
        ]
        report = validate_audio_dialogue(flawed_dialogue, source_refs=[{"page_number": 1}, {"page_number": 2}])
        self.assertFalse(report["passed"])
        issues_joined = " | ".join(report["issues"]).lower()
        self.assertIn("conflates proton flow through atp synthase with oxygen reduction", issues_joined)
        self.assertIn("pyruvate is oxidized", issues_joined)
        self.assertIn("before explaining adp phosphorylation", issues_joined)

    def test_09_fermentation_two_pathway_and_direct_ethanol_rejection(self):
        flawed_direct_ethanol = [
            {"speaker": "Alex", "role": "Lead Host", "text": "How does alcoholic fermentation work?"},
            {
                "speaker": "Maya",
                "role": "Subject Expert",
                "text": "On page 2, pyruvate is directly reduced by NADH to ethanol, regenerating NAD+.",
            },
            {"speaker": "Alex", "role": "Lead Host", "text": "That wraps up our review of fermentation pathways."},
        ]
        report = validate_audio_dialogue(flawed_direct_ethanol, source_refs=[{"page_number": 2}])
        self.assertFalse(report["passed"])
        issues_joined = " | ".join(report["issues"]).lower()
        self.assertIn("directly reduced to ethanol without acetaldehyde", issues_joined)

    def test_10_verified_takeaways_propagation_and_cross_output_consistency(self):
        bio_chunks = [
            {
                "source_id": "src_cons",
                "source_title": "biology pdf",
                "page_number": 1,
                "section_title": "Page 1",
                "content": (
                    "A good way to remember which molecule is being oxidized or reduced is to use the acronym "
                    "\"OIL RIG\" - Oxidation Is Losing, Reduction Is Gaining. "
                    "It is important to note that because H + are being pulled from NADH and FADH 2, both products, NAD + and FAD +, are the oxidized form of the coenzyme. "
                    "The movement of H + into the intermembrane space creates a concentration gradient and a buildup of pressure. "
                    "To release this pressure, the H + passes through ATP synthase. "
                    "The kinetic energy of H + moving through the enzyme is captured and used to phosphorylate ADP to produce ATP. "
                    "When the H + go through the ATP synthase, they react with oxygen to produce water, H 2 O."
                ),
            },
            {
                "source_id": "src_cons",
                "source_title": "biology pdf",
                "page_number": 2,
                "section_title": "Page 2",
                "content": (
                    "No additional ATP is created through fermentation. "
                    "There are two types of fermentation: ethanol fermentation, found in plants, and lactic acid fermentation, found in animals and bacteria. "
                    "In ethanol fermentation, pyruvate is oxidized and turned into ethanol; carbon dioxide is also produced as a byproduct in the reaction."
                ),
            },
        ]
        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            out = generateAudioScript(bio_chunks, {"topic": "Cellular Respiration", "language": "English"}, user_prefs={})

        takeaways_joined = " ".join(out["key_takeaways"]).lower()
        # No uncorrected raw errors in key_takeaways
        self.assertNotIn("pyruvate is oxidized and turned into ethanol", takeaways_joined)
        self.assertNotIn("go through the atp synthase, they react with oxygen", takeaways_joined)
        self.assertNotIn("found in plants, and lactic acid fermentation, found in animals", takeaways_joined)

        # Cross-output consistency validator catches any raw-fact leakage
        _, fact_items, _ = _extract_fact_items(bio_chunks, "Cellular Respiration", max_facts=40)
        model = build_audio_concept_model("Cellular Respiration", fact_items, chunks=bio_chunks)
        bad_cons = validate_cross_output_consistency(
            out["dialogue"],
            ["In ethanol fermentation, pyruvate is oxidized and turned into ethanol; carbon dioxide is also produced as a byproduct in the reaction."],
            model,
        )
        self.assertFalse(bad_cons["passed"])

    def test_11_tts_spoken_notation_separate_from_visual_text(self):
        visual = "H+ ions move while NADH and FADH2 oxidize to NAD+ and FAD, releasing CO2 and forming water (H2O) from O2."
        spoken = normalize_spoken_text_for_tts(visual)
        # Visual unchanged
        self.assertIn("H+", visual)
        self.assertIn("NAD+", visual)
        # Spoken normalized safely
        self.assertIn("hydrogen ions", spoken)
        self.assertIn("N-A-D-H", spoken)
        self.assertIn("F-A-D-H two", spoken)
        self.assertIn("N-A-D plus", spoken)
        self.assertIn("carbon dioxide", spoken)
        self.assertIn("forming water from oxygen", spoken)
        # Ordinary words untouched
        ordinary = "High altitude had a cooperative effort."
        self.assertEqual(normalize_spoken_text_for_tts(ordinary), ordinary)

    def test_12_tts_engine_consumes_spoken_text_over_visual_text(self):
        from unittest.mock import patch
        from backend.tts_engine import synthesize_podcast_audio

        captured_scripts = []

        def fake_run(cmd, **kwargs):
            ps_path = cmd[-1]
            with open(ps_path, "r", encoding="utf-8-sig") as f:
                captured_scripts.append(f.read())

            class Proc:
                returncode = 1

            return Proc()

        dialogue = [
            {
                "speaker": "Alex",
                "text": "H+ ions and NADH oxidize to NAD+ releasing CO2.",
                "spoken_text": "hydrogen ions ions and N-A-D-H oxidize to N-A-D plus releasing carbon dioxide.",
            },
            {
                "speaker": "Maya",
                "text": "Fallback visual text when spoken_text is absent.",
            },
        ]
        with patch("backend.tts_engine.subprocess.run", side_effect=fake_run):
            synthesize_podcast_audio(
                "unit_test_tts_spoken",
                dialogue,
                openai_api_key="",
                language="English",
                require_native_voice=True,
            )

        self.assertEqual(len(captured_scripts), 1)
        script_body = captured_scripts[0]
        self.assertIn("N-A-D-H oxidize to N-A-D plus releasing carbon dioxide.", script_body)
        self.assertNotIn("H+ ions and NADH", script_body)
        self.assertIn("Fallback visual text when spoken_text is absent.", script_body)

    def test_13_cross_subject_concept_names_relationships_and_takeaways(self):
        # 1. Economics Monetary Policy: no 'Unlike' concept name, first Q matches Turn 2, independent takeaways
        econ_chunks = [
            {
                "source_id": "src_econ_q",
                "source_title": "Macroeconomics Lecture",
                "page_number": 9,
                "section_title": "Monetary Policy",
                "content": (
                    "Inflation measures the sustained rise in the general price level of goods and services over time. "
                    "Central banks adjust short-term policy interest rates to influence borrowing costs and aggregate demand. "
                    "When interest rates rise, businesses and households typically reduce borrowing, which cools spending and eases inflationary pressure. "
                    "Unlike fiscal policy, which relies on government taxation and spending, monetary policy operates primarily through liquidity and credit conditions."
                ),
            }
        ]
        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            econ_out = generateAudioScript(econ_chunks, {"topic": "Monetary Policy", "language": "English"}, user_prefs={})

        econ_joined = " ".join(t["text"] for t in econ_out["dialogue"]).lower()
        self.assertNotIn("with unlike?", econ_joined)
        self.assertNotIn("through unlike", econ_joined)
        self.assertNotIn("shows how energy or inputs are transformed", econ_joined)
        self.assertIn("inflation", econ_out["dialogue"][0]["text"].lower())
        self.assertIn("inflation", econ_out["dialogue"][1]["text"].lower())
        for tk in econ_out["key_takeaways"]:
            self.assertFalse(tk.lower().startswith(("however,", "unlike ")), f"Takeaway not independent: {tk}")

        # 2. CS Operating Systems: no 'However' concept name, no raw token-list links
        cs_chunks = [
            {
                "source_id": "src_cs_q",
                "source_title": "Operating Systems Notes",
                "page_number": 4,
                "section_title": "Processes and Scheduling",
                "content": (
                    "A process is an executing program instance with its own isolated virtual address space. "
                    "Threads within the same process share memory and open file descriptors, which makes context switching faster than switching processes. "
                    "Because multiple threads can access shared data concurrently, race conditions occur when synchronization primitives such as mutexes are omitted. "
                    "Preemptive CPU scheduling interrupts running tasks after a time quantum expires so interactive workloads remain responsive. "
                    "However, strict priority scheduling without aging can cause starvation for low-priority tasks."
                ),
            }
        ]
        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            cs_out = generateAudioScript(cs_chunks, {"topic": "Operating Systems Scheduling", "language": "English"}, user_prefs={})

        cs_joined = " ".join(t["text"] for t in cs_out["dialogue"]).lower()
        self.assertNotIn("with however?", cs_joined)
        self.assertNotIn("through however", cs_joined)
        self.assertNotIn("shows how energy or inputs are transformed", cs_joined)
        self.assertTrue(validate_audio_dialogue(cs_out["dialogue"], source_refs=cs_out["source_references"])["passed"])
        for tk in cs_out["key_takeaways"]:
            self.assertFalse(tk.lower().startswith(("however,", "unlike ")), f"Takeaway not independent: {tk}")

        # 3. Validator rejects raw keyword-list relationships and discourse-marker concept names
        bad_dialogue = [
            {"speaker": "Alex", "role": "Lead Host", "text": "Where should a learner start with However?"},
            {"speaker": "Maya", "role": "Subject Expert", "text": "Inflation links directly to Interest Rates through rise."},
            {"speaker": "Alex", "role": "Lead Host", "text": "To sum up, Inflation shows how energy or inputs are transformed."},
        ]
        bad_rep = validate_audio_dialogue(bad_dialogue)
        self.assertFalse(bad_rep["passed"])
        bad_joined = " | ".join(bad_rep["issues"]).lower()
        self.assertIn("discourse marker", bad_joined)
        self.assertIn("raw keyword-list relationship", bad_joined)
        self.assertIn("shows how energy or inputs are transformed", bad_joined)

    def test_14_cs_math_tts_normalization_and_general_kerning_repair(self):
        from backend.doc_processor import repair_pdf_kerning_splits

        # Big-O notation spoken normalization
        vis = "B-Tree lookups run in O(log N), hash lookups run in O(1) time, and worst-case scans take O(n)."
        spk = normalize_spoken_text_for_tts(vis)
        self.assertIn("O(log N)", vis)
        self.assertIn("O of log N", spk)
        self.assertIn("constant time", spk)
        self.assertIn("O of n", spk)

        # General kerning repair: fixes broken fragments without joining valid words or code
        broken = "A Ja vaS c r ip t var ia b le i s si m p l y a n a m e of st or age l o c ati on, for example val u e1."
        repaired = repair_pdf_kerning_splits(broken)
        self.assertIn("JavaScript variable is simply a name of storage location", repaired)
        self.assertIn("value1", repaired)

        clean_code = "var x = 10; There are two types in JavaScript."
        self.assertEqual(repair_pdf_kerning_splits(clean_code), clean_code)

    def test_15_quality_gate_headers_causal_uniqueness_and_page_traceability(self):
        from backend.ai_engine import _is_non_educational_narration_line

        self.assertTrue(_is_non_educational_narration_line("JavaScript Topperworld Topperworld."))
        self.assertTrue(_is_non_educational_narration_line("Variables & DataTypes."))
        self.assertFalse(_is_non_educational_narration_line("A JavaScript variable is simply a name of storage location."))

        bad_conn = [
            {"speaker": "Alex", "role": "Lead Host", "text": "How do these connect?"},
            {"speaker": "Maya", "role": "Subject Expert", "text": "Inflation and Interest Rates connect directly."},
            {"speaker": "Alex", "role": "Lead Host", "text": "To sum up, that covers the core ideas."},
        ]
        self.assertFalse(validate_audio_dialogue(bad_conn)["passed"])


if __name__ == "__main__":
    unittest.main()

