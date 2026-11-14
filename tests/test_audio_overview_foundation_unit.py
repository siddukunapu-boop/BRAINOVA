"""
Comprehensive unit & integration tests for BRAINOVA Audio Overview Foundation (Phases 1-4):
- Sentence-level vs Chunk-level quality validation
- Topic-aware retrieval & multi-section coherence
- LLM-powered source-grounded Audio Overview generation & structured error handling
- Six-language validation (English, Telugu, Hindi, Tamil, Kannada, Marathi)
- Exact transcript-to-TTS parity & explicit non-English TTS unavailability reporting
"""

import sqlite3
import unittest
from unittest.mock import patch

from backend.ai_engine import (
    AudioGenerationError,
    InsufficientSourceEvidenceError,
    _extract_source_facts,
    generateAudioScript,
)
from backend.doc_processor import (
    is_complete_source_sentence,
    is_plausible_source_chunk,
    retrieve_relevant_chunks,
)
from backend.multilang_engine import (
    SUPPORTED_LANGUAGES,
    validate_script_language,
    validate_supported_language,
)
from backend.tts_engine import synthesize_podcast_audio


def _make_memory_retrieval_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE sources (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE source_chunks (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            page_number INTEGER NOT NULL,
            section_title TEXT NOT NULL,
            content TEXT NOT NULL
        );
        """
    )
    return conn


class AudioOverviewFoundationTests(unittest.TestCase):
    def test_01_chunk_vs_sentence_quality_validation(self):
        # Valid long paragraph containing a dense formula + normal prose must pass chunk validation
        long_para = (
            "Thermodynamics describes energy transfer across physical systems. "
            "The Gibbs free energy equation is ΔG = ΔH - TΔS (kJ/mol). "
            "Spontaneous reactions occur when the change in free energy is negative under constant pressure."
        )
        self.assertTrue(is_plausible_source_chunk(long_para))

        # Binary JBIG2 garbage chunk must fail chunk validation
        corrupted_chunk = "^G-\u0376\u020e$K.1#OLhi}\\;KQg?3\u052ffK\u05b0lg_\u02baTv IU/YP\"Erh8\u0693Eo>v[:\u036b'h;/min 7[."
        self.assertFalse(is_plausible_source_chunk(corrupted_chunk))

        # Incomplete/caption/broken fragments must fail sentence-level completeness
        self.assertFalse(is_complete_source_sentence("Russian and German Soldiers as friends, 1917."))
        self.assertFalse(is_complete_source_sentence('historian David Thomson "....the Paris Conference must stand in history.'))
        self.assertFalse(is_complete_source_sentence("15.2.3 Decline of the trend led to the gradual decline of this"))
        self.assertTrue(
            is_complete_source_sentence(
                "World War I began in July 1914 following the assassination of Archduke Franz Ferdinand."
            )
        )

    def test_02_topic_aware_retrieval_excludes_unrelated_units_and_substring_noise(self):
        conn = _make_memory_retrieval_db()
        conn.execute(
            "INSERT INTO sources VALUES ('src_1', 'u1', 'world war 1 pdf', 'ww1.pdf', 'ready', '2026-01-01')"
        )
        chunks = [
            # Unit 12 Marxist (unrelated)
            (0, 1, "UNIT 12 MARXIST THOUGHT", "Karl Marx wrote extensively about industrial capitalism and class struggle in Europe."),
            # Corrupted JBIG2 chunk (must be filtered out)
            (1, 2, "跒AF\\sGAVp\"tkM", "^G-\u0376\u020e$K.1#OLhi}\\;KQg?3\u052ffK\u05b0lg_\u02baTv IU/YP\"Erh8\u0693Eo"),
            # Unit 14 World War 1 (target!)
            (2, 10, "UNIT 14 WORLD WAR 1", "World War 1 erupted in 1914 due to entangling alliances, militarism, and imperial rivalries."),
            (3, 11, "UNIT 14 WORLD WAR 1", "Trench warfare defined the Western Front during World War 1 from 1914 until the 1918 armistice."),
            # Unit 15 Gandhi + substring trap "towards" / "forward" (unrelated!)
            (4, 30, "UNIT 15 INDIAN NATIONAL MOVEMENT", "Mahatma Gandhi marched forward towards non-violent Satyagraha and industrial self-reliance."),
        ]
        for idx, page, sec, content in chunks:
            conn.execute(
                "INSERT INTO source_chunks VALUES (?, 'src_1', 'u1', ?, ?, ?, ?)",
                (f"ch_{idx}", idx, page, sec, content),
            )

        selected = retrieve_relevant_chunks(conn, "u1", ["src_1"], "World War 1", top_k=2)
        self.assertEqual(len(selected), 2)
        joined = " ".join(c["content"] for c in selected)
        self.assertIn("entangling alliances", joined)
        self.assertIn("Trench warfare", joined)
        self.assertNotIn("Gandhi", joined)
        self.assertNotIn("OLhi", joined)

    def test_03_multi_section_coherence_preserves_multiple_relevant_sections(self):
        conn = _make_memory_retrieval_db()
        conn.execute(
            "INSERT INTO sources VALUES ('src_1', 'u1', 'Modern History', 'hist.pdf', 'ready', '2026-01-01')"
        )
        chunks = [
            (0, 10, "UNIT 14 WORLD WAR 1", "World War 1 began in 1914 and reshaped European empires."),
            (1, 20, "UNIT 15 PARIS PEACE CONFERENCE", "The Paris Peace Conference of 1919 drafted the Treaty of Versailles after World War 1."),
            (2, 40, "UNIT 18 INDUSTRIALISATION", "Early industrialisation created large urban factory concentrations."),
        ]
        for idx, page, sec, content in chunks:
            conn.execute(
                "INSERT INTO source_chunks VALUES (?, 'src_1', 'u1', ?, ?, ?, ?)",
                (f"ch_{idx}", idx, page, sec, content),
            )

        selected = retrieve_relevant_chunks(
            conn, "u1", ["src_1"], "World War 1 and Paris Peace Conference", top_k=2
        )
        secs = {c["section_title"] for c in selected}
        self.assertEqual(secs, {"UNIT 14 WORLD WAR 1", "UNIT 15 PARIS PEACE CONFERENCE"})

    def test_04_corrupted_section_title_never_leaks_and_insufficient_evidence_fails_cleanly(self):
        chunks = [
            {
                "source_id": "src_x",
                "source_title": "History Notes",
                "page_number": 4,
                "section_title": "跒AF\\sGAVp\"tkM_[%ԕX'2Mg:θs`&[,Y4SȀO/ۨ",
                "content": "The Treaty of Versailles formally ended World War 1 in 1919.",
            }
        ]
        _, facts, refs = _extract_source_facts(chunks, "World War 1")
        self.assertNotIn("tkM_", " ".join(facts))
        self.assertNotIn("tkM_", refs[0]["section_title"])

        # All-corrupted chunks must raise InsufficientSourceEvidenceError
        bad_chunks = [
            {
                "source_id": "src_bad",
                "source_title": "Bad PDF",
                "page_number": 1,
                "section_title": "Bad",
                "content": "^G-\u0376\u020e$K.1#OLhi}\\;KQg?3\u052ffK\u05b0lg_\u02baTv IU/YP\"Erh8\u0693Eo>v[:\u036b'h;/min 7[.",
            }
        ]
        with self.assertRaises(InsufficientSourceEvidenceError):
            generateAudioScript(bad_chunks, {"topic": "World War 1", "language": "English"})

    def test_05_unsupported_language_raises_instead_of_silent_english_fallback(self):
        with self.assertRaises(ValueError) as ctx:
            validate_supported_language("French")
        self.assertIn("Unsupported language", str(ctx.exception))

        with self.assertRaises(ValueError):
            generateAudioScript([], {"topic": "World War 1", "language": "Spanish"})

    def test_06_all_six_languages_script_validation_with_technical_terms(self):
        samples = {
            "English": "In 1914, World War I reshaped European alliances and global geopolitics.",
            "Telugu": "1914లో World War I యూరోపియన్ కూటములు మరియు అంతర్జాతీయ రాజకీయాలను మార్చివేసింది.",
            "Hindi": "1914 में World War I ने यूरोपीय गठबंधनों और वैश्विक राजनीति को बदल दिया।",
            "Tamil": "1914 இல் World War I ஐரோப்பிய கூட்டணிகளையும் உலக அரசியலையும் மாற்றியது.",
            "Kannada": "1914 ರಲ್ಲಿ World War I ಯುರೋಪಿಯನ್ ಮೈತ್ರಿಗಳು ಮತ್ತು ಜಾಗತಿಕ ರಾಜಕೀಯವನ್ನು ಬದಲಾಯಿಸಿತು.",
            "Marathi": "1914 मध्ये World War I ने युरोपीय आघाड्या आणि जागतिक राजकारण बदलले.",
        }
        for lang in SUPPORTED_LANGUAGES:
            ok, reason = validate_script_language(samples[lang], lang)
            self.assertTrue(ok, f"{lang} failed: {reason}")

        # Cross-script mismatch must be rejected
        ok_mismatch, _ = validate_script_language(samples["Hindi"], "Telugu")
        self.assertFalse(ok_mismatch)

    def test_07_llm_audio_overview_preserves_native_script_and_fails_on_llm_error(self):
        chunks = [
            {
                "source_id": "src_ww1",
                "source_title": "World War 1",
                "page_number": 1,
                "section_title": "Causes",
                "content": "World War I began in 1914 after the assassination of Archduke Franz Ferdinand in Sarajevo.",
            }
        ]
        prefs_with_key = {"gemini_api_key": "fake-test-key"}
        telugu_llm_response = {
            "title": "మొదటి ప్రపంచ యుద్ధం: కారణాలు మరియు ప్రభావాలు",
            "summary": "1914లో ప్రారంభమైన World War I యొక్క ప్రధాన కారణాలను ఈ పాడ్‌కాస్ట్ వివరిస్తుంది.",
            "dialogue": [
                {"speaker": "Alex", "role": "Lead Host", "text": "నమస్కారం! ఈరోజు మనం 1914లో ప్రారంభమైన World War I గురించి చర్చిద్దాం."},
                {"speaker": "Maya", "role": "Subject Expert", "text": "అవును Alex, Sarajevo లో Archduke Franz Ferdinand హత్య తర్వాత ఈ యుద్ధం ప్రారంభమైంది."},
                {"speaker": "Alex", "role": "Lead Host", "text": "ఐరోపాలోని సైనిక కూటములు దీన్ని ప్రపంచ యుద్ధంగా ఎలా మార్చాయి?"},
                {"speaker": "Maya", "role": "Subject Expert", "text": "పరస్పర రక్షణ ఒప్పందాలు అనేక దేశాలను ఒకేసారి యుద్ధంలోకి లాగాయి."},
            ],
            "key_takeaways": ["1914లో World War I ప్రారంభం", "Sarajevo సంఘటన మరియు కూటములు"],
        }

        with patch("backend.ai_engine.call_llm_json", return_value=(telugu_llm_response, "gemini:test")):
            out = generateAudioScript(chunks, {"topic": "World War 1", "language": "Telugu"}, user_prefs=prefs_with_key)

        self.assertTrue(out["llm_grounded"])
        self.assertEqual(out["language"], "Telugu")
        self.assertIn("Sarajevo", out["dialogue"][1]["text"])
        # Exact transcript-to-TTS parity
        for turn in out["dialogue"]:
            self.assertEqual(turn["spoken_text"], turn["text"])

        # If configured LLM fails (returns None), must raise AudioGenerationError instead of fabricating
        with patch("backend.ai_engine.call_llm_json", return_value=(None, "local_structured_engine")):
            with self.assertRaises(AudioGenerationError) as err_ctx:
                generateAudioScript(chunks, {"topic": "World War 1", "language": "English"}, user_prefs=prefs_with_key)
            self.assertEqual(err_ctx.exception.code, "llm_generation_failed")

    def test_08_tts_never_silently_falls_back_to_english_for_indic_languages(self):
        dialogue = [
            {"speaker": "Alex", "text": "నమస్కారం! ఈరోజు మనం World War I గురించి తెలుసుకుందాం."}
        ]
        # Force SAPI check to report no native te-IN voice (returncode 42)
        with patch("backend.tts_engine.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 42
            meta = synthesize_podcast_audio(
                "test_te_nosapi",
                dialogue,
                openai_api_key="",
                language="Telugu",
                require_native_voice=True,
            )
        self.assertEqual(meta["status"], "unsupported_tts_language")
        self.assertFalse(meta["voice_supported"])
        self.assertEqual(meta["audio_url"], "")
        self.assertEqual(meta["file_path"], "")
        self.assertIn("Telugu", meta["error"])

    def test_09_indic_languages_without_llm_raise_structured_422(self):
        chunks = [
            {
                "source_id": "src_ww1",
                "source_title": "World War 1",
                "page_number": 1,
                "section_title": "Causes",
                "content": "World War I began in 1914 after the assassination of Archduke Franz Ferdinand in Sarajevo.",
            }
        ]
        indic_languages = ["Telugu", "Hindi", "Tamil", "Kannada", "Marathi"]
        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            for lang in indic_languages:
                with self.assertRaises(AudioGenerationError) as err_ctx:
                    generateAudioScript(
                        chunks,
                        {"topic": "World War 1", "language": lang},
                        user_prefs={},
                    )
                self.assertEqual(err_ctx.exception.code, "llm_required_for_language")
                self.assertEqual(err_ctx.exception.status_code, 422)
                msg = str(err_ctx.exception)
                self.assertIn(lang, msg)
                self.assertIn("Settings", msg)

    def test_10_english_offline_generation_preserved_and_source_grounded(self):
        chunks = [
            {
                "source_id": "src_ww1",
                "source_title": "World War 1",
                "page_number": 1,
                "section_title": "Causes",
                "content": (
                    "World War I began in 1914 after the assassination of Archduke Franz Ferdinand in Sarajevo. "
                    "European alliance systems turned the regional crisis into a global conflict."
                ),
            }
        ]
        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            out = generateAudioScript(
                chunks,
                {"topic": "World War 1", "language": "English"},
                user_prefs={},
            )
        self.assertEqual(out["language"], "English")
        self.assertFalse(out["llm_grounded"])
        joined = " ".join(t["text"] for t in out["dialogue"])
        self.assertIn("1914", joined)
        self.assertNotIn("scalability", joined.lower())
        for turn in out["dialogue"]:
            self.assertEqual(turn["spoken_text"], turn["text"])

    def test_11_localize_audio_overview_never_overwrites_or_wraps_turns(self):
        from backend.multilang_engine import localize_studio_output

        original_turns = [
            {"speaker": "Alex", "role": "Lead Host", "text": f"Turn {i}: World War I event {i}."}
            for i in range(7)
        ]
        payload = {
            "title": "World War I Overview",
            "summary": "Summary of World War I.",
            "dialogue": [dict(t) for t in original_turns],
            "llm_grounded": False,
        }
        localized = localize_studio_output("audio_overview", payload, "Telugu", topic_hint="World War 1")
        self.assertEqual(len(localized["dialogue"]), 7)
        for idx, turn in enumerate(localized["dialogue"]):
            self.assertEqual(turn["text"], original_turns[idx]["text"])
            self.assertEqual(turn["spoken_text"], original_turns[idx]["text"])
        joined = " ".join(t["text"] for t in localized["dialogue"]).lower()
        self.assertNotIn("engineers", joined)
        self.assertNotIn("scalability", joined)

    def test_12_provider_backed_generation_preserves_all_six_languages(self):
        chunks = [
            {
                "source_id": "src_ww1",
                "source_title": "World War 1",
                "page_number": 1,
                "section_title": "Causes",
                "content": "World War I began in 1914 after the assassination of Archduke Franz Ferdinand in Sarajevo.",
            }
        ]
        native_samples = {
            "English": (
                "World War I began in 1914 in Sarajevo.",
                "Alliances escalated the conflict across Europe.",
                "Trench warfare defined the Western Front.",
                "The armistice ended fighting in November 1918.",
            ),
            "Telugu": (
                "నమస్కారం! 1914లో Sarajevo సంఘటనతో World War I ప్రారంభమైంది.",
                "ఐరోపా కూటములు ఈ యుద్ధాన్ని ప్రపంచవ్యాప్తం చేశాయి.",
                "పశ్చిమ సరిహద్దులో ట్రెంచ్ యుద్ధం ప్రధానంగా జరిగింది.",
                "1918 నవంబర్‌లో యుద్ధ విరమణ ఒప్పందంతో పోరాటం ముగిసింది.",
            ),
            "Hindi": (
                "नमस्ते! 1914 में Sarajevo की घटना के बाद World War I शुरू हुआ।",
                "यूरोपीय गठबंधनों ने इसे विश्व युद्ध में बदल दिया।",
                "पश्चिमी मोर्चे पर खाइयों की लड़ाई प्रमुख रही।",
                "नवंबर 1918 के युद्धविराम के साथ यह संघर्ष समाप्त हुआ।",
            ),
            "Tamil": (
                "வணக்கம்! 1914 இல் Sarajevo சம்பவத்திற்குப் பிறகு World War I தொடங்கியது.",
                "ஐரோப்பிய கூட்டணிகள் போரை உலகளாவியதாக்கின.",
                "மேற்கு முனையில் அகழிப் போர் முக்கிய பங்கு வகித்தது.",
                "1918 நவம்பர் போர் நிறுத்தத்துடன் மோதல் முடிவுக்கு வந்தது.",
            ),
            "Kannada": (
                "ನಮಸ್ಕಾರ! 1914 ರಲ್ಲಿ Sarajevo ಘಟನೆಯ ನಂತರ World War I ಪ್ರಾರಂಭವಾಯಿತು.",
                "ಯುರೋಪಿಯನ್ ಮೈತ್ರಿಗಳು ಯುದ್ಧವನ್ನು ವಿಸ್ತರಿಸಿದವು.",
                "ಪಶ್ಚಿಮ ರಂಗದಲ್ಲಿ ಕಂದಕ ಯುದ್ಧವು ಪ್ರಮುಖವಾಗಿತ್ತು.",
                "ನವೆಂಬರ್ 1918 ರ ಕದನ ವಿರಾಮದೊಂದಿಗೆ ಯುದ್ಧ ಕೊನೆಗೊಂಡಿತು.",
            ),
            "Marathi": (
                "नमस्कार! 1914 मध्ये Sarajevo घटनेनंतर World War I सुरू झाले.",
                "युरोपीय युतीमुळे हे जागतिक युद्ध बनले.",
                "पश्चिम आघाडीवर खंदकातील युद्ध महत्त्वाचे ठरले.",
                "नोव्हेंबर 1918 च्या युद्धविरामाने संघर्ष संपला.",
            ),
        }
        prefs_with_key = {"gemini_api_key": "fake-test-key"}
        for lang, (t1, t2, t3, t4) in native_samples.items():
            mock_resp = {
                "title": f"World War I ({lang})",
                "summary": f"{t1} {t2}",
                "dialogue": [
                    {"speaker": "Alex", "role": "Lead Host", "text": t1},
                    {"speaker": "Maya", "role": "Subject Expert", "text": t2},
                    {"speaker": "Alex", "role": "Lead Host", "text": t3},
                    {"speaker": "Maya", "role": "Subject Expert", "text": t4},
                ],
                "key_takeaways": [t1, t2],
            }
            with patch("backend.ai_engine.call_llm_json", return_value=(mock_resp, "gemini:test")):
                out = generateAudioScript(chunks, {"topic": "World War 1", "language": lang}, user_prefs=prefs_with_key)
            self.assertEqual(out["language"], lang)
            self.assertTrue(out["llm_grounded"])
            self.assertEqual(len(out["dialogue"]), 4)
            self.assertEqual(out["dialogue"][0]["text"], t1)
            self.assertEqual(out["dialogue"][1]["text"], t2)
            self.assertEqual(out["dialogue"][2]["text"], t3)
            self.assertEqual(out["dialogue"][3]["text"], t4)

    def test_13_ocr_cleanup_conservative_and_preserves_ambiguous_terms(self):
        from backend.doc_processor import clean_source_sentence_for_narration

        self.assertEqual(
            clean_source_sentence_for_narration("The pre-war German and Austrian domiriance came to an end."),
            "The pre-war German and Austrian dominance came to an end.",
        )
        self.assertEqual(
            clean_source_sentence_for_narration("The govemment enacted rnilitary reforms."),
            "The government enacted military reforms.",
        )
        # Ambiguous/unfamiliar proper names or technical terms containing 'ri' or 'rn' must NEVER be altered
        preserved = "Bernoulli studied barometric pressure in Sardinia and ornithology near Sarajevo."
        self.assertEqual(clean_source_sentence_for_narration(preserved), preserved)

    def test_14_topic_section_hygiene_and_multipage_citations(self):
        chunks = [
            {
                "source_id": "src_ww1",
                "source_title": "world war 1 pdf",
                "page_number": 42,
                "section_title": "Causes and Outbreak",
                "content": (
                    "Archduke Franz Ferdinand was assassinated in Sarajevo in June 1914. "
                    "Mutual defense alliances pulled major European powers into war."
                ),
            },
            {
                "source_id": "src_ww1",
                "source_title": "world war 1 pdf",
                "page_number": 43,
                "section_title": "the world. As a consequence of this war, there was a military and political coll",
                "content": (
                    "The pre-war German and Austrian domiriance, for a time, came to an end. "
                    "The supreme task before the peacemakers was to see that Germany is kept in check and weakened militarily. "
                    "To weaken Germany several measures were taken. "
                    "German forces were asked to evacuate all the occupied territories."
                ),
            },
        ]
        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            out = generateAudioScript(chunks, {"language": "English"}, user_prefs={})

        joined = " ".join(t["text"] for t in out["dialogue"])
        # Spoken topic hygiene & OCR cleanup
        self.assertNotIn("world war 1 pdf", joined.lower())
        self.assertIn("World War 1", joined)
        self.assertNotIn("domiriance", joined)
        self.assertIn("dominance", joined)
        # No mid-sentence capitalization error or old generic filler
        self.assertNotIn("Furthermore, To weaken", joined)
        self.assertNotIn("How does the source develop this idea further?", joined)
        self.assertNotIn("check your understanding in BRAINOVA", joined)

        # Multi-page citations preserved & truncated lowercase section title rejected
        pages_in_refs = [r["page_number"] for r in out["source_references"]]
        self.assertEqual(pages_in_refs, [42, 43])
        self.assertEqual(out["source_references"][1]["section_title"], "Page 43")
        # Turn 1 cites page 42 claims only; later turns cite page 43 claims accurately
        self.assertIn("page 42", out["dialogue"][1]["text"].lower())
        self.assertNotIn("page 43", out["dialogue"][1]["text"].lower())

    def test_15_general_purpose_subjects_and_shorter_accurate_overview(self):
        bio_chunks = [
            {
                "source_id": "src_bio",
                "source_title": "cellular_respiration_notes.pdf",
                "page_number": 12,
                "section_title": "Glycolysis and Citric Acid Cycle",
                "content": (
                    "Cellular respiration converts glucose into usable chemical energy in the form of ATP. "
                    "Glycolysis takes place in the cytoplasm and breaks one glucose molecule into two pyruvate molecules."
                ),
            },
            {
                "source_id": "src_bio",
                "source_title": "cellular_respiration_notes.pdf",
                "page_number": 14,
                "section_title": "Oxidative Phosphorylation",
                "content": (
                    "Inside the mitochondria, the electron transport chain drives oxidative phosphorylation. "
                    "Oxygen serves as the final electron acceptor and enables high ATP yield."
                ),
            },
        ]
        cs_chunks = [
            {
                "source_id": "src_os",
                "source_title": "operating_systems_scheduling.pdf",
                "page_number": 7,
                "section_title": "CPU Scheduling",
                "content": (
                    "The operating system scheduler selects which ready process runs next on the CPU. "
                    "Round-robin scheduling assigns each process a fixed time quantum to guarantee fairness."
                ),
            },
            {
                "source_id": "src_os",
                "source_title": "operating_systems_scheduling.pdf",
                "page_number": 8,
                "section_title": "Priority and Starvation",
                "content": (
                    "Priority scheduling executes higher-priority tasks first but can cause starvation for low-priority jobs. "
                    "Aging gradually increases the priority of waiting processes to prevent indefinite postponement."
                ),
            },
        ]
        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            bio_out = generateAudioScript(bio_chunks, {"language": "English"}, user_prefs={})
            cs_out = generateAudioScript(cs_chunks, {"language": "English"}, user_prefs={})

        bio_joined = " ".join(t["text"] for t in bio_out["dialogue"])
        self.assertIn("ATP", bio_joined)
        self.assertIn("mitochondria", bio_joined)
        self.assertIn("page 12", bio_joined.lower())
        self.assertIn("page 14", bio_joined.lower())
        self.assertNotIn("Germany", bio_joined)

        cs_joined = " ".join(t["text"] for t in cs_out["dialogue"])
        self.assertIn("scheduler", cs_joined.lower())
        self.assertIn("starvation", cs_joined.lower())
        self.assertIn("page 7", cs_joined.lower())
        self.assertIn("page 8", cs_joined.lower())

        # Shorter accurate overview when only 2 facts exist (no fabricated padding)
        short_chunks = [bio_chunks[0]]
        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            short_out = generateAudioScript(short_chunks, {"language": "English"}, user_prefs={})
        self.assertEqual(len(short_out["dialogue"]), 3)
        self.assertNotIn("Key concept from", " ".join(t["text"] for t in short_out["dialogue"]))

        # Insufficient evidence raises InsufficientSourceEvidenceError
        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            with self.assertRaises(InsufficientSourceEvidenceError):
                generateAudioScript([], {"topic": "Empty", "language": "English"}, user_prefs={})

    def test_16_cluster_focus_no_morphological_duplicates_and_list_semicolon_cleanup(self):
        from backend.ai_engine import _extract_cluster_focus
        from backend.doc_processor import clean_source_sentence_for_narration

        # 1. Stray semicolon inside a comma-separated list is normalized, while prose semicolons are preserved
        self.assertEqual(
            clean_source_sentence_for_narration(
                "Collapse of the old Russian, Austro-Hungarian; German and Turkish empires occurred."
            ),
            "Collapse of the old Russian, Austro-Hungarian, German and Turkish empires occurred.",
        )
        prose = "The experiment succeeded; however, further trials are needed."
        self.assertEqual(clean_source_sentence_for_narration(prose), prose)

        # 2. _extract_cluster_focus avoids morphological duplicates ("Germany and German")
        focus_dup = _extract_cluster_focus(
            [
                {"text": "To weaken Germany several measures were taken."},
                {"text": "German forces were asked to evacuate all occupied territories."},
            ],
            "World War 1",
        )
        self.assertNotIn("Germany and German", focus_dup)
        self.assertNotEqual(focus_dup.lower(), "german and germany")

        # 3. _extract_cluster_focus avoids incomplete adjectival pair ("Russian and Austro-Hungarian")
        focus_adj = _extract_cluster_focus(
            [
                {"text": "There was a military collapse of the old Russian, Austro-Hungarian, German and Turkish empires."},
            ],
            "World War 1",
        )
        self.assertNotEqual(focus_adj, "Russian and Austro-Hungarian")
        self.assertIn("empires", focus_adj.lower())

    def test_17_pdf_tj_kerning_and_artifact_exclusion(self):
        from backend.doc_processor import extract_text_from_pdf_bytes

        stream_content = (
            b"BT\n"
            b"/Artifact <</Subtype /Header /Type /Pagination>>BDC\n"
            b"[(H)-5 (e)-2 (ader) -250 (P)-3 (age) -250 (1)]TJ\n"
            b"EMC\n"
            b"/Artifact <</Subtype /Footer /Type /Pagination>>BDC\n"
            b"[(P)-7 (r)-1 (o)-1 (v)-8 (i)-5 (de)-6 (d by)]TJ ( )Tj [(C)3 (e)-1 (ll)]TJ\n"
            b"EMC\n"
            b"/Artifact <</Subtype /Watermark /Type /Pagination>>BDC\n"
            b"(CONFIDENTIAL)Tj\n"
            b"EMC\n"
            b"0 -20 TD\n"
            b"[(G)-2 (ly)-4 (co)-3 (ly)-2 (sis) -250 (c)-2 (on)-1 (v)-3 (er)-1 (ts) -250 (gl)-2 (u)-1 (co)-2 (se) -250 (in)-2 (to) -250 (py)-2 (ru)-1 (va)-2 (te.)]TJ\n"
            b"0 -14 TD\n"
            b"[(T)-3 (hi)-2 (s) -250 (pr)-1 (oc)-2 (es)-1 (s) -250 (pr)-1 (od)-2 (uc)-1 (es) -250 (A)-1 (T)-1 (P.)]TJ\n"
            b"ET"
        )
        pdf_bytes = (
            b"%PDF-1.4\n1 0 obj\n<< /Length "
            + str(len(stream_content)).encode("ascii")
            + b" >>\nstream\n"
            + stream_content
            + b"\nendstream\nendobj\n%%EOF"
        )
        pages, err = extract_text_from_pdf_bytes(pdf_bytes)
        self.assertIsNone(err)
        self.assertTrue(pages)
        joined = " ".join(pages)
        self.assertIn("Glycolysis converts glucose into pyruvate.", joined)
        self.assertIn("This process produces ATP.", joined)
        self.assertNotIn("Provided", joined)
        self.assertNotIn("CONFIDENTIAL", joined)
        self.assertNotIn("Header Page 1", joined)
        self.assertNotIn("G ly", joined)

    def test_18_incomplete_sentence_and_spaced_ocr_rejection(self):
        from backend.doc_processor import is_complete_source_sentence

        self.assertFalse(is_complete_source_sentence("In cellular respiration, glucose and i"))
        self.assertFalse(is_complete_source_sentence("In cellular respiration, glucose and its intermediates are always oxidiz e"))
        self.assertFalse(is_complete_source_sentence("P r o v i de d by C e ll R e sp ir a t io n."))
        self.assertTrue(is_complete_source_sentence("Glycolysis breaks one glucose molecule into two pyruvate molecules and ATP."))
        self.assertTrue(is_complete_source_sentence("NADH carries high-energy electrons to the electron transport chain."))

    def test_19_overlap_dedup_handout_exclusion_and_biology_e2e(self):
        from backend.doc_processor import chunk_document_sections, extract_text_from_pdf_bytes

        stream_content = (
            b"BT\n"
            b"/Artifact <</Subtype /Footer /Type /Pagination>>BDC\n"
            b"[(P)-7 (r)-1 (o)-1 (v)-8 (i)-5 (de)-6 (d by) -250 (The Academic Center 2024)]TJ\n"
            b"EMC\n"
            b"0 -20 TD\n"
            b"[(C)-2 (el)-1 (lu)-2 (la)-1 (r) -250 (R)-2 (es)-1 (pi)-2 (ra)-1 (ti)-2 (on)]TJ\n"
            b"0 -14 TD\n"
            b"[(O)-2 (x)-1 (id)-2 (at)-1 (io)-2 (n) -250 (an)-1 (d) -250 (re)-1 (du)-2 (ct)-1 (io)-2 (n) -250 (re)-1 (ac)-2 (ti)-1 (on)-2 (s) -250 (ar)-1 (e) -250 (co)-1 (up)-2 (le)-1 (d) -250 (in) -250 (ce)-1 (ll)-2 (ul)-1 (ar) -250 (re)-1 (sp)-2 (ir)-1 (at)-2 (io)-1 (n.)]TJ\n"
            b"0 -14 TD\n"
            b"[(A) -250 (go)-1 (od) -250 (wa)-1 (y) -250 (to) -250 (re)-1 (me)-2 (mb)-1 (er) -250 (th)-1 (is) -250 (is) -250 (th)-1 (e) -250 (ac)-1 (ro)-2 (ny)-1 (m) -250 (\"OIL RIG\".)]TJ\n"
            b"0 -14 TD\n"
            b"[(T)-2 (he) -250 (en)-1 (er)-2 (gy) -250 (wi)-1 (th)-2 (in) -250 (gl)-1 (uc)-2 (os)-1 (e) -250 (is) -250 (co)-1 (nv)-2 (er)-1 (te)-2 (d) -250 (to) -250 (AT)-1 (P.)]TJ\n"
            b"0 -14 TD\n"
            b"[(F)-2 (or) -250 (fu)-1 (rt)-2 (he)-1 (r) -250 (in)-1 (fo)-2 (rm)-1 (at)-2 (io)-1 (n,) -250 (pl)-1 (ea)-2 (se) -250 (re)-1 (fe)-2 (r) -250 (to) -250 (th)-1 (e) -250 (Oxidation) -250 (ha)-1 (nd)-2 (ou)-1 (t.)]TJ\n"
            b"0 -14 TD\n"
            b"[(G)-2 (ly)-4 (co)-3 (ly)-2 (sis) -250 (br)-1 (ea)-2 (ks) -250 (gl)-1 (uc)-2 (os)-1 (e) -250 (in)-1 (to) -250 (tw)-1 (o) -250 (py)-2 (ru)-1 (va)-2 (te) -250 (mo)-1 (le)-2 (cu)-1 (le)-2 (s.)]TJ\n"
            b"ET"
        )
        pdf_bytes = (
            b"%PDF-1.4\n1 0 obj\n<< /Length "
            + str(len(stream_content)).encode("ascii")
            + b" >>\nstream\n"
            + stream_content
            + b"\nendstream\nendobj\n%%EOF"
        )
        pages, err = extract_text_from_pdf_bytes(pdf_bytes)
        self.assertIsNone(err)
        chunks = [
            {
                "source_id": "src_bio_e2e",
                "source_title": "biology pdf",
                "page_number": c["page_number"],
                "section_title": c["section_title"],
                "content": c["content"],
            }
            for c in chunk_document_sections(
                [(idx + 1, "Cellular Respiration", p) for idx, p in enumerate(pages)]
            )
        ]
        # Add an overlapping partial-prefix chunk to verify deduplication
        chunks.append(
            {
                "source_id": "src_bio_e2e",
                "source_title": "biology pdf",
                "page_number": 1,
                "section_title": "Cellular Respiration",
                "content": "The energy within glucose is converted to ATP. Glycolysis breaks glucose into two",
            }
        )
        with patch("backend.ai_engine._resolve_active_provider", return_value=("none", "", "")):
            out = generateAudioScript(chunks, {"language": "English"}, user_prefs={})

        joined = " ".join(t["text"] for t in out["dialogue"])
        self.assertNotIn("Provided by", joined)
        self.assertNotIn("handout", joined.lower())
        self.assertNotIn("focusing on OIL ", joined)
        self.assertIn("ATP", joined)
        self.assertIn("Glycolysis", joined)
        self.assertIn("pyruvate", joined.lower())
        # Verify overlapping sentence wasn't repeated twice
        self.assertEqual(joined.lower().count("energy within glucose is converted to atp"), 1)
        # Topic should resolve away from generic "Biology"
        self.assertNotEqual(out["title"], "Audio Overview: Biology")

    def test_20_non_educational_filtering_tables_visual_pointers_and_kerning(self):
        from backend.ai_engine import _extract_fact_items

        chunks = [
            {
                "source_id": "src_filter",
                "source_title": "biology pdf",
                "page_number": 2,
                "section_title": "Page 2",
                "content": (
                    "The flow chart below shows the full anaerobic cellular respiration process. "
                    "The Academic Center for Excellence (ACE) offers free on-campus and online tutoring appointments for biology. "
                    "For further assistance, please call ACE at (540) 891-3017 or email us at ACE@germanna.edu. "
                    "In the diagram below, a simplified form of the cellular respiration process can be seen with each of the steps involved. "
                    "The chart below shows a summary of how much of each molecule is being produced during each stage. "
                    "Pathway ATP Produced NADH Produced FADH 2 Produced Glycolysis 4 2 0 Pyruvate Oxidation 0 2 0 Krebs Cycle 2 6 2 30 32 0 0 Total 36 38 10 2 Fermentation. "
                    "The diagram below depicts the electron transport chain, which includes the process of chemiosmosis. "
                    "In the diagram below, the electron transport chain drives chemiosmosis to produce ATP. "
                    "The other form of fermentation is lactic acid fermentation, which is similar to ethanol f ermentation in that pyruvate is oxidized again."
                ),
            }
        ]
        _, items, refs = _extract_fact_items(chunks, "Biology")
        texts = [it["text"] for it in items]
        joined = " ".join(texts)

        # Excluded items
        self.assertNotIn("Academic Center", joined)
        self.assertNotIn("891-3017", joined)
        self.assertNotIn("ACE@germanna.edu", joined)
        self.assertNotIn("flow chart below", joined.lower())
        self.assertNotIn("simplified form", joined.lower())
        self.assertNotIn("chart below shows a summary", joined.lower())
        self.assertNotIn("which includes the process of chemiosmosis", joined)
        self.assertNotIn("Total 36 38", joined)

        # Preserved explanatory science sentences & kerning fix
        self.assertTrue(any("drives chemiosmosis to produce ATP" in t for t in texts))
        self.assertTrue(any("ethanol fermentation" in t for t in texts))
        self.assertNotIn("f ermentation", joined)
        self.assertEqual(refs[0]["page_number"], 2)

    def test_21_diagram_label_fragments_kerning_and_inline_heading_cleanup(self):
        from backend.ai_engine import _extract_fact_items

        chunks = [
            {
                "source_id": "src_bio_clean",
                "source_title": "biology pdf",
                "page_number": 1,
                "section_title": "Page 1",
                "content": (
                    "2 x ATP 2 x FADH 2 6 x NADH + H intermembrane space. "
                    "2 molecules of pyruvate are produced when one glucose molecule undergoes glycolysis. "
                    "The oxygen later react s with H + to form water. "
                    "A good way to remember this is O xidation I s L osing, R eduction I s G aining. "
                    "Oxidation and Reduction Before viewing the individual steps of cellular respiration, it is important to understand redox."
                ),
            }
        ]
        _, items, _ = _extract_fact_items(chunks, "Biology")
        texts = [it["text"] for it in items]
        joined = " ".join(texts)

        # Incomplete diagram label fragment excluded; valid numbered sentence retained
        self.assertNotIn("intermembrane space", joined)
        self.assertTrue(any("2 molecules of pyruvate are produced" in t for t in texts))

        # Verified kerning fixes applied
        self.assertIn("reacts with", joined)
        self.assertNotIn("react s", joined)
        self.assertIn("Oxidation Is Losing, Reduction Is Gaining.", joined)

        # Inline heading separated from explanatory sentence
        self.assertTrue(any(t.startswith("Before viewing the individual steps") for t in texts))
        self.assertFalse(any(t.startswith("Oxidation and Reduction Before") for t in texts))


if __name__ == "__main__":
    unittest.main(verbosity=2)

