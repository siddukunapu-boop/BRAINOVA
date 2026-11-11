"""
AetherLearn AI — Document Processing, Text Extraction, Chunking & Source-Grounded Retrieval Pipeline
Enforces user ownership across extraction and retrieval.
Handles PDFs (text-layer stream decoding + scanned PDF OCR detection), Markdown, TXT, CSV, JSON, and Code files.
"""

import math
import os
import re
import zlib
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from backend.database import new_id, utc_now

SUPPORTED_EXTENSIONS = {
    ".pdf": "PDF Document",
    ".txt": "Plain Text",
    ".md": "Markdown Document",
    ".markdown": "Markdown Document",
    ".csv": "CSV Dataset",
    ".json": "JSON Document",
    ".py": "Python Source",
    ".js": "JavaScript Source",
    ".ts": "TypeScript Source",
    ".tsx": "TypeScript React",
    ".html": "HTML Document",
}


def _decode_pdf_literal_string(raw: bytes) -> str:
    """Decodes PDF literal strings (...) and hex strings <...> into readable text."""
    out: List[str] = []
    # Match (text) blocks
    for m in re.finditer(rb"\((?:\\.|[^\\()])*\)", raw):
        s = m.group(0)[1:-1]
        s = s.replace(rb"\n", b"\n").replace(rb"\r", b"\r").replace(rb"\t", b" ")
        s = s.replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\")
        # Octal escapes
        s = re.sub(rb"\\([0-7]{1,3})", lambda om: bytes([int(om.group(1), 8)]), s)
        try:
            decoded = s.decode("utf-8", errors="ignore")
        except Exception:
            decoded = s.decode("latin-1", errors="ignore")
        decoded = "".join(ch for ch in decoded if ch.isprintable() or ch in "\n\t ")
        if decoded.strip():
            out.append(decoded)
    return " ".join(out)


def extract_text_from_pdf_bytes(data: bytes) -> Tuple[List[str], Optional[str]]:
    """
    Extracts text per page from a PDF file.
    1. Tries pypdf / pypdf2 if installed.
    2. Uses native PDF stream inflation (FlateDecode) and BT/ET text operator extraction.
    3. Detects scanned/image-only PDFs and returns a clear OCR limitation message if no text layer exists.
    """
    try:
        import pypdf  # type: ignore
        import io
        reader = pypdf.PdfReader(io.BytesIO(data))
        pages = []
        for idx, page in enumerate(reader.pages):
            txt = (page.extract_text() or "").strip()
            if txt:
                pages.append(txt)
        if pages:
            return pages, None
    except Exception:
        pass

    # Native PDF parser for uncompressed and FlateDecode compressed content streams
    pages_text: List[str] = []
    stream_pattern = re.compile(rb"stream[\r\n]+(.*?)[\r\n]+endstream", re.DOTALL)
    streams = stream_pattern.findall(data)

    extracted_blocks: List[str] = []
    for raw_stream in streams:
        decompressed = None
        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                decompressed = zlib.decompress(raw_stream.strip(), wbits)
                break
            except Exception:
                continue
        target = decompressed if decompressed is not None else raw_stream

        # Look for BT ... ET text blocks
        bt_blocks = re.findall(rb"BT(.*?)ET", target, re.DOTALL)
        if bt_blocks:
            page_fragments: List[str] = []
            for blk in bt_blocks:
                txt = _decode_pdf_literal_string(blk)
                if txt.strip():
                    page_fragments.append(txt.strip())
            if page_fragments:
                extracted_blocks.append("\n".join(page_fragments))
        else:
            # Check if stream directly has readable literal text
            txt = _decode_pdf_literal_string(target)
            if len(txt.strip()) > 35:
                extracted_blocks.append(txt.strip())

    # Also check top-level uncompressed PDF text operators
    if not extracted_blocks:
        top_bt = re.findall(rb"BT(.*?)ET", data, re.DOTALL)
        for blk in top_bt:
            txt = _decode_pdf_literal_string(blk)
            if txt.strip():
                extracted_blocks.append(txt.strip())

    # Group blocks into sensible logical pages
    if extracted_blocks:
        combined = "\n\n".join(extracted_blocks)
        cleaned = normalize_text(combined)
        if len(cleaned.split()) >= 5:
            # Split into ~350-word pages if multiple blocks merged
            words = cleaned.split()
            page_size = 350
            for i in range(0, len(words), page_size):
                pages_text.append(" ".join(words[i : i + page_size]))
            return pages_text, None

    # Check if this is a valid PDF header but has no extractable text layer (e.g., scanned PDF)
    if data.startswith(b"%PDF"):
        return (
            [],
            "This PDF appears to be a scanned image-only document or uses custom embedded font encodings without a standard text layer. "
            "Local OCR is not configured in this environment. Please upload a text-searchable PDF, Markdown, or plain text document.",
        )
    return [], "Invalid or corrupted PDF file."


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_document_content(file_path: str, filename: str) -> Tuple[List[Tuple[int, str, str]], str, Optional[str]]:
    """
    Returns (list of (page_number, section_title, page_text), full_extracted_text, error_message)
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return [], "", f"Unsupported file format '{ext}'. Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS.keys()))}"

    if not os.path.exists(file_path):
        return [], "", "Uploaded file could not be found on disk."

    with open(file_path, "rb") as f:
        raw_bytes = f.read()

    if len(raw_bytes) == 0:
        return [], "", "The uploaded file is empty (0 bytes)."

    if ext == ".pdf":
        pages, err = extract_text_from_pdf_bytes(raw_bytes)
        if err:
            return [], "", err
        structured_pages: List[Tuple[int, str, str]] = []
        for idx, p_text in enumerate(pages, start=1):
            first_line = p_text.split("\n")[0][:80].strip() or f"Page {idx}"
            structured_pages.append((idx, first_line, p_text))
        full_text = "\n\n".join(p[2] for p in structured_pages)
        return structured_pages, full_text, None

    # Text-based formats (.txt, .md, .csv, .json, .py, .js, .ts, .html)
    try:
        decoded = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        decoded = raw_bytes.decode("latin-1", errors="replace")

    if ext == ".html":
        # Strip script/style tags and extract readable text
        decoded = re.sub(r"<script[\s\S]*?</script>", " ", decoded, flags=re.IGNORECASE)
        decoded = re.sub(r"<style[\s\S]*?</style>", " ", decoded, flags=re.IGNORECASE)
        decoded = re.sub(r"<[^>]+>", " ", decoded)

    cleaned = normalize_text(decoded)
    if not cleaned:
        return [], "", "No readable text content could be extracted from the file."

    # Split into logical sections or pages (~300 words per page/section)
    sections: List[Tuple[int, str, str]] = []
    heading_splits = re.split(r"(?m)^(#{1,3}\s+.+)$", cleaned)
    if len(heading_splits) > 2:
        current_title = "Introduction"
        page_num = 1
        for part in heading_splits:
            part_str = part.strip()
            if not part_str:
                continue
            if re.match(r"^#{1,3}\s+", part_str):
                current_title = re.sub(r"^#{1,3}\s+", "", part_str).strip()[:90]
            else:
                sections.append((page_num, current_title, part_str))
                page_num += 1
    else:
        paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
        current_words: List[str] = []
        current_paras: List[str] = []
        page_num = 1
        for para in paragraphs:
            current_paras.append(para)
            current_words.extend(para.split())
            if len(current_words) >= 260:
                sec_title = current_paras[0].split("\n")[0][:75]
                sections.append((page_num, f"Section {page_num}: {sec_title}", "\n\n".join(current_paras)))
                page_num += 1
                current_words = []
                current_paras = []
        if current_paras:
            sec_title = current_paras[0].split("\n")[0][:75]
            sections.append((page_num, f"Section {page_num}: {sec_title}", "\n\n".join(current_paras)))

    return sections, cleaned, None


def chunk_document_sections(sections: List[Tuple[int, str, str]], max_words: int = 180) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    chunk_idx = 0
    for page_num, sec_title, text in sections:
        words = text.split()
        if not words:
            continue
        step = max(80, max_words - 30)
        for start in range(0, len(words), step):
            slice_words = words[start : start + max_words]
            chunk_text = " ".join(slice_words).strip()
            if not chunk_text:
                continue
            chunks.append(
                {
                    "chunk_index": chunk_idx,
                    "page_number": page_num,
                    "section_title": sec_title,
                    "content": chunk_text,
                    "token_estimate": int(len(slice_words) * 1.3),
                }
            )
            chunk_idx += 1
            if start + max_words >= len(words):
                break
    return chunks


def process_and_index_source(conn, source_id: str, user_id: str, file_path: str, filename: str) -> Dict[str, Any]:
    """
    Full pipeline:
    Validate ownership -> Extract text -> Normalize & chunk -> Store chunks -> Build summary -> Mark ready (or error).
    Never marks a source ready before its extracted content and chunks are persisted.
    """
    row = conn.execute("SELECT * FROM sources WHERE id = ? AND user_id = ?", (source_id, user_id)).fetchone()
    if not row:
        raise ValueError("Source record not found or unauthorized.")

    conn.execute(
        "UPDATE sources SET status = 'processing', error_message = '', updated_at = ? WHERE id = ? AND user_id = ?",
        (utc_now(), source_id, user_id),
    )

    sections, full_text, err = extract_document_content(file_path, filename)
    if err or not full_text.strip():
        err_msg = err or "Unable to extract text from document."
        conn.execute(
            "UPDATE sources SET status = 'error', error_message = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (err_msg, utc_now(), source_id, user_id),
        )
        return conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()

    chunks = chunk_document_sections(sections)
    conn.execute("DELETE FROM source_chunks WHERE source_id = ? AND user_id = ?", (source_id, user_id))

    for ch in chunks:
        conn.execute(
            """
            INSERT INTO source_chunks (id, source_id, user_id, chunk_index, page_number, section_title, content, token_estimate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("chk"),
                source_id,
                user_id,
                ch["chunk_index"],
                ch["page_number"],
                ch["section_title"],
                ch["content"],
                ch["token_estimate"],
            ),
        )

    words = full_text.split()
    word_count = len(words)
    page_count = max(1, len(sections))
    summary_preview = " ".join(words[:65]) + ("..." if word_count > 65 else "")

    conn.execute(
        """
        UPDATE sources
        SET status = 'ready',
            error_message = '',
            extracted_text = ?,
            word_count = ?,
            page_count = ?,
            summary = ?,
            updated_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (full_text, word_count, page_count, summary_preview, utc_now(), source_id, user_id),
    )

    return conn.execute("SELECT * FROM sources WHERE id = ? AND user_id = ?", (source_id, user_id)).fetchone()


def _tokenize_for_search(text: str) -> List[str]:
    stop_words = {
        "the", "and", "for", "that", "this", "with", "from", "are", "was", "were",
        "have", "has", "had", "what", "when", "where", "which", "who", "how", "why",
        "can", "will", "into", "about", "your", "their", "there", "been", "being",
    }
    tokens = re.findall(r"[a-zA-Z0-9_+#.-]{2,}", text.lower())
    return [t for t in tokens if t not in stop_words]


def retrieve_relevant_chunks(
    conn,
    user_id: str,
    source_ids: Optional[List[str]],
    query: str,
    top_k: int = 6,
) -> List[Dict[str, Any]]:
    """
    Retrieves authorized source chunks owned by `user_id` ranked by BM25-style lexical relevance.
    Enforces strict document ownership (`s.user_id = ? AND c.user_id = ?`).
    """
    if source_ids:
        placeholders = ",".join("?" for _ in source_ids)
        sql = f"""
            SELECT c.id, c.source_id, c.chunk_index, c.page_number, c.section_title, c.content,
                   s.title AS source_title, s.original_filename
            FROM source_chunks c
            JOIN sources s ON s.id = c.source_id
            WHERE c.user_id = ? AND s.user_id = ? AND s.status = 'ready' AND c.source_id IN ({placeholders})
            ORDER BY c.source_id, c.chunk_index
        """
        params = [user_id, user_id, *source_ids]
    else:
        sql = """
            SELECT c.id, c.source_id, c.chunk_index, c.page_number, c.section_title, c.content,
                   s.title AS source_title, s.original_filename
            FROM source_chunks c
            JOIN sources s ON s.id = c.source_id
            WHERE c.user_id = ? AND s.user_id = ? AND s.status = 'ready'
            ORDER BY s.created_at DESC, c.chunk_index ASC
        """
        params = [user_id, user_id]

    all_chunks = conn.execute(sql, params).fetchall()
    if not all_chunks:
        return []

    query_tokens = _tokenize_for_search(query)
    if not query_tokens:
        return all_chunks[:top_k]

    # Compute IDF across chunks
    N = len(all_chunks)
    doc_Tokens_list = [_tokenize_for_search(ch["content"] + " " + ch["section_title"]) for ch in all_chunks]
    df: Counter = Counter()
    for d_tokens in doc_Tokens_list:
        for tok in set(d_tokens):
            df[tok] += 1

    avgdl = max(1.0, sum(len(dt) for dt in doc_Tokens_list) / N)
    k1 = 1.5
    b = 0.75

    scored: List[Tuple[float, int, Dict[str, Any]]] = []
    for idx, (ch, d_tokens) in enumerate(zip(all_chunks, doc_Tokens_list)):
        tf = Counter(d_tokens)
        dl = len(d_tokens)
        score = 0.0
        for q_tok in query_tokens:
            if q_tok in tf:
                idf = math.log(1.0 + (N - df[q_tok] + 0.5) / (df[q_tok] + 0.5))
                freq = tf[q_tok]
                denom = freq + k1 * (1.0 - b + b * (dl / avgdl))
                score += idf * ((freq * (k1 + 1.0)) / denom)
            else:
                # Substring match bonus for technical terms
                for dt in set(d_tokens):
                    if q_tok in dt or dt in q_tok:
                        score += 0.35
        scored.append((score, -idx, ch))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected = [item[2] for item in scored[:top_k]]
    return selected

