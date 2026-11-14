import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _build_pdf_with_streams(page_streams: list[bytes], extra_objs: list[bytes] | None = None) -> bytes:
    """Builds a minimal valid PDF with explicit /Type /Page -> /Contents mapping."""
    objs: list[bytes] = []
    # 1: Catalog, 2: Pages
    page_ids = []
    next_id = 3
    page_entries = []
    for st in page_streams:
        p_id = next_id
        c_id = next_id + 1
        next_id += 2
        page_ids.append(p_id)
        page_entries.append((p_id, c_id, st))

    kids_str = " ".join(f"{pid} 0 R" for pid in page_ids).encode("ascii")
    objs.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objs.append(f"2 0 obj\n<< /Type /Pages /Kids [".encode("ascii") + kids_str + f"] /Count {len(page_ids)} >>\nendobj\n".encode("ascii"))

    for p_id, c_id, st in page_entries:
        objs.append(
            f"{p_id} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {c_id} 0 R >>\nendobj\n".encode("ascii")
        )
        objs.append(
            f"{c_id} 0 obj\n<< /Length {len(st)} >>\nstream\n".encode("ascii") + st + b"\nendstream\nendobj\n"
        )

    if extra_objs:
        for eo in extra_objs:
            objs.append(eo)

    buf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(buf))
        buf.extend(obj)
    xref_pos = len(buf)
    buf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for off in offsets[1:]:
        buf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    buf.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    return bytes(buf)


def _pdf_escape(s: str) -> bytes:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("latin-1", errors="replace")


def _make_docx_bytes(paragraphs: list[str], tables: list[list[list[str]]] | None = None) -> bytes:
    bio = io.BytesIO()
    body_parts = []
    for p in paragraphs:
        body_parts.append(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>")
    for tbl in tables or []:
        rows_xml = []
        for row in tbl:
            cells_xml = "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in row)
            rows_xml.append(f"<w:tr>{cells_xml}</w:tr>")
        body_parts.append(f"<w:tbl>{''.join(rows_xml)}</w:tbl>")

    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(body_parts)}</w:body></w:document>"
    )
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
        zf.writestr("word/document.xml", doc_xml)
    return bio.getvalue()


def _make_pptx_bytes(slides: list[list[str]]) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
        for idx, lines in enumerate(slides, start=1):
            ps = "".join(f"<a:p><a:r><a:t>{ln}</a:t></a:r></a:p>" for ln in lines)
            xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                f"<p:cSld><p:spTree><p:sp><p:txBody>{ps}</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
            )
            zf.writestr(f"ppt/slides/slide{idx}.xml", xml)
    return bio.getvalue()


def _write_silent_wav(path: Path, duration_sec: float = 8.0, sample_rate: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * int(duration_sec * sample_rate))


class TestDocExtractionAndVideoRepair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory(prefix="brainova_doc_repair_")
        cls.tmp_path = Path(cls.tmp_dir.name)
        os.environ["AETHER_DB_PATH"] = str(cls.tmp_path / "test_repair.db")

        import backend.database as db
        import backend.video_engine as ve

        db.DB_PATH = cls.tmp_path / "test_repair.db"
        db.init_db()
        ve.VIDEOS_DIR = str(cls.tmp_path / "videos")
        ve.AUDIO_DIR = str(cls.tmp_path / "audio")
        os.makedirs(ve.VIDEOS_DIR, exist_ok=True)
        os.makedirs(ve.AUDIO_DIR, exist_ok=True)

        now = db.utc_now()
        cls.uid = "usr_repair_owner"
        cls.other_uid = "usr_repair_other"
        with db.get_db(commit=True) as conn:
            for u, em in [(cls.uid, "owner@brainova.test"), (cls.other_uid, "other@brainova.test")]:
                conn.execute(
                    "INSERT INTO users (id, name, email, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, 'student', ?, ?)",
                    (u, u, em, "hash", now, now),
                )
                conn.execute("INSERT INTO user_preferences (user_id, updated_at) VALUES (?, ?)", (u, now))

    @classmethod
    def tearDownClass(cls):
        cls.tmp_dir.cleanup()

    def test_01_text_based_css_pdf(self):
        from backend.doc_processor import extract_text_from_pdf_bytes

        st = (
            b"BT /F1 12 Tf 72 720 Td (" + _pdf_escape("CSS Box Model controls content, padding, border, and margin around HTML elements.") + b") Tj "
            b"0 -20 Td (" + _pdf_escape("Flexbox and CSS Grid provide responsive two-dimensional page layouts.") + b") Tj ET"
        )
        pdf_bytes = _build_pdf_with_streams([st])
        pages, err = extract_text_from_pdf_bytes(pdf_bytes)
        self.assertIsNone(err)
        self.assertEqual(len(pages), 1)
        self.assertIn("CSS Box Model", pages[0])
        self.assertIn("Flexbox and CSS Grid", pages[0])

    def test_02_scanned_css_pdf_and_mixed_pdf_ocr(self):
        from backend.doc_processor import extract_pdf_with_diagnostics

        real_scanned = ROOT_DIR / "data" / "uploads" / "usr_193af7f668bf4982" / "src_ee57378ba5f04190_CS_FUNDAMENTALS.pdf"
        if real_scanned.exists():
            pages, err, diag = extract_pdf_with_diagnostics(real_scanned.read_bytes())
            self.assertIsNone(err, f"Scanned PDF OCR failed unexpectedly: {err}")
            self.assertGreaterEqual(len(pages), 2)
            self.assertGreaterEqual(diag["pages_requiring_ocr"], 2)
            self.assertGreaterEqual(diag["pages_ocr_succeeded"], 2)
            combined = "\n".join(pages)
            self.assertIn("CS Fundamentals", combined)

        # Mixed PDF: Page 1 has native text, Page 2 is image/blank stream needing OCR (mocked WinRT OCR for deterministic mixed merge)
        p1 = b"BT /F1 12 Tf 72 720 Td (" + _pdf_escape("CSS Specificity determines which selector rule wins when multiple rules target an element.") + b") Tj ET"
        p2 = b"q 612 0 0 792 0 0 cm /Im1 Do Q"
        mixed_pdf = _build_pdf_with_streams([p1, p2])
        with patch("backend.doc_processor._ocr_pdf_pages_winrt", return_value=({2: "CSS Grid uses grid-template-columns and grid-template-rows to align tracks cleanly."}, 2, 0.25, None)) as mock_ocr:
            pages, err, diag = extract_pdf_with_diagnostics(mixed_pdf)
            self.assertIsNone(err)
            self.assertEqual(len(pages), 2)
            self.assertEqual(diag["pages_with_native_text"], 1)
            self.assertEqual(diag["pages_requiring_ocr"], 1)
            # Ensure OCR was only called for page 2, NOT page 1
            mock_ocr.assert_called_once()
            self.assertEqual(mock_ocr.call_args[0][1], [2])
            self.assertIn("CSS Specificity", pages[0])
            self.assertIn("CSS Grid", pages[1])

    def test_03_multicolumn_tables_and_equations_pdf(self):
        from backend.doc_processor import extract_text_from_pdf_bytes

        # Multi-column PDF: left column (x=60) vs right column (x=340)
        mc_stream = (
            b"BT 1 0 0 1 60 700 Tm (" + _pdf_escape("Left Column First: CSS Cascading rules resolve conflicting declarations.") + b") Tj ET\n"
            b"BT 1 0 0 1 340 700 Tm (" + _pdf_escape("Right Column First: Media queries adapt styles across viewport widths.") + b") Tj ET\n"
            b"BT 1 0 0 1 60 660 Tm (" + _pdf_escape("Left Column Second: Inheritance passes typography properties to child nodes.") + b") Tj ET\n"
            b"BT 1 0 0 1 340 660 Tm (" + _pdf_escape("Right Column Second: Custom properties store reusable CSS design tokens.") + b") Tj ET\n"
        )
        pages_mc, err = extract_text_from_pdf_bytes(_build_pdf_with_streams([mc_stream]))
        self.assertIsNone(err)
        txt_mc = pages_mc[0]
        self.assertLess(txt_mc.index("Left Column Second"), txt_mc.index("Right Column First"))

        # Table + Equations PDF
        tbl_stream = (
            b"BT 1 0 0 1 60 700 Tm (" + _pdf_escape("Selector") + b") Tj ET\n"
            b"BT 1 0 0 1 260 700 Tm (" + _pdf_escape("Specificity") + b") Tj ET\n"
            b"BT 1 0 0 1 60 670 Tm (" + _pdf_escape("#header") + b") Tj ET\n"
            b"BT 1 0 0 1 260 670 Tm (" + _pdf_escape("100 points") + b") Tj ET\n"
            b"BT 1 0 0 1 60 620 Tm (" + _pdf_escape("Total Width = content + 2 * padding + 2 * border, and 6CO2 + 6H2O -> C6H12O6 + 6O2.") + b") Tj ET\n"
        )
        pages_tbl, err2 = extract_text_from_pdf_bytes(_build_pdf_with_streams([tbl_stream]))
        self.assertIsNone(err2)
        self.assertIn("Total Width = content + 2 * padding + 2 * border", pages_tbl[0])
        self.assertIn("6CO2 + 6H2O -> C6H12O6 + 6O2", pages_tbl[0])

    def test_04_docx_pptx_txt_formats(self):
        from backend.doc_processor import extract_document_content

        docx_p = self.tmp_path / "css_guide.docx"
        docx_p.write_bytes(_make_docx_bytes(
            ["CSS Flexbox arranges items along a main axis and a cross axis cleanly."],
            tables=[[["Property", "Purpose"], ["justify-content", "Aligns items horizontally"]]],
        ))
        secs_d, full_d, err_d = extract_document_content(str(docx_p), "css_guide.docx")
        self.assertIsNone(err_d)
        self.assertIn("CSS Flexbox", full_d)
        self.assertIn("justify-content | Aligns items horizontally", full_d)

        pptx_p = self.tmp_path / "css_slides.pptx"
        pptx_p.write_bytes(_make_pptx_bytes([
            ["Slide One: CSS Selectors", "Element, class, and ID selectors target DOM elements."],
            ["Slide Two: CSS Animations", "Keyframes interpolate properties smoothly over duration."],
        ]))
        secs_p, full_p, err_p = extract_document_content(str(pptx_p), "css_slides.pptx")
        self.assertIsNone(err_p)
        self.assertEqual(len(secs_p), 2)
        self.assertLess(full_p.index("Slide One"), full_p.index("Slide Two"))

        txt_p = self.tmp_path / "css_notes.txt"
        txt_p.write_text("CSS Variables allow theme tokens like --primary-color to be reused cleanly.", encoding="utf-8")
        secs_t, full_t, err_t = extract_document_content(str(txt_p), "css_notes.txt")
        self.assertIsNone(err_t)
        self.assertIn("--primary-color", full_t)

    def test_05_empty_corrupt_insufficient_and_unauthorized(self):
        from backend.doc_processor import diagnose_and_recover_source_chunks, extract_document_content
        import backend.database as db

        empty_pdf = self.tmp_path / "empty.pdf"
        empty_pdf.write_bytes(b"")
        _, _, err_e = extract_document_content(str(empty_pdf), "empty.pdf")
        self.assertIsNotNone(err_e)

        corrupt_pdf = self.tmp_path / "corrupt.pdf"
        corrupt_pdf.write_bytes(b"NOT_A_PDF_BINARY_GARBAGE_12345")
        _, _, err_c = extract_document_content(str(corrupt_pdf), "corrupt.pdf")
        self.assertIn("couldn't read", err_c.lower())

        insuff_pdf = self.tmp_path / "tiny.pdf"
        insuff_pdf.write_bytes(_build_pdf_with_streams([b"BT /F1 12 Tf 72 720 Td (Hi) Tj ET"]))
        with patch("backend.doc_processor._ocr_pdf_pages_winrt", return_value=({1: "Hi"}, 1, 0.05, None)):
            _, _, err_i = extract_document_content(str(insuff_pdf), "tiny.pdf")
            self.assertIsNotNone(err_i)

        # Unauthorized source ID check
        with db.get_db() as conn:
            chunks_u, diag_u = diagnose_and_recover_source_chunks(conn, self.other_uid, ["src_nonexistent_or_unowned"], "CSS")
            self.assertEqual(chunks_u, [])
            self.assertEqual(diag_u["error_code"], "unauthorized_source")

    def test_06_retrieval_recovery_and_full_video_overview_plus_frame_orientation(self):
        import backend.database as db
        from backend.doc_processor import diagnose_and_recover_source_chunks
        from backend.job_worker import execute_job_sync

        # Create a real text-based CSS PDF on disk, but simulate legacy corrupt chunks in DB!
        css_pdf_path = self.tmp_path / "css_mastery.pdf"
        st1 = (
            b"BT /F1 12 Tf 72 720 Td (" + _pdf_escape("CSS Box Model defines content, padding, border, and margin around every element.") + b") Tj "
            b"0 -22 Td (" + _pdf_escape("CSS Flexbox aligns items in one dimension using justify-content and align-items.") + b") Tj ET"
        )
        st2 = (
            b"BT /F1 12 Tf 72 720 Td (" + _pdf_escape("CSS Grid creates two-dimensional layouts with grid-template-columns and gap spacing.") + b") Tj "
            b"0 -22 Td (" + _pdf_escape("Media queries enable responsive web design across mobile, tablet, and desktop viewports.") + b") Tj ET"
        )
        css_pdf_path.write_bytes(_build_pdf_with_streams([st1, st2]))

        now = db.utc_now()
        src_id = "src_css_recovery"
        oid = "std_css_recovery"
        jid = "job_css_recovery"
        with db.get_db(commit=True) as conn:
            conn.execute(
                """
                INSERT INTO sources (id, user_id, title, original_filename, file_path, file_type, file_size,
                    status, error_message, extracted_text, word_count, page_count, summary, tags_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, '.pdf', ?, 'ready', '', 'corrupt', 5, 1, 'corrupt', '[]', ?, ?)
                """,
                (src_id, self.uid, "CSS", "css_mastery.pdf", str(css_pdf_path), css_pdf_path.stat().st_size, now, now),
            )
            # Legacy corrupt ICC binary chunk
            conn.execute(
                """
                INSERT INTO source_chunks (id, source_id, user_id, chunk_index, page_number, section_title, content, token_estimate)
                VALUES (?, ?, ?, 0, 1, 'Page 1', 'cprt<mlucenUSsRGBXYZ Google Inc. \x01\x02\x03', 10)
                """,
                (db.new_id("chk"), src_id, self.uid),
            )
            chunks, diag = diagnose_and_recover_source_chunks(conn, self.uid, [src_id], "CSS")
            self.assertEqual(diag["status"], "ok")
            self.assertEqual(diag.get("recovery_used"), "reprocessed_with_ocr_or_parser")
            self.assertGreaterEqual(len(chunks), 2)

            conn.execute(
                """
                INSERT INTO studio_outputs (
                    id, user_id, tool_type, title, source_ids_json, config_json, content_json,
                    language, style_label, duration_label, status, error_message, created_at, updated_at
                ) VALUES (?, ?, 'video_overview', 'CSS', ?, ?, '{}', 'English', 'Concept Breakdown', 'Adaptive', 'queued', '', ?, ?)
                """,
                (oid, self.uid, json.dumps([src_id]), json.dumps({"topic": "CSS", "language": "English"}), now, now),
            )
            conn.execute(
                """
                INSERT INTO generation_jobs (id, user_id, job_type, resource_type, studio_output_id, status, created_at)
                VALUES (?, ?, 'studio_video', 'video_overview', ?, 'queued', ?)
                """,
                (jid, self.uid, oid, now),
            )

        fake_wav = self.tmp_path / "audio" / f"{oid}_vid.wav"
        _write_silent_wav(fake_wav, duration_sec=8.0)

        def _fake_tts(output_id, dialogue, openai_api_key=None, language="English", require_native_voice=True):
            return {
                "file_name": fake_wav.name,
                "file_path": str(fake_wav),
                "audio_url": f"/api/studio/audio/{fake_wav.name}",
                "duration_seconds": 8,
                "language": language,
                "provider": "test_local_wav",
                "status": "ready",
                "voice_supported": True,
            }

        with patch("backend.video_engine.synthesize_podcast_audio", side_effect=_fake_tts):
            res_job = execute_job_sync(jid)

        self.assertEqual(res_job["status"], "completed", f"Job failed: {res_job}")
        with db.get_db() as conn:
            out = conn.execute("SELECT * FROM studio_outputs WHERE id = ?", (oid,)).fetchone()
        self.assertEqual(out["status"], "completed")
        payload = json.loads(out["content_json"])
        scenes = payload.get("scenes") or []
        self.assertGreaterEqual(len(scenes), 2)
        all_text = " ".join(
            f"{s.get('title','')} {s.get('on_screen_text','')} {s.get('narration','')}" for s in scenes
        )
        self.assertTrue("CSS" in all_text or "Flexbox" in all_text or "Grid" in all_text)

        # Part 10: Check generated MP4 + keyframe PNG dimensions & upright header/caption composition
        vid_meta = payload.get("video") or {}
        mp4_path = Path(str(vid_meta.get("file_path") or ""))
        self.assertTrue(mp4_path.exists(), f"MP4 missing: {mp4_path}")
        thumb_path = Path(str(vid_meta.get("thumbnail_path") or ""))
        frame_png = mp4_path.parent / f"frames_{oid}" / "scene_1.png"
        png_to_check = frame_png if frame_png.exists() else thumb_path
        self.assertTrue(png_to_check.exists(), f"Keyframe PNG missing: {frame_png} / {thumb_path}")
        png_bytes = png_to_check.read_bytes()
        self.assertTrue(png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))
        w = int.from_bytes(png_bytes[16:20], "big")
        h = int.from_bytes(png_bytes[20:24], "big")
        self.assertEqual((w, h), (1920, 1080))
        self.assertEqual(vid_meta.get("resolution"), "1920x1080")
        self.assertEqual(vid_meta.get("fps"), 24)


if __name__ == "__main__":
    unittest.main()
