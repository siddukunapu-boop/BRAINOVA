"""
AetherLearn AI — Document Processing, Text Extraction, Chunking & Source-Grounded Retrieval Pipeline
Enforces user ownership across extraction and retrieval.
Handles PDFs (native page-stream decoding + selective WinRT OCR), DOCX, PPTX, Markdown, TXT, CSV, JSON, HTML, and Code files.
"""

import json
import logging
import math
import os
import re
import subprocess
import tempfile
import time
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
import zlib
from collections import Counter
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from backend.database import new_id, utc_now

_DOC_LOGGER = logging.getLogger("brainova.doc_processor")

SUPPORTED_EXTENSIONS = {
    ".pdf": "PDF Document",
    ".docx": "Word Document",
    ".pptx": "PowerPoint Presentation",
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


_ALLOWED_COMMON_COMBINING = (
    "COMBINING ACUTE",
    "COMBINING GRAVE",
    "COMBINING TILDE",
    "COMBINING DIAERESIS",
    "COMBINING CIRCUMFLEX",
    "COMBINING CEDILLA",
    "COMBINING RING",
    "COMBINING MACRON",
)

_NON_TEXT_STREAM_DICT_PATTERNS = (
    re.compile(rb"/Subtype\s*/(?:Image|Type1C|CIDFontType0C|OpenType|XML)\b"),
    re.compile(rb"/Type\s*/(?:XRef|ObjStm|Metadata)\b"),
    re.compile(rb"/(?:Length1|Length2|Length3|FontFile|FontFile2|FontFile3|FontBBox|FontDescriptor)\b"),
    re.compile(rb"/Alternate\s*/"),
)

_UNSUPPORTED_FILTER_NAMES = {
    b"DCTDecode",
    b"JPXDecode",
    b"JBIG2Decode",
    b"CCITTFaxDecode",
    b"LZWDecode",
    b"RunLengthDecode",
    b"Crypt",
    b"ASCII85Decode",
    b"ASCIIHexDecode",
}

_PDF_TEXT_OPERATOR_RE = re.compile(rb"(?:\((?:\\.|[^\\()])*\)|\[[^\]]*\])\s*(?:Tj|TJ|'|\"(?=\s))")


def is_plausible_source_sentence(text: str) -> bool:
    """
    Validates that a candidate text sequence is plausible natural-language, technical,
    mathematical, or multilingual content rather than decoded binary/font/image artifacts.
    """
    if not text or not text.strip():
        return False

    for ch in text:
        code = ord(ch)
        if (code < 32 and ch not in "\t\n\r") or (0x7F <= code <= 0x9F) or code == 0xFFFD or (0xE000 <= code <= 0xF8FF):
            return False

    # Reject long runs of identical non-word symbols (e.g. '........', '////////')
    if re.search(r"([^\w\s])\1{5,}", text):
        return False

    # Reject sentences mixing multiple unrelated non-Latin natural scripts
    non_latin_scripts = set()
    prev_latin = False
    for ch in text:
        cat = unicodedata.category(ch)
        nm = unicodedata.name(ch, "")
        if cat.startswith("L") and nm:
            script = nm.split()[0]
            if script not in ("LATIN", "GREEK", "MATHEMATICAL"):
                non_latin_scripts.add(script)
        if cat.startswith("M") and prev_latin:
            if nm and not any(k in nm for k in _ALLOWED_COMMON_COMBINING):
                return False
        prev_latin = cat.startswith("L") and nm.startswith("LATIN")

    if len(non_latin_scripts) >= 2:
        return False

    non_ws = [c for c in text if not c.isspace()]
    if not non_ws:
        return False

    alnum = sum(1 for c in non_ws if unicodedata.category(c)[0] in ("L", "N"))
    if alnum / len(non_ws) < 0.35:
        return False

    tokens = text.split()
    tangled = 0
    clean_words = 0
    for tok in tokens:
        stripped = tok.strip(".,!?;:'\"()[]{}")
        if not stripped:
            continue
        if re.search(r"[A-Za-z0-9]", stripped) and len(re.findall(r"[@#$%^&*\\|<>~?!/`]", stripped)) >= 2:
            tangled += 1
        if re.fullmatch(r"[^\W\d_]{2,}(?:['-][^\W\d_]+)*", stripped, re.UNICODE) or any(
            unicodedata.category(c) in ("Lo", "Mc", "Mn") for c in stripped
        ):
            clean_words += 1

    if tangled >= 2 or (len(tokens) >= 4 and tangled / len(tokens) > 0.25):
        return False
    if len(text.strip()) >= 25 and clean_words < 2:
        return False

    return True


def is_plausible_source_chunk(text: str) -> bool:
    """
    Chunk-level quality validator for multi-sentence paragraphs and long passages.
    Allows valid long paragraphs even if a single embedded formula or minor token is unusual,
    while rejecting binary/font/image garbage chunks.
    """
    if not text or not text.strip():
        return False

    for ch in text:
        code = ord(ch)
        if (code < 32 and ch not in "\t\n\r") or (0x7F <= code <= 0x9F) or code == 0xFFFD or (0xE000 <= code <= 0xF8FF):
            return False

    non_ws = [c for c in text if not c.isspace()]
    if not non_ws:
        return False

    alnum = sum(1 for c in non_ws if unicodedata.category(c)[0] in ("L", "N"))
    if alnum / len(non_ws) < 0.35:
        return False

    # Split into sentences/lines and require at least one substantial plausible sentence
    segments = [seg.strip() for seg in re.split(r"(?<=[.!?।])\s+|\n+", text) if len(seg.strip()) >= 20]
    if not segments:
        return is_plausible_source_sentence(text)

    plausible_count = sum(1 for seg in segments if is_plausible_source_sentence(seg))
    return plausible_count >= 1 and (plausible_count / len(segments)) >= 0.35


_INCOMPLETE_ENDING_WORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "by", "from",
    "and", "or", "but", "this", "that", "these", "those", "is", "are", "was", "were",
}


def is_complete_source_sentence(text: str) -> bool:
    """
    Sentence-level completeness validator for narration facts.
    Rejects image captions, unclosed quote fragments, section-number-only headings,
    and truncated mid-sentence fragments while preserving valid citations and formulas.
    """
    s = (text or "").strip()
    if not is_plausible_source_sentence(s):
        return False

    # Reject unclosed double quotes (e.g. broken mid-quote fragments)
    if s.count('"') % 2 == 1:
        return False

    # Reject fragments starting lowercase (mid-sentence continuation), except code/math symbols
    if s[0].islower() and not re.match(r"^(?:const|let|var|def|class|function|e\.g\.|i\.e\.)", s):
        return False

    # Reject figure/table/photo captions (e.g. "Figure 1: ...", "Russian and German Soldiers as friends, 1917.")
    if re.match(r"^(?:fig(?:ure)?|table|plate|photo|map|chart|diagram|source)\s*\d*[:.\-]", s, re.IGNORECASE):
        return False

    # Reject character-spaced OCR/PDF fragments (e.g. "P r o v i de d by", "I n c e ll u lar")
    words = s.rstrip(".!?।").split()
    if len(words) >= 8:
        single_alpha = sum(1 for w in words if len(w.strip(",;:'\"()[]")) == 1 and w.strip(",;:'\"()[]").isalpha())
        if single_alpha / len(words) > 0.40:
            return False

    # Reject short noun-phrase + year captions with no finite verb (<= 10 words ending in ", 1917.")
    if len(words) <= 9 and re.search(r",\s*\d{4}[.!?]?$", s) and not re.search(
        r"\b(?:is|are|was|were|has|have|had|became|led|ended|began|started|established|created|caused|showed)\b",
        s,
        re.IGNORECASE,
    ):
        return False

    # Require terminal sentence punctuation for narration facts so mid-sentence chunk cuts
    # (e.g. "In cellular respiration, glucose and i") are never accepted as complete facts.
    if s[-1] not in ".!?।\"'”’)]":
        return False

    return True


# Conservative, deterministic map of unambiguous whole-word OCR misreads.
# Never apply blind substring rules (e.g. rn->m or ri->n) to avoid corrupting
# unfamiliar historical, scientific, technical, or proper-name terminology.
_SAFE_OCR_WORD_CORRECTIONS: Dict[str, str] = {
    "domiriance": "dominance",
    "govemment": "government",
    "governrnent": "government",
    "developrnent": "development",
    "informalion": "information",
    "corirnection": "connection",
    "environrnent": "environment",
    "managernent": "management",
    "parliarnent": "parliament",
    "agreernent": "agreement",
    "treatrnent": "treatment",
    "rnilitary": "military",
    "econornic": "economic",
    "corirnunity": "community",
    "induslrial": "industrial",
    "polilical": "political",
    "consequenee": "consequence",
}

_OCR_WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _SAFE_OCR_WORD_CORRECTIONS) + r")\b",
    re.IGNORECASE,
)

_PRESERVED_UPPER_TOKENS = {
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
    "ww1", "ww2", "wwi", "wwii", "dna", "rna", "api", "os", "cpu",
    "gpu", "http", "https", "sql", "ai", "ml", "usa", "uk", "ussr", "un",
}


_SAFE_KERNING_PHRASE_CORRECTIONS: Dict[str, str] = {
    "f ermentation": "fermentation",
    "ha ndout": "handout",
    "s yntha se": "synthase",
    "react s": "reacts",
}

_EXACT_CASE_KERNING_CORRECTIONS: Dict[str, str] = {
    "O xidation": "Oxidation",
    "I s": "Is",
    "L osing": "Losing",
    "R eduction": "Reduction",
    "G aining": "Gaining",
    "T he": "The",
}

_KERNING_PHRASE_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _SAFE_KERNING_PHRASE_CORRECTIONS) + r")\b",
    re.IGNORECASE,
)
_EXACT_KERNING_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _EXACT_CASE_KERNING_CORRECTIONS) + r")\b"
)


_KERNING_WORD_LEXICON: FrozenSet[str] = frozenset({
    # Core English function & prose words
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by", "can",
    "could", "did", "do", "does", "done", "each", "either", "every", "for", "from",
    "had", "has", "have", "having", "he", "her", "here", "hers", "him", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "just", "may", "might", "more", "most",
    "must", "my", "neither", "no", "not", "now", "of", "on", "one", "only", "or",
    "other", "our", "out", "over", "own", "same", "shall", "she", "should", "since",
    "so", "some", "such", "than", "that", "the", "their", "them", "then", "there",
    "these", "they", "this", "those", "though", "through", "to", "too", "two", "under",
    "until", "up", "us", "use", "used", "using", "very", "was", "we", "well", "were",
    "what", "when", "where", "which", "while", "who", "whom", "whose", "why", "will",
    "with", "within", "without", "would", "you", "your",
    # Common academic, CS, JS, Bio, Econ words
    "above", "access", "accessed", "across", "after", "again", "all", "allow", "allows",
    "also", "always", "amount", "another", "any", "application", "array", "assigned",
    "assigns", "available", "based", "because", "becomes", "before", "below", "between",
    "block", "boolean", "both", "called", "calls", "case", "cases", "change", "changes",
    "character", "characters", "class", "code", "comment", "comments", "common", "complex",
    "concept", "condition", "conditions", "const", "constant", "contains", "content",
    "context", "control", "correct", "create", "created", "creates", "current", "data",
    "datatype", "datatypes", "declare", "declared", "declaring", "default", "defined",
    "defines", "definition", "different", "digit", "digits", "directly", "document",
    "dollar", "dynamic", "earlier", "element", "elements", "else", "enable", "enables",
    "end", "enough", "equal", "error", "errors", "even", "event", "example", "examples",
    "execute", "executed", "executes", "execution", "expression", "expressions", "external",
    "false", "feature", "features", "fermentation", "file", "files", "final", "finally",
    "find", "first", "float", "flow", "following", "form", "format", "forms", "found",
    "function", "functions", "general", "given", "global", "good", "group", "handout",
    "high", "higher", "hold", "holds", "however", "identifier", "identifiers", "important",
    "include", "includes", "including", "incorrect", "index", "indexes", "information",
    "initial", "initialize", "initialized", "input", "inputs", "inside", "instance",
    "instead", "integer", "integers", "internal", "into", "invalid", "item", "items",
    "javascript", "key", "keys", "keyword", "keywords", "known", "language", "large",
    "last", "later", "learn", "less", "let", "letter", "letters", "level", "like",
    "line", "lines", "list", "lists", "local", "location", "locations", "long", "loop",
    "loops", "low", "lower", "main", "make", "makes", "making", "many", "mean", "meaning",
    "means", "memory", "method", "methods", "model", "module", "multiple", "name",
    "named", "names", "naming", "need", "needs", "never", "new", "next", "null", "number",
    "numbers", "numeric", "object", "objects", "often", "once", "open", "operand",
    "operands", "operator", "operators", "order", "output", "outputs", "outside",
    "overview", "page", "pages", "parameter", "parameters", "part", "parts", "pass",
    "passed", "passes", "passing", "path", "pattern", "perform", "performs", "place",
    "point", "points", "possible", "power", "present", "primitive", "primitives", "print",
    "process", "processes", "program", "programming", "programs", "property", "properties",
    "provide", "provides", "public", "purpose", "put", "range", "read", "reading", "real",
    "reason", "record", "records", "reference", "references", "refer", "refers", "related",
    "remember", "replace", "represent", "represents", "require", "requires", "reserved",
    "result", "results", "return", "returns", "rule", "rules", "run", "running", "runs",
    "same", "save", "saved", "scope", "script", "scripts", "second", "section", "see",
    "select", "sensitive", "sentence", "separate", "sequence", "server", "set", "sets",
    "several", "share", "shared", "shares", "short", "show", "shown", "shows", "side",
    "sign", "signs", "similar", "simple", "simply", "single", "size", "small", "source",
    "space", "spaces", "special", "specific", "standard", "start", "starting", "starts",
    "state", "statement", "statements", "states", "static", "status", "step", "steps",
    "still", "stop", "storage", "store", "stored", "stores", "storing", "string",
    "strings", "structure", "structures", "study", "style", "subject", "summary",
    "support", "supported", "supports", "symbol", "symbols", "syntax", "system", "systems",
    "table", "tables", "take", "taken", "takes", "target", "task", "tasks", "term",
    "terms", "text", "therefore", "thing", "things", "think", "third", "though", "three",
    "time", "times", "title", "today", "together", "topperworld", "total", "true", "try",
    "turn", "turns", "type", "typed", "types", "typical", "typically", "undefined",
    "underscore", "understand", "unit", "units", "unknown", "unlike", "update", "updated",
    "upper", "user", "users", "usually", "valid", "value", "values", "var", "variable",
    "variables", "various", "version", "view", "way", "ways", "web", "whether", "whole",
    "wide", "word", "words", "work", "working", "works", "world", "write", "writes",
    "writing", "written", "wrong", "year", "years", "zero",
})

_PROTECTED_CODE_TOKENS: FrozenSet[str] = frozenset({"var", "let", "const", "int", "str", "def", "fn", "x", "y", "z", "i", "j", "k", "n"})


def _is_valid_standalone_word(tok: str) -> bool:
    low = tok.lower()
    if low in _KERNING_WORD_LEXICON:
        return True
    if len(tok) >= 3 and tok.isupper() and tok.isalpha():
        return True
    return False


def repair_pdf_kerning_splits(text: str) -> str:
    """
    Conservatively repairs PDF character-kerning splits (e.g. 'J av aS cri p t' -> 'JavaScript',
    'var ia b le' -> 'variable') using dictionary-guided dynamic programming over runs of
    alphabetic fragments. Preserves legitimate spaces between valid words and code tokens.
    """
    raw = text or ""
    # Fast guard: only run when there is at least one suspicious short non-word fragment
    if not re.search(r"(?:^|\s)[A-Za-z]{1,3}\s+[A-Za-z]{1,4}(?:\s|$)", raw):
        return raw

    # Split into alternating runs of [alphabetic-space-runs] and [non-run separators]
    # Process each contiguous run of space-separated alphabetic tokens independently.
    def _repair_alpha_run(match: re.Match) -> str:
        run = match.group(0)
        tokens = run.split(" ")
        if len(tokens) < 2:
            return run
        # Require at least one non-word fragment (or single non-article letter not next to code)
        has_fragment = any(
            not _is_valid_standalone_word(t) or (len(t) == 1 and t.lower() not in {"a", "i"})
            for t in tokens
        )
        if not has_fragment:
            return run

        n = len(tokens)
        # DP: best[i] = (score, output_tokens_list) for tokens[i:]
        # Higher score is better; merging valid fragments into a lexicon word gives +10,
        # leaving a non-word fragment unmerged gives -5, leaving a valid word unmerged gives +2.
        best: List[Optional[Tuple[int, List[str]]]] = [None] * (n + 1)
        best[n] = (0, [])

        for i in range(n - 1, -1, -1):
            # Option 1: keep tokens[i] as-is
            tok_i = tokens[i]
            tail_score, tail_list = best[i + 1]  # type: ignore[misc]
            if _is_valid_standalone_word(tok_i):
                step_score = 3 if len(tok_i) >= 2 else 1
            elif tok_i.lower() in _PROTECTED_CODE_TOKENS:
                step_score = 1
            else:
                step_score = -6
            best_choice = (step_score + tail_score, [tok_i] + tail_list)

            # Option 2: merge tokens[i..j] (up to 8 fragments) into one lexicon word
            max_j = min(n, i + 9)
            for j in range(i + 2, max_j + 1):
                span = tokens[i:j]
                # Never merge if every token in the span is already a valid standalone word
                if all(_is_valid_standalone_word(t) for t in span):
                    continue
                # Never merge a protected 1-letter variable if preceded by var/let/const
                if i > 0 and tokens[i - 1].lower() in {"var", "let", "const"} and len(tokens[i]) == 1:
                    continue
                joined = "".join(span)
                if len(joined) < 2 or joined.lower() not in _KERNING_WORD_LEXICON:
                    continue
                # Bonus scales with number of fragments rescued
                frag_count = sum(1 for t in span if not _is_valid_standalone_word(t) or len(t) == 1)
                if frag_count == 0:
                    continue
                merge_score = 10 + 3 * (j - i) + 2 * frag_count
                next_score, next_list = best[j]  # type: ignore[misc]
                cand_score = merge_score + next_score
                if cand_score > best_choice[0]:
                    # Preserve canonical casing for JavaScript if matched
                    display = "JavaScript" if joined.lower() == "javascript" else joined
                    best_choice = (cand_score, [display] + next_list)

            best[i] = best_choice

        return " ".join(best[0][1])  # type: ignore[index]

    # Handle kerning splits immediately before a trailing digit (e.g. 'val u e1' -> 'value1')
    raw = re.sub(r"\bval\s+u\s+e(\d+)\b", r"value\1", raw)
    return re.sub(r"\b[A-Za-z]+(?: [A-Za-z]+)+\b", _repair_alpha_run, raw)


def clean_source_sentence_for_narration(text: str) -> str:
    """
    Applies conservative, deterministic cleanup to a validated source sentence
    for spoken narration without altering unfamiliar or proper terminology.
    """
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return ""
    cleaned = repair_pdf_kerning_splits(cleaned)

    def _replace_map(mapping: Dict[str, str], case_sensitive: bool = False):
        def _repl(match: re.Match) -> str:
            raw = match.group(0)
            if case_sensitive:
                return mapping[raw]
            replacement = mapping[raw.lower()]
            if raw.isupper():
                return replacement.upper()
            if raw[0].isupper():
                return replacement[0].upper() + replacement[1:]
            return replacement
        return _repl

    cleaned = _EXACT_KERNING_RE.sub(_replace_map(_EXACT_CASE_KERNING_CORRECTIONS, case_sensitive=True), cleaned)
    cleaned = _KERNING_PHRASE_RE.sub(_replace_map(_SAFE_KERNING_PHRASE_CORRECTIONS), cleaned)
    cleaned = _OCR_WORD_RE.sub(_replace_map(_SAFE_OCR_WORD_CORRECTIONS), cleaned)
    # Normalize a stray semicolon inside a comma-separated list before 'and'
    # while preserving legitimate semicolons between independent prose clauses.
    cleaned = re.sub(r"(,\s*[^,;.!?]+);\s+([^,;.!?]+\s+and\s+)", r"\1, \2", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    # Clean PDF-spaced quotation marks and chemical/ion notation (e.g. "“ OIL RIG ”", "H +", "FADH 2", "H 2 O")
    cleaned = re.sub(r'([“"])\s+([^”"]+?)\s+([”"])', r"\1\2\3", cleaned)
    cleaned = re.sub(r"\b(H|NAD|FAD)\s+\+", r"\1+", cleaned)
    cleaned = re.sub(r"\b(FADH|NADH|CO)\s+2\b", r"\g<1>2", cleaned)
    cleaned = re.sub(r"\bH\s+2\s+O\b", "H2O", cleaned)
    return cleaned


def clean_spoken_topic_name(raw_topic: str, fallback: str = "Selected Study Material") -> str:
    """Converts raw filenames or lowercase titles into natural spoken topic names."""
    topic = re.sub(r"\s+", " ", (raw_topic or "").strip())
    if not topic:
        return fallback

    # Strip trailing file extensions (e.g. '.pdf' or ' pdf')
    topic = re.sub(r"(?:\.(?:pdf|docx?|txt|md|pptx?|csv))+$", "", topic, flags=re.IGNORECASE).strip()
    topic = re.sub(r"(?:[\s_-]+(?:pdf|docx?|txt|md|pptx?))+$", "", topic, flags=re.IGNORECASE).strip()
    if "_" in topic or (topic == topic.lower() and "-" in topic):
        topic = re.sub(r"[_-]+", " ", topic)
    topic = re.sub(r"\s+", " ", topic).strip()
    if not topic:
        return fallback

    if topic == topic.lower():
        words = []
        for idx, tok in enumerate(topic.split(" ")):
            low = tok.lower()
            if low in _PRESERVED_UPPER_TOKENS:
                words.append(low.upper())
            elif idx > 0 and low in {"of", "and", "the", "in", "on", "for", "to", "a", "an"}:
                words.append(low)
            else:
                words.append(tok.capitalize())
        return " ".join(words)
    return topic


def _extract_preceding_stream_dict(data: bytes, stream_start: int) -> bytes:
    """Returns the PDF object dictionary bytes immediately preceding a `stream` keyword."""
    window = data[max(0, stream_start - 1536) : stream_start]
    last_endobj = window.rfind(b"endobj")
    if last_endobj != -1:
        window = window[last_endobj + 6 :]
    last_open = window.rfind(b"<<")
    last_close = window.rfind(b">>")
    if last_open != -1 and last_close > last_open:
        return window[last_open : last_close + 2]
    return window


def _classify_pdf_stream(dict_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """
    Classifies whether a PDF stream can be a text content stream and identifies its filter.
    Returns (is_candidate, filter_kind) where filter_kind is 'flate' or None (uncompressed).
    Rejects image streams, embedded fonts, metadata, XRef/ObjStm streams, and unsupported filters.
    """
    for pat in _NON_TEXT_STREAM_DICT_PATTERNS:
        if pat.search(dict_bytes):
            return False, None

    filter_match = re.search(rb"/Filter\s*(?:\[([^\]]+)\]|/([A-Za-z0-9]+))", dict_bytes)
    if not filter_match:
        return True, None

    if filter_match.group(2):
        filters = [filter_match.group(2)]
    else:
        filters = re.findall(rb"/([A-Za-z0-9]+)", filter_match.group(1) or b"")

    if not filters:
        return False, None

    for flt in filters:
        if flt in _UNSUPPORTED_FILTER_NAMES:
            return False, None
        if flt not in (b"FlateDecode", b"Fl"):
            return False, None

    return True, "flate"


_PDF_ARTIFACT_START_RE = re.compile(
    rb"/Artifact\b(?:(?!(?:BDC|BMC|EMC)).)*?/Subtype\s*/(?:Header|Footer|Watermark)\b(?:(?!(?:BDC|BMC|EMC)).)*?BDC",
    re.DOTALL,
)
_PDF_BDC_OR_EMC_RE = re.compile(rb"\b(?:BDC|BMC|EMC)\b")
_PDF_OP_TOKEN_RE = re.compile(
    rb"\[(?P<tj>(?:[^\[\]\\()]|\\.|(?:\((?:\\.|[^\\()])*\)))*)\]\s*TJ"
    rb"|(?P<lit>\((?:\\.|[^\\()])*\))\s*(?P<litop>Tj|'|\"(?=\s|$))"
    rb"|(?P<tx>-?\d+(?:\.\d+)?)\s+(?P<ty>-?\d+(?:\.\d+)?)\s+(?P<tdop>Td|TD)"
    rb"|(?P<tstar>T\*)"
    rb"|(?P<tm>-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?)\s+Tm",
    re.DOTALL,
)
_TJ_ITEM_RE = re.compile(rb"(?P<lit>\((?:\\.|[^\\()])*\))|(?P<num>-?\d+(?:\.\d+)?)")
_BOILERPLATE_LINE_RE = re.compile(
    r"^(?:provided\s+by\b.*\b(?:academic\s+center|university|college|20\d{2})\b|page\s+\d+(?:\s+of\s+\d+)?$)",
    re.IGNORECASE,
)


def _strip_pdf_artifact_blocks(block: bytes) -> bytes:
    """Removes /Artifact /Subtype /Header|Footer|Watermark BDC...EMC sections safely."""
    out_parts: List[bytes] = []
    pos = 0
    while pos < len(block):
        m = _PDF_ARTIFACT_START_RE.search(block, pos)
        if not m:
            out_parts.append(block[pos:])
            break
        out_parts.append(block[pos : m.start()])
        depth = 1
        scan = m.end()
        for bm in _PDF_BDC_OR_EMC_RE.finditer(block, scan):
            tok = bm.group(0)
            if tok in (b"BDC", b"BMC"):
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    scan = bm.end()
                    break
        else:
            scan = len(block)
        pos = scan
    return b"".join(out_parts)


def _decode_single_pdf_literal(literal_bytes: bytes) -> str:
    """Decodes one PDF literal string `(...)`, preserving internal spaces while rejecting binary control bytes."""
    s = literal_bytes[1:-1] if literal_bytes.startswith(b"(") and literal_bytes.endswith(b")") else literal_bytes
    s = s.replace(rb"\n", b"\n").replace(rb"\r", b"\r").replace(rb"\t", b" ")
    s = s.replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\")
    s = re.sub(rb"\\([0-7]{1,3})", lambda om: bytes([int(om.group(1), 8)]), s)

    if s.startswith(b"\xfe\xff"):
        try:
            decoded = s[2:].decode("utf-16-be", errors="strict")
        except UnicodeDecodeError:
            return ""
    else:
        try:
            decoded = s.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            if any(b < 0x20 and b not in (9, 10, 13) for b in s):
                return ""
            try:
                decoded = s.decode("cp1252", errors="strict")
            except UnicodeDecodeError:
                decoded = s.decode("latin-1", errors="strict")

    if any((ord(ch) < 32 and ch not in "\n\t\r") or (0x7F <= ord(ch) <= 0x9F) or ch == "\ufffd" for ch in decoded):
        return ""
    return "".join(ch for ch in decoded if ch.isprintable() or ch in "\n\t ")


def _decode_pdf_literal_string(raw: bytes) -> str:
    """Decodes PDF literal strings (...) into readable UTF-8/UTF-16BE/Western text, rejecting binary noise."""
    out: List[str] = []
    for m in re.finditer(rb"\((?:\\.|[^\\()])*\)", raw):
        decoded = _decode_single_pdf_literal(m.group(0))
        if decoded.strip():
            out.append(decoded)
    return " ".join(out)


def _extract_text_from_pdf_bt_block(block: bytes) -> str:
    """
    Extracts readable text from a PDF BT...ET block:
    - Excludes /Artifact Header/Footer/Watermark BDC...EMC blocks.
    - Interprets TJ kerning offsets (small offsets concatenate within a word; <= -120 inserts space).
    - Handles Tj, ', ", Td, TD, T*, and Tm positioning operators.
    """
    cleaned_block = _strip_pdf_artifact_blocks(block)
    buf: List[str] = []
    last_tm_y: Optional[float] = None

    def _append_space() -> None:
        if buf and not buf[-1].endswith((" ", "\n", "\t")):
            buf.append(" ")

    def _append_newline() -> None:
        if buf and not buf[-1].endswith("\n"):
            buf.append("\n")

    for m in _PDF_OP_TOKEN_RE.finditer(cleaned_block):
        if m.group("tj") is not None:
            tj_raw = m.group("tj")
            for item in _TJ_ITEM_RE.finditer(tj_raw):
                if item.group("lit") is not None:
                    piece = _decode_single_pdf_literal(item.group("lit"))
                    if piece:
                        buf.append(piece)
                elif item.group("num") is not None:
                    try:
                        kern = float(item.group("num"))
                    except ValueError:
                        continue
                    if kern <= -120.0:
                        _append_space()
        elif m.group("lit") is not None:
            op = m.group("litop")
            if op in (b"'", b'"'):
                _append_newline()
            piece = _decode_single_pdf_literal(m.group("lit"))
            if piece:
                buf.append(piece)
        elif m.group("tdop") is not None:
            try:
                tx = float(m.group("tx"))
                ty = float(m.group("ty"))
            except ValueError:
                continue
            if abs(ty) > 0.05:
                _append_newline()
            elif tx > 0.2:
                _append_space()
        elif m.group("tstar") is not None:
            _append_newline()
        elif m.group("tm") is not None:
            parts = m.group("tm").split()
            if len(parts) == 6:
                try:
                    tm_y = float(parts[5])
                except ValueError:
                    tm_y = None
                if tm_y is not None:
                    if last_tm_y is not None and abs(tm_y - last_tm_y) > 2.0:
                        _append_newline()
                    elif last_tm_y is not None:
                        _append_space()
                    last_tm_y = tm_y

    text = "".join(buf)
    lines = [
        re.sub(r" {2,}", " ", ln).strip()
        for ln in text.splitlines()
        if ln.strip() and not _BOILERPLATE_LINE_RE.match(ln.strip())
    ]
    return "\n".join(lines)


_OBJ_DEF_RE = re.compile(rb"(\d+)\s+\d+\s+obj\b(.*?)\bendobj", re.DOTALL)
_STREAM_IN_OBJ_RE = re.compile(rb"stream(?:\r\n|\r|\n)(.*?)[\r\n]*endstream", re.DOTALL)
_TM_XY_RE = re.compile(
    rb"-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+Tm"
)
_TD_XY_RE = re.compile(rb"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(?:Td|TD)\b")
_STANDALONE_PAGE_NUM_RE = re.compile(
    r"^(?:page\s+\d+(?:\s*(?:of|/)\s*\d+)?|[-–—]?\s*\d{1,4}\s*[-–—]?|\d{1,4}\s*/\s*\d{1,4})$",
    re.IGNORECASE,
)


def _inflate_pdf_stream(dict_bytes: bytes, raw_stream: bytes) -> Optional[bytes]:
    is_candidate, filter_kind = _classify_pdf_stream(dict_bytes)
    if not is_candidate:
        return None
    if filter_kind != "flate":
        return raw_stream
    for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
        try:
            return zlib.decompress(raw_stream.strip(), wbits)
        except Exception:
            continue
    return None


def _extract_pdf_stream_text_ordered(target: bytes) -> str:
    """
    Extracts readable text from a PDF content stream, preserving multi-column reading order
    and pipe-delimited table rows when text positioning (Tm/Td) coordinates are available.
    """
    bt_blocks = re.findall(rb"BT(.*?)ET", target, re.DOTALL)
    if not bt_blocks:
        if _PDF_TEXT_OPERATOR_RE.search(target):
            txt = _extract_text_from_pdf_bt_block(target)
            if len(txt.strip()) > 35 and is_plausible_source_sentence(txt):
                return txt.strip()
        return ""

    positioned: List[Tuple[Optional[float], Optional[float], int, str]] = []
    for idx, blk in enumerate(bt_blocks):
        txt = _extract_text_from_pdf_bt_block(blk).strip()
        if not txt or not is_plausible_source_sentence(txt):
            continue
        x_pos: Optional[float] = None
        y_pos: Optional[float] = None
        tm_m = _TM_XY_RE.search(blk)
        if tm_m:
            try:
                x_pos = float(tm_m.group(1))
                y_pos = float(tm_m.group(2))
            except ValueError:
                pass
        else:
            td_m = _TD_XY_RE.search(blk)
            if td_m:
                try:
                    x_pos = float(td_m.group(1))
                    y_pos = float(td_m.group(2))
                except ValueError:
                    pass
        positioned.append((x_pos, y_pos, idx, txt))

    if not positioned:
        return ""

    coords = [(x, y, idx, txt) for x, y, idx, txt in positioned if x is not None and y is not None]
    if len(coords) >= 4 and len(coords) == len(positioned):
        xs = sorted(c[0] for c in coords)
        # Detect clear 2-column split (gap >= 80pt)
        max_gap = 0.0
        split_x = None
        for i in range(len(xs) - 1):
            gap = xs[i + 1] - xs[i]
            if gap > max_gap:
                max_gap = gap
                split_x = (xs[i] + xs[i + 1]) / 2.0

        # Group same-Y items (table rows) vs distinct columns
        y_buckets: Dict[int, List[Tuple[float, str]]] = {}
        for x, y, _idx, txt in coords:
            yb = int(round(y / 4.0))
            y_buckets.setdefault(yb, []).append((x, txt))

        multi_col_rows = sum(1 for items in y_buckets.values() if len(items) >= 2)
        if max_gap >= 80.0 and split_x is not None and multi_col_rows >= 2:
            # Check if it's a table (short cells) or 2-column prose (longer lines)
            avg_len = sum(len(c[3]) for c in coords) / len(coords)
            if avg_len < 42:
                # Table layout: sort top-to-bottom (descending Y), join cells on same row with ' | '
                rows_out = []
                for yb in sorted(y_buckets.keys(), reverse=True):
                    cells = [t for _, t in sorted(y_buckets[yb], key=lambda item: item[0])]
                    rows_out.append(" | ".join(cells) if len(cells) > 1 else cells[0])
                return "\n".join(rows_out)
            else:
                # Multi-column prose: left column top-to-bottom, then right column top-to-bottom
                left = [c for c in coords if c[0] < split_x]
                right = [c for c in coords if c[0] >= split_x]
                left.sort(key=lambda c: (-c[1], c[0], c[2]))
                right.sort(key=lambda c: (-c[1], c[0], c[2]))
                return "\n".join([c[3] for c in left] + [c[3] for c in right])

    return "\n".join(item[3] for item in positioned)


def _extract_pdf_pages_native(data: bytes) -> Tuple[List[str], int]:
    """
    Maps /Type /Page objects to their /Contents streams to extract text per actual PDF page.
    Falls back to classified content streams when page-tree references are absent.
    Returns (pages_text_list, detected_page_count).
    """
    objects: Dict[int, bytes] = {}
    for m in _OBJ_DEF_RE.finditer(data):
        try:
            oid = int(m.group(1))
            objects[oid] = m.group(2)
        except ValueError:
            continue

    page_objs: List[Tuple[int, bytes]] = []
    for oid, body in objects.items():
        header = body.split(b"stream", 1)[0]
        if re.search(rb"/Type\s*/Page\b(?!s)", header):
            page_objs.append((oid, header))

    if page_objs:
        pages_out: List[str] = []
        for _oid, header in page_objs:
            content_ids: List[int] = []
            arr_m = re.search(rb"/Contents\s*\[([^\]]+)\]", header)
            if arr_m:
                content_ids = [int(x) for x in re.findall(rb"(\d+)\s+0\s+R", arr_m.group(1))]
            else:
                single_m = re.search(rb"/Contents\s+(\d+)\s+0\s+R", header)
                if single_m:
                    content_ids = [int(single_m.group(1))]

            page_parts: List[str] = []
            for cid in content_ids:
                c_body = objects.get(cid)
                if not c_body:
                    continue
                sm = _STREAM_IN_OBJ_RE.search(c_body)
                if not sm:
                    continue
                dict_bytes = c_body[: sm.start()]
                inflated = _inflate_pdf_stream(dict_bytes, sm.group(1))
                if inflated is None:
                    continue
                txt = _extract_pdf_stream_text_ordered(inflated)
                if txt.strip():
                    page_parts.append(txt.strip())

            pages_out.append("\n".join(page_parts).strip())
        return pages_out, len(page_objs)

    # Fallback: classified content streams without explicit /Page -> /Contents mapping
    stream_pattern = re.compile(rb"stream(?:\r\n|\r|\n)(.*?)[\r\n]*endstream", re.DOTALL)
    extracted_blocks: List[str] = []
    for m in stream_pattern.finditer(data):
        dict_bytes = _extract_preceding_stream_dict(data, m.start())
        inflated = _inflate_pdf_stream(dict_bytes, m.group(1))
        if inflated is None:
            continue
        txt = _extract_pdf_stream_text_ordered(inflated)
        if txt.strip():
            extracted_blocks.append(txt.strip())

    if not extracted_blocks:
        top_bt = re.findall(rb"BT(.*?)ET", data, re.DOTALL)
        top_parts = []
        for blk in top_bt:
            txt = _extract_text_from_pdf_bt_block(blk)
            if txt.strip() and is_plausible_source_sentence(txt):
                top_parts.append(txt.strip())
        if top_parts:
            extracted_blocks.append("\n".join(top_parts))

    return extracted_blocks, max(len(extracted_blocks), len(re.findall(rb"/Type\s*/Page\b(?!s)", data)))


def _page_needs_ocr(text: str) -> bool:
    s = (text or "").strip()
    if len(re.sub(r"\s+", "", s)) < 35:
        return True
    words = s.split()
    if len(words) < 5:
        return True
    return not is_plausible_source_chunk(s)


def _ocr_pdf_pages_winrt(data: bytes, page_numbers_1based: List[int]) -> Tuple[Dict[int, str], int, float, Optional[str]]:
    """
    Runs Windows WinRT PDF rendering + Windows.Media.Ocr.OcrEngine ONLY on specified 1-based pages.
    Returns (page_num -> ocr_text, total_pdf_pages, duration_sec, error_message_if_unavailable).
    """
    if os.name != "nt" or not data.startswith(b"%PDF") or not page_numbers_1based:
        return {}, 0, 0.0, "OCR unavailable in this environment."

    t0 = time.perf_counter()
    ps_script = r"""
param([string]$PdfPath, [string]$PagesCsv)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.DataWriter, Windows.Storage.Streams, ContentType=WindowsRuntime] | Out-Null

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
$asTaskAction = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0]
function AwaitOp($op, $resultType) {
    $t = $asTaskGeneric.MakeGenericMethod($resultType).Invoke($null, @($op))
    $t.Wait()
    return $t.Result
}
function AwaitAct($act) {
    $t = $asTaskAction.Invoke($null, @($act))
    $t.Wait()
}

$ocr = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (-not $ocr) {
    $enLang = New-Object Windows.Globalization.Language("en-US")
    $ocr = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($enLang)
}
if (-not $ocr) {
    Write-Output '{"error":"no_ocr_engine","pages":{},"page_count":0}'
    exit 0
}

$bytes = [System.IO.File]::ReadAllBytes($PdfPath)
$pdfRas = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
$dw = New-Object Windows.Storage.Streams.DataWriter($pdfRas)
$dw.WriteBytes($bytes)
$null = AwaitOp ($dw.StoreAsync()) ([uint32])
$null = AwaitOp ($dw.FlushAsync()) ([bool])
$dw.DetachStream() | Out-Null
$pdfRas.Seek(0)

$pdfDoc = AwaitOp ([Windows.Data.Pdf.PdfDocument]::LoadFromStreamAsync($pdfRas)) ([Windows.Data.Pdf.PdfDocument])
$totalPages = [int]$pdfDoc.PageCount
$targets = @()
if ($PagesCsv -eq "ALL") {
    for ($p = 1; $p -le $totalPages; $p++) { $targets += $p }
} else {
    foreach ($tok in ($PagesCsv -split ',')) {
        $n = 0
        if ([int]::TryParse($tok.Trim(), [ref]$n) -and $n -ge 1 -and $n -le $totalPages) { $targets += $n }
    }
}

$outMap = @{}
foreach ($pNum in $targets) {
    $page = $pdfDoc.GetPage([uint32]($pNum - 1))
    $imgRas = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
    $opts = New-Object Windows.Data.Pdf.PdfPageRenderOptions
    $opts.DestinationWidth = [uint32]([Math]::Min(2400, [Math]::Max(1200, $page.Size.Width * 2.0)))
    AwaitAct ($page.RenderToStreamAsync($imgRas, $opts))
    $imgRas.Seek(0)
    $dec = AwaitOp ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($imgRas)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $sbmp = AwaitOp ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $ocrRes = AwaitOp ($ocr.RecognizeAsync($sbmp)) ([Windows.Media.Ocr.OcrResult])
    $outMap["$pNum"] = [string]$ocrRes.Text
    $sbmp.Dispose()
    $imgRas.Dispose()
    $page.Dispose()
}
$pdfRas.Dispose()
$payload = @{ page_count = $totalPages; pages = $outMap } | ConvertTo-Json -Depth 4 -Compress
Write-Output ("OCR_JSON:" + $payload)
"""
    tmp_dir = tempfile.mkdtemp(prefix="brainova_ocr_")
    pdf_tmp = os.path.join(tmp_dir, "input.pdf")
    ps_tmp = os.path.join(tmp_dir, "run_ocr.ps1")
    try:
        with open(pdf_tmp, "wb") as pf:
            pf.write(data)
        with open(ps_tmp, "w", encoding="utf-8-sig") as sf:
            sf.write(ps_script)

        pages_csv = "ALL" if page_numbers_1based == [-1] else ",".join(str(p) for p in page_numbers_1based)
        timeout_sec = max(35, min(180, len(page_numbers_1based) * 15))
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_tmp, "-PdfPath", pdf_tmp, "-PagesCsv", pages_csv],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
        )
        dur = time.perf_counter() - t0
        for line in (proc.stdout or "").splitlines():
            if line.startswith("OCR_JSON:"):
                parsed = json.loads(line[len("OCR_JSON:") :])
                if parsed.get("error"):
                    return {}, int(parsed.get("page_count") or 0), dur, str(parsed["error"])
                pages_dict = {int(k): str(v or "") for k, v in (parsed.get("pages") or {}).items()}
                return pages_dict, int(parsed.get("page_count") or len(pages_dict)), dur, None
        return {}, 0, dur, (proc.stderr or "WinRT OCR produced no output.")[:240]
    except Exception as exc:
        return {}, 0, time.perf_counter() - t0, str(exc)[:240]
    finally:
        for fp in (pdf_tmp, ps_tmp):
            try:
                os.remove(fp)
            except OSError:
                pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass


def _merge_native_and_ocr(native_text: str, ocr_text: str) -> str:
    n_clean = normalize_text(native_text)
    o_clean = normalize_text(ocr_text)
    if not n_clean:
        return o_clean
    if not o_clean:
        return n_clean
    existing = {re.sub(r"\s+", " ", ln.strip().lower()) for ln in n_clean.splitlines() if ln.strip()}
    merged = [n_clean]
    for ln in o_clean.splitlines():
        key = re.sub(r"\s+", " ", ln.strip().lower())
        if key and key not in existing:
            existing.add(key)
            merged.append(ln.strip())
    return "\n".join(merged)


def clean_extracted_pages(pages: List[str]) -> List[str]:
    """
    Removes repeated headers/footers across >=3 pages, standalone page numbers,
    consecutive duplicate paragraphs, and joins hyphenated line wraps while preserving
    equations, tables, and Unicode educational text.
    """
    if not pages:
        return []
    first_lines = Counter()
    last_lines = Counter()
    split_pages: List[List[str]] = []
    for pg in pages:
        norm_pg = normalize_text(pg)
        lines = [ln.strip() for ln in norm_pg.splitlines() if ln.strip()]
        split_pages.append(lines)
        if len(pages) >= 3 and lines:
            if len(lines[0]) <= 90:
                first_lines[lines[0].lower()] += 1
            if len(lines[-1]) <= 90:
                last_lines[lines[-1].lower()] += 1

    repeated_hf = {
        k for k, cnt in first_lines.items() if cnt >= 3
    } | {
        k for k, cnt in last_lines.items() if cnt >= 3
    }

    cleaned_pages: List[str] = []
    for lines in split_pages:
        kept: List[str] = []
        for ln in lines:
            if _STANDALONE_PAGE_NUM_RE.match(ln):
                continue
            if ln.lower() in repeated_hf:
                continue
            if _BOILERPLATE_LINE_RE.match(ln):
                continue
            kept.append(ln)
        joined = "\n".join(kept)
        # Rejoin hyphenated words split across line breaks (e.g. "photo-\nsynthesis" -> "photosynthesis")
        joined = re.sub(r"([A-Za-z]{2,})-\n([a-z]{2,})", r"\1\2", joined)
        # Deduplicate consecutive identical paragraphs
        paras = [p.strip() for p in joined.split("\n\n") if p.strip()]
        dedup_paras: List[str] = []
        for p in paras:
            if not dedup_paras or dedup_paras[-1].lower() != p.lower():
                dedup_paras.append(p)
        cleaned_pages.append(normalize_text("\n\n".join(dedup_paras)))
    return cleaned_pages


def extract_pdf_with_diagnostics(data: bytes) -> Tuple[List[str], Optional[str], Dict[str, Any]]:
    """
    Extracts text per page from a PDF with intelligent per-page OCR fallback and structured diagnostics.
    """
    t0 = time.perf_counter()
    diag: Dict[str, Any] = {
        "file_type": ".pdf",
        "file_size": len(data),
        "page_count": 0,
        "pages_with_native_text": 0,
        "pages_requiring_ocr": 0,
        "pages_ocr_succeeded": 0,
        "ocr_duration_sec": 0.0,
        "extraction_duration_sec": 0.0,
        "errors": [],
    }

    if not data.startswith(b"%PDF"):
        diag["errors"].append("invalid_pdf_header")
        diag["extraction_duration_sec"] = round(time.perf_counter() - t0, 3)
        return [], "We couldn't read this document. Please upload a valid PDF, DOCX or supported document.", diag

    native_pages: List[str] = []
    detected_page_count = 0

    try:
        import pypdf  # type: ignore
        import io
        reader = pypdf.PdfReader(io.BytesIO(data))
        detected_page_count = len(reader.pages)
        for page in reader.pages:
            native_pages.append((page.extract_text() or "").strip())
    except Exception:
        native_pages, detected_page_count = _extract_pdf_pages_native(data)

    if detected_page_count == 0 and not native_pages:
        # Valid %PDF header; ask WinRT PdfDocument for actual page count & OCR
        ocr_map, winrt_pages, ocr_dur, ocr_err = _ocr_pdf_pages_winrt(data, [-1])
        diag["ocr_duration_sec"] = round(ocr_dur, 3)
        if winrt_pages > 0:
            diag["page_count"] = winrt_pages
            diag["pages_requiring_ocr"] = winrt_pages
            final_pages = [
                normalize_text(ocr_map.get(p, ""))
                for p in range(1, winrt_pages + 1)
                if ocr_map.get(p, "").strip()
            ]
            diag["pages_ocr_succeeded"] = len(final_pages)
            diag["extraction_duration_sec"] = round(time.perf_counter() - t0, 3)
            if final_pages:
                return clean_extracted_pages(final_pages), None, diag
            diag["errors"].append("scanned_pdf_no_ocr_text")
            return (
                [],
                "Your document appears to contain scanned pages. Text extraction could not read them. "
                "Please use a searchable PDF or upload a document with readable text.",
                diag,
            )
        diag["errors"].append(f"corrupt_or_unreadable_pdf:{ocr_err or 'no_pages'}")
        diag["extraction_duration_sec"] = round(time.perf_counter() - t0, 3)
        return [], "We couldn't read this document. Please upload a valid PDF, DOCX or supported document.", diag

    diag["page_count"] = max(detected_page_count, len(native_pages))
    pages_to_ocr: List[int] = []
    for idx, txt in enumerate(native_pages, start=1):
        if _page_needs_ocr(txt):
            pages_to_ocr.append(idx)
        else:
            diag["pages_with_native_text"] += 1

    diag["pages_requiring_ocr"] = len(pages_to_ocr)
    ocr_results: Dict[int, str] = {}
    if pages_to_ocr:
        ocr_results, winrt_pages, ocr_dur, ocr_err = _ocr_pdf_pages_winrt(data, pages_to_ocr)
        diag["ocr_duration_sec"] = round(ocr_dur, 3)
        if winrt_pages > diag["page_count"]:
            diag["page_count"] = winrt_pages
        if ocr_err:
            diag["errors"].append(f"ocr_limitation:{ocr_err}")

    merged_pages: List[str] = []
    for idx in range(1, diag["page_count"] + 1):
        nat = native_pages[idx - 1] if idx - 1 < len(native_pages) else ""
        ocr = ocr_results.get(idx, "")
        if ocr.strip() and is_plausible_source_chunk(ocr):
            diag["pages_ocr_succeeded"] += 1
        combined = _merge_native_and_ocr(nat, ocr)
        if combined.strip() and is_plausible_source_chunk(combined):
            merged_pages.append(combined)

    cleaned = [p for p in clean_extracted_pages(merged_pages) if p.strip()]
    diag["extraction_duration_sec"] = round(time.perf_counter() - t0, 3)
    total_words = sum(len(p.split()) for p in cleaned)
    if cleaned and total_words >= 6:
        return cleaned, None, diag

    if pages_to_ocr:
        diag["errors"].append("scanned_pdf_ocr_failed_or_empty")
        return (
            [],
            "Your document appears to contain scanned pages. Text extraction could not read them. "
            "Please use a searchable PDF or upload a document with readable text.",
            diag,
        )

    diag["errors"].append("pdf_no_readable_text")
    return (
        [],
        "This document does not contain enough readable educational content to create a reliable Video Overview.",
        diag,
    )


def extract_text_from_pdf_bytes(data: bytes) -> Tuple[List[str], Optional[str]]:
    """
    Extracts text per page from a PDF file using native page parsing + selective WinRT OCR.
    """
    pages, err, _diag = extract_pdf_with_diagnostics(data)
    return pages, err


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_docx_sections(raw_bytes: bytes) -> Tuple[List[Tuple[int, str, str]], str, Optional[str]]:
    import io
    try:
        import docx  # type: ignore
        doc = docx.Document(io.BytesIO(raw_bytes))
        blocks: List[str] = []
        for p in doc.paragraphs:
            if p.text.strip():
                blocks.append(p.text.strip())
        for tbl in doc.tables:
            for row in tbl.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    blocks.append(" | ".join(cells))
        full = normalize_text("\n\n".join(blocks))
        if not full:
            return [], "", "This document does not contain enough readable educational content."
        return [(1, full.splitlines()[0][:80], full)], full, None
    except ImportError:
        pass
    except Exception:
        return [], "", "We couldn't read this document. Please upload a valid PDF, DOCX or supported document."

    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            if "word/document.xml" not in zf.namelist():
                return [], "", "We couldn't read this document. Please upload a valid PDF, DOCX or supported document."
            root = ET.fromstring(zf.read("word/document.xml"))
    except Exception:
        return [], "", "We couldn't read this document. Please upload a valid PDF, DOCX or supported document."

    w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    blocks = []
    body = root.find(f"{w_ns}body")
    if body is not None:
        for child in body:
            if child.tag == f"{w_ns}p":
                txt = "".join(t.text or "" for t in child.iter(f"{w_ns}t")).strip()
                if txt:
                    blocks.append(txt)
            elif child.tag == f"{w_ns}tbl":
                for tr in child.findall(f"{w_ns}tr"):
                    row_cells = []
                    for tc in tr.findall(f"{w_ns}tc"):
                        c_txt = " ".join(
                            "".join(t.text or "" for t in p.iter(f"{w_ns}t")).strip()
                            for p in tc.findall(f"{w_ns}p")
                        ).strip()
                        if c_txt:
                            row_cells.append(c_txt)
                    if row_cells:
                        blocks.append(" | ".join(row_cells))

    full = normalize_text("\n\n".join(blocks))
    if not full:
        return [], "", "This document does not contain enough readable educational content."
    sections: List[Tuple[int, str, str]] = []
    cur_words: List[str] = []
    cur_paras: List[str] = []
    page_num = 1
    for para in full.split("\n\n"):
        cur_paras.append(para)
        cur_words.extend(para.split())
        if len(cur_words) >= 260:
            sections.append((page_num, cur_paras[0].splitlines()[0][:75], "\n\n".join(cur_paras)))
            page_num += 1
            cur_words = []
            cur_paras = []
    if cur_paras:
        sections.append((page_num, cur_paras[0].splitlines()[0][:75], "\n\n".join(cur_paras)))
    return sections, full, None


def _extract_pptx_sections(raw_bytes: bytes) -> Tuple[List[Tuple[int, str, str]], str, Optional[str]]:
    import io
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            slide_files = []
            for name in zf.namelist():
                m = re.match(r"^ppt/slides/slide(\d+)\.xml$", name)
                if m:
                    slide_files.append((int(m.group(1)), name))
            if not slide_files:
                return [], "", "We couldn't read this document. Please upload a valid PDF, DOCX or supported document."
            slide_files.sort(key=lambda item: item[0])

            a_ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
            sections: List[Tuple[int, str, str]] = []
            for slide_num, name in slide_files:
                root = ET.fromstring(zf.read(name))
                lines = []
                for p in root.iter(f"{a_ns}p"):
                    txt = "".join(t.text or "" for t in p.iter(f"{a_ns}t")).strip()
                    if txt:
                        lines.append(txt)
                # Also include speaker notes if present
                notes_name = f"ppt/notesSlides/notesSlide{slide_num}.xml"
                if notes_name in zf.namelist():
                    n_root = ET.fromstring(zf.read(notes_name))
                    for p in n_root.iter(f"{a_ns}p"):
                        nt = "".join(t.text or "" for t in p.iter(f"{a_ns}t")).strip()
                        if nt and not nt.isdigit():
                            lines.append(nt)
                slide_text = normalize_text("\n".join(lines))
                if slide_text:
                    sec_title = f"Slide {slide_num}: {slide_text.splitlines()[0][:70]}"
                    sections.append((slide_num, sec_title, slide_text))

            if not sections:
                return [], "", "This document does not contain enough readable educational content."
            return sections, "\n\n".join(s[2] for s in sections), None
    except Exception:
        return [], "", "We couldn't read this document. Please upload a valid PDF, DOCX or supported document."


def extract_document_content_with_diagnostics(
    file_path: str, filename: str
) -> Tuple[List[Tuple[int, str, str]], str, Optional[str], Dict[str, Any]]:
    """
    Returns (sections, full_extracted_text, error_message, diagnostics_dict).
    """
    t0 = time.perf_counter()
    ext = os.path.splitext(filename)[1].lower()
    diag: Dict[str, Any] = {
        "file_type": ext,
        "file_size": 0,
        "page_count": 0,
        "pages_with_native_text": 0,
        "pages_requiring_ocr": 0,
        "pages_ocr_succeeded": 0,
        "total_extracted_chars": 0,
        "valid_paragraphs": 0,
        "extraction_duration_sec": 0.0,
        "ocr_duration_sec": 0.0,
        "errors": [],
    }
    if ext not in SUPPORTED_EXTENSIONS:
        diag["errors"].append(f"unsupported_extension:{ext}")
        return [], "", f"Unsupported file format '{ext}'. Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS.keys()))}", diag

    if not os.path.exists(file_path):
        diag["errors"].append("file_missing")
        return [], "", "Uploaded file could not be found on disk.", diag

    with open(file_path, "rb") as f:
        raw_bytes = f.read()

    diag["file_size"] = len(raw_bytes)
    if len(raw_bytes) == 0:
        diag["errors"].append("empty_file")
        return [], "", "The uploaded file is empty (0 bytes).", diag

    if ext == ".pdf":
        pages, err, pdf_diag = extract_pdf_with_diagnostics(raw_bytes)
        diag.update(pdf_diag)
        if err:
            return [], "", err, diag
        structured_pages: List[Tuple[int, str, str]] = []
        for idx, p_text in enumerate(pages, start=1):
            first_line = p_text.split("\n")[0][:80].strip() or f"Page {idx}"
            structured_pages.append((idx, first_line, p_text))
        full_text = "\n\n".join(p[2] for p in structured_pages)
        diag["total_extracted_chars"] = len(full_text)
        diag["valid_paragraphs"] = len([p for p in full_text.split("\n\n") if p.strip()])
        return structured_pages, full_text, None, diag

    if ext == ".docx":
        sections, full_text, err = _extract_docx_sections(raw_bytes)
        diag["extraction_duration_sec"] = round(time.perf_counter() - t0, 3)
        diag["page_count"] = len(sections)
        diag["pages_with_native_text"] = len(sections)
        diag["total_extracted_chars"] = len(full_text)
        diag["valid_paragraphs"] = len([p for p in full_text.split("\n\n") if p.strip()])
        if err:
            diag["errors"].append("docx_extraction_failed")
        return sections, full_text, err, diag

    if ext == ".pptx":
        sections, full_text, err = _extract_pptx_sections(raw_bytes)
        diag["extraction_duration_sec"] = round(time.perf_counter() - t0, 3)
        diag["page_count"] = len(sections)
        diag["pages_with_native_text"] = len(sections)
        diag["total_extracted_chars"] = len(full_text)
        diag["valid_paragraphs"] = len([p for p in full_text.split("\n\n") if p.strip()])
        if err:
            diag["errors"].append("pptx_extraction_failed")
        return sections, full_text, err, diag

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
        diag["errors"].append("empty_text_content")
        diag["extraction_duration_sec"] = round(time.perf_counter() - t0, 3)
        return [], "", "This document does not contain enough readable educational content.", diag

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

    diag["extraction_duration_sec"] = round(time.perf_counter() - t0, 3)
    diag["page_count"] = len(sections)
    diag["pages_with_native_text"] = len(sections)
    diag["total_extracted_chars"] = len(cleaned)
    diag["valid_paragraphs"] = len([p for p in cleaned.split("\n\n") if p.strip()])
    return sections, cleaned, None, diag


def extract_document_content(file_path: str, filename: str) -> Tuple[List[Tuple[int, str, str]], str, Optional[str]]:
    """
    Returns (list of (page_number, section_title, page_text), full_extracted_text, error_message)
    """
    sections, full_text, err, _diag = extract_document_content_with_diagnostics(file_path, filename)
    return sections, full_text, err


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

    sections, full_text, err, diag = extract_document_content_with_diagnostics(file_path, filename)
    if err or not full_text.strip():
        err_msg = err or "This document does not contain enough readable educational content."
        diag["source_id"] = source_id
        diag["generated_chunks"] = 0
        diag["persisted_chunks"] = 0
        _DOC_LOGGER.info("extraction_diagnostics=%s", json.dumps(diag, sort_keys=True))
        conn.execute(
            "UPDATE sources SET status = 'error', error_message = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (err_msg, utc_now(), source_id, user_id),
        )
        return conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()

    chunks = chunk_document_sections(sections)
    conn.execute("DELETE FROM source_chunks WHERE source_id = ? AND user_id = ?", (source_id, user_id))

    persisted_count = 0
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
        persisted_count += 1

    diag["source_id"] = source_id
    diag["generated_chunks"] = len(chunks)
    diag["persisted_chunks"] = persisted_count
    _DOC_LOGGER.info("extraction_diagnostics=%s", json.dumps(diag, sort_keys=True))

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
        "pdf", "audio", "video", "overview", "study", "notes", "document", "source",
    }
    tokens = re.findall(r"[^\W\d_]{2,}|[a-zA-Z0-9_+#.-]{2,}", (text or "").lower(), re.UNICODE)
    return [t for t in tokens if t not in stop_words]


def _section_group_key(ch: Dict[str, Any]) -> Tuple[str, str]:
    sid = str(ch.get("source_id") or "")
    sec = str(ch.get("section_title") or "").strip()
    if sec and is_plausible_source_sentence(sec):
        # Group by Unit/Chapter prefix if present, else normalized section title
        m = re.match(r"^(unit\s*\d+|chapter\s*\d+|\d+\.\d+)", sec, re.IGNORECASE)
        if m:
            return (sid, m.group(1).lower())
        return (sid, sec[:40].lower())
    page = int(ch.get("page_number") or 1)
    return (sid, f"page_win_{(page - 1) // 4}")


def retrieve_relevant_chunks(
    conn,
    user_id: str,
    source_ids: Optional[List[str]],
    query: str,
    top_k: int = 6,
) -> List[Dict[str, Any]]:
    """
    Retrieves authorized, quality-validated source chunks owned by `user_id`
    ranked by BM25 lexical relevance with multi-section coherence boosting.
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

    raw_chunks = conn.execute(sql, params).fetchall()
    if not raw_chunks:
        return []

    # Filter out legacy corrupted binary/font/image chunks before ranking
    all_chunks = [dict(ch) for ch in raw_chunks if is_plausible_source_chunk(ch["content"])]
    if not all_chunks:
        return []

    query_tokens = _tokenize_for_search(query)
    if not query_tokens:
        return all_chunks[:top_k]

    # Compute IDF across clean chunks
    N = len(all_chunks)
    doc_tokens_list: List[List[str]] = []
    sec_tokens_list: List[set] = []
    for ch in all_chunks:
        sec_clean = ch["section_title"] if is_plausible_source_sentence(ch.get("section_title", "")) else ""
        doc_tokens_list.append(_tokenize_for_search(ch["content"] + " " + sec_clean))
        sec_tokens_list.append(set(_tokenize_for_search(sec_clean)))

    df: Counter = Counter()
    for d_tokens in doc_tokens_list:
        for tok in set(d_tokens):
            df[tok] += 1

    avgdl = max(1.0, sum(len(dt) for dt in doc_tokens_list) / N)
    k1 = 1.5
    b = 0.75

    base_scores: List[float] = []
    for ch, d_tokens, s_tokens in zip(all_chunks, doc_tokens_list, sec_tokens_list):
        tf = Counter(d_tokens)
        dl = len(d_tokens)
        score = 0.0
        for q_tok in query_tokens:
            if q_tok in tf:
                idf = math.log(1.0 + (N - df[q_tok] + 0.5) / (df[q_tok] + 0.5))
                freq = tf[q_tok]
                denom = freq + k1 * (1.0 - b + b * (dl / avgdl))
                score += idf * ((freq * (k1 + 1.0)) / denom)
                if q_tok in s_tokens:
                    score += 0.8
            elif len(q_tok) >= 4:
                # Bounded prefix-stem match only (prevents "war" matching "towards"/"forward")
                for dt in set(d_tokens):
                    if dt.startswith(q_tok) and len(dt) <= len(q_tok) + 4:
                        score += 0.15
                        break
        base_scores.append(score)

    global_max = max(base_scores) if base_scores else 0.0
    if global_max <= 0.0:
        return all_chunks[:top_k]

    # Intelligent multi-section coherence: preserve all sections strongly matching the query
    sec_max: Dict[Tuple[str, str], float] = {}
    sec_keys = [_section_group_key(ch) for ch in all_chunks]
    for key, sc in zip(sec_keys, base_scores):
        if sc > sec_max.get(key, 0.0):
            sec_max[key] = sc

    relevant_threshold = 0.45 * global_max
    scored: List[Tuple[float, int, Dict[str, Any]]] = []
    for idx, (ch, sc, key) in enumerate(zip(all_chunks, base_scores, sec_keys)):
        s_peak = sec_max.get(key, 0.0)
        if s_peak >= relevant_threshold:
            final_score = sc + (0.30 * s_peak if sc > 0 else 0.12 * s_peak)
        else:
            final_score = sc * 0.4
        scored.append((final_score, -idx, ch))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored[:top_k]]


def diagnose_and_recover_source_chunks(
    conn,
    user_id: str,
    source_ids: Optional[List[str]],
    query: str,
    top_k: int = 60,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Retrieves relevant source chunks with ownership verification, structured diagnostics,
    and transparent recovery for legacy corrupt chunks or retrieval mismatches.
    Never invents facts or lowers quality thresholds.
    """
    chunks = retrieve_relevant_chunks(conn, user_id, source_ids, query, top_k=top_k)
    if chunks:
        _DOC_LOGGER.info(
            "retrieval_diagnostics=%s",
            json.dumps(
                {
                    "source_ids": list(source_ids or []),
                    "retrieved_chunks": len(chunks),
                    "recovery_used": False,
                },
                sort_keys=True,
            ),
        )
        return chunks, {"status": "ok", "retrieved_chunks": len(chunks), "retryable": False}

    if not source_ids:
        return [], {
            "status": "insufficient_source_evidence",
            "error_code": "insufficient_source_evidence",
            "retryable": False,
            "user_message": "This document does not contain enough readable educational content to create a reliable Video Overview.",
        }

    placeholders = ",".join("?" for _ in source_ids)
    owned_rows = conn.execute(
        f"SELECT id, title, original_filename, file_path, file_type, status, error_message FROM sources WHERE user_id = ? AND id IN ({placeholders})",
        [user_id, *source_ids],
    ).fetchall()
    if not owned_rows:
        return [], {
            "status": "unauthorized_source",
            "error_code": "unauthorized_source",
            "retryable": False,
            "user_message": "The selected source document could not be accessed.",
        }

    # Case 5: Clean chunks exist in DB (even if status wasn't 'ready' or query didn't match)
    raw_rows = conn.execute(
        f"""
        SELECT c.id, c.source_id, c.chunk_index, c.page_number, c.section_title, c.content,
               s.title AS source_title, s.original_filename
        FROM source_chunks c
        JOIN sources s ON s.id = c.source_id
        WHERE c.user_id = ? AND s.user_id = ? AND s.status = 'ready' AND c.source_id IN ({placeholders})
        ORDER BY c.source_id, c.chunk_index
        """,
        [user_id, user_id, *source_ids],
    ).fetchall()
    clean_fallback = [dict(r) for r in raw_rows if is_plausible_source_chunk(r["content"])]
    if clean_fallback:
        return clean_fallback[:top_k], {
            "status": "ok",
            "recovery_used": "ordered_clean_chunk_fallback",
            "retrieved_chunks": min(len(clean_fallback), top_k),
            "retryable": False,
        }

    # Case 2 / Legacy corrupt chunks: Re-extract from original file on disk using upgraded PDF/OCR/DOCX/PPTX pipeline
    last_error_msg = ""
    for src in owned_rows:
        fp = src["file_path"] if isinstance(src, dict) else src[3]
        fn = src["original_filename"] if isinstance(src, dict) else src[2]
        sid = src["id"] if isinstance(src, dict) else src[0]
        if fp and os.path.exists(fp):
            updated = process_and_index_source(conn, sid, user_id, fp, fn or os.path.basename(fp))
            u_err = updated["error_message"] if isinstance(updated, dict) else ""
            if u_err:
                last_error_msg = u_err

    recovered = retrieve_relevant_chunks(conn, user_id, source_ids, query, top_k=top_k)
    if recovered:
        _DOC_LOGGER.info(
            "retrieval_diagnostics=%s",
            json.dumps(
                {
                    "source_ids": list(source_ids),
                    "retrieved_chunks": len(recovered),
                    "recovery_used": "reprocessed_with_ocr_or_parser",
                },
                sort_keys=True,
            ),
        )
        return recovered, {
            "status": "ok",
            "recovery_used": "reprocessed_with_ocr_or_parser",
            "retrieved_chunks": len(recovered),
            "retryable": False,
        }

    msg_lower = last_error_msg.lower()
    if "scanned" in msg_lower:
        code = "scanned_pdf_ocr_unavailable"
        user_msg = (
            "Your document appears to contain scanned pages. Text extraction could not read them. "
            "Please use a searchable PDF or upload a document with readable text."
        )
    elif "couldn't read" in msg_lower or "invalid" in msg_lower or "corrupt" in msg_lower:
        code = "corrupt_document"
        user_msg = "We couldn't read this document. Please upload a valid PDF, DOCX or supported document."
    else:
        code = "insufficient_source_evidence"
        user_msg = (
            "This document does not contain enough readable educational content to create a reliable Video Overview."
        )

    _DOC_LOGGER.warning(
        "retrieval_diagnostics=%s",
        json.dumps(
            {
                "source_ids": list(source_ids),
                "retrieved_chunks": 0,
                "error_code": code,
            },
            sort_keys=True,
        ),
    )
    return [], {
        "status": code,
        "error_code": code,
        "retryable": False,
        "user_message": user_msg,
    }


