"""
BRAINOVA AI Studio — Shared Source-Grounded Generation Pipeline (Cycle 1)
========================================================================
Provides a unified, domain-neutral, source-grounded generation architecture for
the seven non-audio/non-video AI Studio tools:
  1. slide_deck
  2. mind_map
  3. study_guide
  4. flashcards
  5. quiz
  6. infographic
  7. data_table

Pipeline stages:
  1. Validate & filter clean source chunks (preserving source_id, title, page_number, section_title).
  2. Build a domain-neutral evidence & concept representation (definitions, mechanisms,
     comparisons, quantitative facts, structured rows, source references).
  3. Select task-specific JSON schema & prompt; call configured LLM provider via call_llm_json
     when an API key is configured.
  4. Validate factual claims, structure, coverage, and source references; conservatively
     repair malformed LLM output or fall back to a domain-neutral source-grounded builder
     (never injecting unrelated CS/engineering boilerplate).
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple


class StudioGenerationError(Exception):
    """Structured error raised when reliable source-grounded generation is impossible."""

    def __init__(self, message: str, code: str = "studio_generation_error", status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


# Discourse markers / weak starters that must never be used as standalone concept titles
_WEAK_CONCEPT_PREFIXES = {
    "however", "therefore", "moreover", "furthermore", "additionally", "meanwhile",
    "consequently", "nevertheless", "nonetheless", "unlike", "although", "because",
    "since", "while", "when", "where", "this", "these", "that", "those", "it", "they",
    "for example", "in contrast", "on the other hand", "in addition", "as a result",
    "in", "on", "at", "by", "for", "to", "from", "the", "a", "an", "of",
}


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        norm = re.sub(r"\s+", " ", item.strip().lower())
        if norm and norm not in seen:
            seen.add(norm)
            out.append(item.strip())
    return out


def _split_clean_sentences(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", (text or "").replace("\r", " ")).strip()
    if not cleaned:
        return []
    raw_parts = re.split(r"(?<=[.!?])\s+", cleaned)
    sentences: List[str] = []
    for part in raw_parts:
        s = part.strip(" -*\t")
        if len(s) < 25:
            continue
        # Reject obvious extraction garbage (too many non-alphanumeric symbols)
        alnum = sum(1 for ch in s if ch.isalnum())
        if alnum < len(s) * 0.45:
            continue
        sentences.append(s)
    return sentences


def _extract_concept_label(sentence: str, fallback: str = "Core Concept") -> str:
    """Derives a clean, domain-neutral concept label from a sentence without discourse markers."""
    s = _clean_text(sentence)
    if not s:
        return fallback

    # Check "X is/are/refers to/means/consists of ..." definition pattern
    def_match = re.match(
        r"^([A-Z][A-Za-z0-9\s\-/()]{2,55}?)\s+(?:is|are|refers to|means|represents|consists of|involves|produces|converts)\b",
        s,
    )
    if def_match:
        cand = def_match.group(1).strip(" ,;:-")
        if cand.lower() not in _WEAK_CONCEPT_PREFIXES and len(cand.split()) <= 7:
            return cand

    # Check "Title: description" pattern
    colon_match = re.match(r"^([A-Za-z0-9\s\-/()]{3,50}):\s+", s)
    if colon_match:
        cand = colon_match.group(1).strip()
        if cand.lower() not in _WEAK_CONCEPT_PREFIXES and len(cand.split()) <= 7:
            return cand

    # Otherwise extract capitalized/technical noun phrases or first meaningful words
    words = [w.strip(",.;:()[]{}") for w in s.split()]
    filtered: List[str] = []
    for w in words:
        if not filtered and w.lower() in _WEAK_CONCEPT_PREFIXES:
            continue
        if w:
            filtered.append(w)
        if len(filtered) >= 5:
            break
    label = " ".join(filtered).strip(" ,;:-")
    return label if len(label) >= 3 else fallback


def _classify_fact(sentence: str) -> str:
    low = sentence.lower()
    if any(k in low for k in (" is ", " are ", " defined as ", " refers to ", " means ")):
        return "Definition"
    if any(k in low for k in ("causes", "produces", "leads to", "results in", "converts", "reduces", "oxidizes", "regulates", "triggers", "increases", "decreases")):
        return "Mechanism"
    if any(k in low for k in ("whereas", "unlike", "compared to", "in contrast", "difference between", "versus", "rather than")):
        return "Comparison"
    if re.search(r"\b\d+(?:\.\d+)?\s*(?:%|kg|g|mg|ml|l|km|m|cm|mm|ms|s|min|hr|hours|years|atp|mv|kb|mb|gb|usd|\$)\b", low):
        return "Quantitative"
    return "Key Evidence"


def _extract_structured_rows_from_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detects markdown/pipe/tab/colon structured data rows in source chunks."""
    rows: List[Dict[str, Any]] = []
    for ch in chunks:
        src_title = _clean_text(ch.get("source_title") or "Source")
        page = int(ch.get("page_number") or 1)
        lines = (ch.get("content") or "").splitlines()
        for line in lines:
            raw = line.strip()
            if not raw or set(raw) <= {"|", "-", ":", " ", "+"}:
                continue
            # Pipe-delimited table row
            if "|" in raw and raw.count("|") >= 2:
                parts = [p.strip() for p in raw.strip("|").split("|")]
                parts = [p for p in parts if p]
                if len(parts) >= 2:
                    rows.append({
                        "cells": parts,
                        "source_title": src_title,
                        "page_number": page,
                        "origin": "extracted_table",
                    })
                continue
            # Tab-delimited row
            if "\t" in raw:
                parts = [p.strip() for p in raw.split("\t") if p.strip()]
                if len(parts) >= 2:
                    rows.append({
                        "cells": parts,
                        "source_title": src_title,
                        "page_number": page,
                        "origin": "extracted_table",
                    })
                continue
            # Key: Value structured line or inline sentence-level Key: Value pair
            kv = re.match(r"^([A-Za-z0-9\s\-/()]{3,45}):\s+(.{2,180})$", raw)
            if kv:
                rows.append({
                    "cells": [kv.group(1).strip(), kv.group(2).strip()],
                    "source_title": src_title,
                    "page_number": page,
                    "origin": "extracted_key_value",
                })
                continue
            for seg in re.split(r"(?<=[.!?])\s+", raw):
                seg_clean = seg.strip()
                kv_seg = re.match(r"^([A-Za-z][A-Za-z0-9\s\-/()]{2,45}):\s+(.{2,180})$", seg_clean)
                if kv_seg:
                    rows.append({
                        "cells": [kv_seg.group(1).strip(), kv_seg.group(2).strip()],
                        "source_title": src_title,
                        "page_number": page,
                        "origin": "extracted_key_value",
                    })
    return rows


def build_studio_evidence_model(
    chunks: List[Dict[str, Any]],
    config: Dict[str, Any],
    is_plausible_chunk_fn: Optional[Callable[[str], bool]] = None,
) -> Dict[str, Any]:
    """
    Builds a domain-neutral evidence and concept model from retrieved source chunks.
    Preserves source_id, source_title, page_number, and section_title for every claim.
    """
    clean_chunks = [
        ch for ch in (chunks or [])
        if (is_plausible_chunk_fn(ch.get("content", "")) if is_plausible_chunk_fn else bool(_clean_text(ch.get("content"))))
    ]

    refs: List[Dict[str, Any]] = []
    seen_refs = set()
    fact_items: List[Dict[str, Any]] = []
    seen_fact_texts = set()
    context_blocks: List[str] = []
    total_ctx_chars = 0
    max_ctx_chars = 18000

    for idx, ch in enumerate(clean_chunks, start=1):
        src_id = str(ch.get("source_id") or "")
        src_title = _clean_text(ch.get("source_title") or "Selected Source")
        page = int(ch.get("page_number") or 1)
        sec = _clean_text(ch.get("section_title") or f"Page {page}")
        ref_key = (src_id, page, sec)
        if ref_key not in seen_refs:
            seen_refs.add(ref_key)
            refs.append({
                "source_id": src_id,
                "title": src_title,
                "page_number": page,
                "section_title": sec,
            })

        content = _clean_text(ch.get("content"))
        if total_ctx_chars < max_ctx_chars and content:
            block = f"[Excerpt #{idx} | source_id={src_id} | Source: {src_title} | Page {page} | {sec}]\n{content[:2200]}"
            context_blocks.append(block)
            total_ctx_chars += len(block)

        for sent in _split_clean_sentences(ch.get("content", "")):
            norm = sent.lower()
            if norm in seen_fact_texts:
                continue
            seen_fact_texts.add(norm)
            fact_items.append({
                "text": sent,
                "label": _extract_concept_label(sent),
                "category": _classify_fact(sent),
                "source_id": src_id,
                "source_title": src_title,
                "page_number": page,
                "section_title": sec,
            })

    topic_hint = _clean_text(config.get("topic") or config.get("title") or "")
    if not topic_hint:
        if refs:
            topic_hint = refs[0]["title"]
        elif fact_items:
            topic_hint = fact_items[0]["label"]
        else:
            topic_hint = "Study Topic"

    structured_rows = _extract_structured_rows_from_chunks(clean_chunks)
    quantitative_facts = [f for f in fact_items if f["category"] == "Quantitative"]
    definitions = [f for f in fact_items if f["category"] == "Definition"]
    mechanisms = [f for f in fact_items if f["category"] == "Mechanism"]
    comparisons = [f for f in fact_items if f["category"] == "Comparison"]

    return {
        "topic": topic_hint,
        "clean_chunks": clean_chunks,
        "source_references": refs,
        "fact_items": fact_items,
        "definitions": definitions,
        "mechanisms": mechanisms,
        "comparisons": comparisons,
        "quantitative_facts": quantitative_facts,
        "structured_rows": structured_rows,
        "context_text": "\n\n".join(context_blocks),
        "has_sources": len(clean_chunks) > 0 and len(fact_items) > 0,
    }


def _wrap_untrusted_context(evidence: Dict[str, Any]) -> str:
    if not evidence["context_text"]:
        return f"Topic: {evidence['topic']}\n(No uploaded source passages were provided.)"
    return (
        "<untrusted_source_material>\n"
        f"{evidence['context_text']}\n"
        "</untrusted_source_material>"
    )


def _format_ref_citation(item: Dict[str, Any]) -> str:
    return f"{item.get('source_title', 'Source')} (p.{item.get('page_number', 1)})"


def _ensure_source_evidence_if_ids_given(
    source_ids: Optional[List[str]],
    evidence: Dict[str, Any],
) -> None:
    if source_ids and not evidence["clean_chunks"]:
        raise StudioGenerationError(
            "Insufficient clean source evidence: the selected source documents contain no readable passages.",
            code="insufficient_source_evidence",
            status_code=422,
        )


# ============================================================================
# A. SLIDE DECK
# ============================================================================
def generate_slide_deck_grounded(
    chunks: List[Dict[str, Any]],
    config: Dict[str, Any],
    user_prefs: Optional[Dict[str, Any]],
    call_llm_json_fn: Callable[..., Tuple[Optional[Any], str]],
    normalize_language_fn: Callable[[str], str],
    is_plausible_chunk_fn: Optional[Callable[[str], bool]] = None,
    source_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    evidence = build_studio_evidence_model(chunks, config, is_plausible_chunk_fn)
    _ensure_source_evidence_if_ids_given(source_ids, evidence)

    language = normalize_language_fn(config.get("language", "English"))
    audience = _clean_text(config.get("audience_level") or "Intermediate")
    topic = evidence["topic"]

    lang_note = f" Write ALL slide titles, subtitles, bullets, examples, and speaker_notes strictly in {language}." if language != "English" else ""
    prompt = (
        f"Create an educational Slide Deck JSON for topic '{topic}' at {audience} level.{lang_note}\n"
        f"{_wrap_untrusted_context(evidence)}\n\n"
        "Requirements:\n"
        "- Scale the number of slides (between 4 and 10 slides) to match the actual richness of the source material.\n"
        "- Include a title slide with learning objectives, concept/definition slides, mechanism/process slides, "
        "examples or comparison slides, and a synthesis/takeaway slide.\n"
        "- Ground every factual bullet in the source material and cite page numbers when supported.\n"
        "- Never invent unrelated jargon or software-engineering terms if the source is another subject.\n"
        "Return JSON with keys: title, learning_objectives (array of strings), slides (array of objects with: "
        "id, slide_number, layout [one of title_hero, key_concepts, process_flow, comparison, takeaways], "
        "title, subtitle, bullets [2-5 strings], example, visual_suggestion, speaker_notes, source_citation)."
    )

    llm_data, provider = call_llm_json_fn(
        "You are an expert curriculum designer creating clear, source-grounded academic presentations.",
        prompt,
        user_prefs=user_prefs,
    )

    slides: List[Dict[str, Any]] = []
    objectives: List[str] = []
    out_title = _clean_text(config.get("title")) or ""

    if isinstance(llm_data, dict) and isinstance(llm_data.get("slides"), list) and len(llm_data["slides"]) >= 2:
        out_title = out_title or _clean_text(llm_data.get("title")) or f"Slide Deck: {topic}"
        objectives = [_clean_text(o) for o in (llm_data.get("learning_objectives") or []) if _clean_text(o)][:5]
        for idx, raw_s in enumerate(llm_data["slides"][:12], start=1):
            if not isinstance(raw_s, dict):
                continue
            bullets = [_clean_text(b) for b in (raw_s.get("bullets") or []) if _clean_text(b)][:6]
            if not bullets:
                continue
            slides.append({
                "id": f"slide-{len(slides) + 1}",
                "slide_number": len(slides) + 1,
                "layout": str(raw_s.get("layout") or ("title_hero" if idx == 1 else "key_concepts")),
                "title": _clean_text(raw_s.get("title") or f"Section {len(slides) + 1}"),
                "subtitle": _clean_text(raw_s.get("subtitle") or topic),
                "bullets": bullets,
                "example": _clean_text(raw_s.get("example") or ""),
                "visual_suggestion": _clean_text(raw_s.get("visual_suggestion") or "Concept diagram illustrating relationships from the source."),
                "speaker_notes": _clean_text(raw_s.get("speaker_notes") or ""),
                "source_citation": _clean_text(raw_s.get("source_citation") or ""),
            })

    if len(slides) < 2:
        provider = "local_structured_engine"
        facts = evidence["fact_items"]
        out_title = out_title or f"Slide Deck: {topic}"
        objectives = [
            f"Explain the core principles and terminology of {topic}.",
            "Trace key mechanisms, relationships, and supporting evidence from the selected source(s).",
            "Distinguish closely related concepts and review key takeaways.",
        ]
        if not facts:
            slides = [
                {
                    "id": "slide-1",
                    "slide_number": 1,
                    "layout": "title_hero",
                    "title": topic,
                    "subtitle": f"Study Presentation ({audience}) — No Source Document Attached",
                    "bullets": [
                        "No uploaded source passages were provided for this deck.",
                        "Select one or more ready sources in AI Studio for detailed, page-cited slides.",
                    ],
                    "example": "Tip: Attach your lecture notes or textbook PDF and regenerate.",
                    "visual_suggestion": "Title card with topic overview.",
                    "speaker_notes": f"Introduce {topic} and note that source documents should be attached for grounded detail.",
                },
                {
                    "id": "slide-2",
                    "slide_number": 2,
                    "layout": "takeaways",
                    "title": "Study Framework",
                    "subtitle": "Core Questions to Explore",
                    "bullets": [
                        f"What are the foundational definitions in {topic}?",
                        "Which mechanisms or cause-and-effect links explain how it works?",
                        "What evidence, examples, or comparisons support those claims?",
                    ],
                    "example": "Use the Study Guide or Flashcards after uploading a source.",
                    "visual_suggestion": "Three-column inquiry checklist.",
                    "speaker_notes": "Guide learners to frame key questions before reading.",
                },
            ]
        else:
            # Scale slide count dynamically based on number of extracted facts (4 to 8 slides)
            slides.append({
                "id": "slide-1",
                "slide_number": 1,
                "layout": "title_hero",
                "title": topic,
                "subtitle": f"Source-Grounded Presentation ({audience})",
                "bullets": objectives,
                "example": f"Grounded in {len(evidence['source_references'])} source section(s).",
                "visual_suggestion": f"Overview map introducing the main themes of {topic}.",
                "speaker_notes": f"Introduce {topic} and outline the learning objectives covered across the source.",
            })
            group_size = 3
            for g_idx in range(0, min(len(facts), 18), group_size):
                group = facts[g_idx : g_idx + group_size]
                slide_num = len(slides) + 1
                primary = group[0]
                cat = primary["category"]
                layout = "process_flow" if cat == "Mechanism" else ("comparison" if cat == "Comparison" else "key_concepts")
                cites = _dedupe_preserve_order([_format_ref_citation(f) for f in group])
                slides.append({
                    "id": f"slide-{slide_num}",
                    "slide_number": slide_num,
                    "layout": layout,
                    "title": f"{slide_num - 1}. {primary['label']}",
                    "subtitle": f"{cat} • {', '.join(cites)}",
                    "bullets": [f["text"] for f in group],
                    "example": f"Source reference: {', '.join(cites)}",
                    "visual_suggestion": f"Structured {cat.lower()} diagram for {primary['label']}.",
                    "speaker_notes": f"Walk through {primary['label']} using evidence from {', '.join(cites)}.",
                    "source_citation": ", ".join(cites),
                })
            # Closing synthesis slide
            last_num = len(slides) + 1
            takeaways = [f["text"] for f in facts[:3]]
            slides.append({
                "id": f"slide-{last_num}",
                "slide_number": last_num,
                "layout": "takeaways",
                "title": f"{last_num - 1}. Key Takeaways & Review",
                "subtitle": "Source-Grounded Synthesis",
                "bullets": takeaways,
                "example": f"Self-check: Summarize {topic} in your own words using the cited pages.",
                "visual_suggestion": "Summary takeaway board linking core concepts.",
                "speaker_notes": "Review the main takeaways and verify understanding with Flashcards or Quiz.",
            })

    return {
        "title": out_title,
        "language": language,
        "learning_objectives": objectives,
        "outline": [s["title"] for s in slides],
        "slides": slides,
        "source_references": evidence["source_references"],
        "generation_provider": provider,
    }


# ============================================================================
# B. MIND MAP
# ============================================================================
def _validate_mind_map_tree(node: Any, depth: int = 0) -> Optional[Dict[str, Any]]:
    if not isinstance(node, dict) or depth > 4:
        return None
    label = _clean_text(node.get("label"))
    if not label:
        return None
    nid = _clean_text(node.get("id")) or f"node_{depth}_{abs(hash(label)) % 10000}"
    details = _clean_text(node.get("details") or label)
    category = _clean_text(node.get("category") or ("root" if depth == 0 else ("branch" if depth == 1 else "leaf")))
    raw_children = node.get("children") if isinstance(node.get("children"), list) else []
    children: List[Dict[str, Any]] = []
    for ch in raw_children[:6]:
        valid_ch = _validate_mind_map_tree(ch, depth + 1)
        if valid_ch:
            children.append(valid_ch)
    return {
        "id": nid,
        "label": label[:80],
        "category": category,
        "details": details,
        "children": children,
    }


def _collect_node_ids(node: Dict[str, Any]) -> set:
    ids = {node["id"]}
    for ch in node.get("children") or []:
        ids |= _collect_node_ids(ch)
    return ids


def generate_mind_map_grounded(
    chunks: List[Dict[str, Any]],
    config: Dict[str, Any],
    user_prefs: Optional[Dict[str, Any]],
    call_llm_json_fn: Callable[..., Tuple[Optional[Any], str]],
    normalize_language_fn: Callable[[str], str],
    is_plausible_chunk_fn: Optional[Callable[[str], bool]] = None,
    source_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    evidence = build_studio_evidence_model(chunks, config, is_plausible_chunk_fn)
    _ensure_source_evidence_if_ids_given(source_ids, evidence)

    language = normalize_language_fn(config.get("language", "English"))
    topic = evidence["topic"]
    lang_note = f" Write ALL node labels, details, and relationship labels strictly in {language}." if language != "English" else ""

    prompt = (
        f"Build a hierarchical Mind Map JSON for '{topic}'.{lang_note}\n"
        f"{_wrap_untrusted_context(evidence)}\n\n"
        "Requirements:\n"
        "- Root node represents the central topic.\n"
        "- 3 to 6 main concept branches, each with 2 to 4 specific sub-concept leaf nodes grounded in the source.\n"
        "- Include meaningful cross-links in 'relationships' ONLY when supported by the source (no fabricated links).\n"
        "- Keep labels concise (2-6 words) and put full explanations in 'details'.\n"
        "Return JSON with keys: title, root ({id, label, category, details, children: [...]}), "
        "relationships (array of {from, to, label} referencing actual node ids)."
    )

    llm_data, provider = call_llm_json_fn(
        "You are an expert knowledge architect building accurate, source-grounded concept maps.",
        prompt,
        user_prefs=user_prefs,
    )

    root_node: Optional[Dict[str, Any]] = None
    relationships: List[Dict[str, str]] = []
    out_title = _clean_text(config.get("title")) or ""

    if isinstance(llm_data, dict) and llm_data.get("root"):
        candidate_root = _validate_mind_map_tree(llm_data["root"])
        if candidate_root and len(candidate_root.get("children", [])) >= 2:
            root_node = candidate_root
            out_title = out_title or _clean_text(llm_data.get("title")) or f"Mind Map: {topic}"
            valid_ids = _collect_node_ids(root_node)
            for rel in (llm_data.get("relationships") or [])[:10]:
                if isinstance(rel, dict):
                    src_id = _clean_text(rel.get("from"))
                    dst_id = _clean_text(rel.get("to"))
                    lbl = _clean_text(rel.get("label"))
                    if src_id in valid_ids and dst_id in valid_ids and src_id != dst_id and lbl:
                        relationships.append({"from": src_id, "to": dst_id, "label": lbl})

    if not root_node:
        provider = "local_structured_engine"
        out_title = out_title or f"Mind Map: {topic}"
        facts = evidence["fact_items"]
        if not facts:
            root_node = {
                "id": "root",
                "label": topic,
                "category": "root",
                "details": "No source passages were attached. Upload and select a source document to map its concepts.",
                "children": [
                    {
                        "id": "branch-1",
                        "label": "Core Definitions",
                        "category": "foundation",
                        "details": f"Key terminology defining {topic}.",
                        "children": [],
                    },
                    {
                        "id": "branch-2",
                        "label": "Mechanisms & Context",
                        "category": "mechanism",
                        "details": f"Processes, evidence, and relationships in {topic}.",
                        "children": [],
                    },
                ],
            }
        else:
            # Group facts by category or section into 2-5 meaningful branches
            buckets: Dict[str, List[Dict[str, Any]]] = {}
            for f in facts[:16]:
                key = f["category"]
                buckets.setdefault(key, []).append(f)

            branches: List[Dict[str, Any]] = []
            for b_idx, (cat, items) in enumerate(list(buckets.items())[:5], start=1):
                leaves = []
                for l_idx, item in enumerate(items[:4], start=1):
                    leaves.append({
                        "id": f"b{b_idx}-{l_idx}",
                        "label": item["label"][:60],
                        "category": "leaf",
                        "details": f"{item['text']} [{_format_ref_citation(item)}]",
                        "children": [],
                    })
                branches.append({
                    "id": f"branch-{b_idx}",
                    "label": cat,
                    "category": cat.lower().replace(" ", "_"),
                    "details": f"{len(items)} source-grounded point(s) categorized under {cat}.",
                    "children": leaves,
                })

            root_node = {
                "id": "root",
                "label": topic[:60],
                "category": "root",
                "details": f"Concept hierarchy synthesized from {len(evidence['source_references'])} source section(s).",
                "children": branches,
            }
            # Only add relationships between adjacent branches that actually exist
            for idx in range(len(branches) - 1):
                relationships.append({
                    "from": branches[idx]["id"],
                    "to": branches[idx + 1]["id"],
                    "label": "relates to in source",
                })

    return {
        "title": out_title,
        "language": language,
        "root": root_node,
        "relationships": relationships,
        "source_references": evidence["source_references"],
        "generation_provider": provider,
    }


# ============================================================================
# C. STUDY GUIDE
# ============================================================================
def generate_study_guide_grounded(
    chunks: List[Dict[str, Any]],
    config: Dict[str, Any],
    user_prefs: Optional[Dict[str, Any]],
    call_llm_json_fn: Callable[..., Tuple[Optional[Any], str]],
    normalize_language_fn: Callable[[str], str],
    is_plausible_chunk_fn: Optional[Callable[[str], bool]] = None,
    source_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    evidence = build_studio_evidence_model(chunks, config, is_plausible_chunk_fn)
    _ensure_source_evidence_if_ids_given(source_ids, evidence)

    language = normalize_language_fn(config.get("language", "English"))
    audience = _clean_text(config.get("audience_level") or "Intermediate")
    topic = evidence["topic"]
    lang_note = f" Write ALL fields strictly in {language}." if language != "English" else ""

    prompt = (
        f"Author a comprehensive, strictly source-grounded Study Guide JSON for '{topic}' ({audience} level).{lang_note}\n"
        f"{_wrap_untrusted_context(evidence)}\n\n"
        "Requirements:\n"
        "- Adapt vocabulary and structure strictly to the subject domain of the source (never inject unrelated CS/coding terms).\n"
        "- Include overview, learning_objectives, detailed sections, terminology, mechanisms/examples, "
        "comparison_tables, common_mistakes/limitations, practice_questions (with model answers), and summary.\n"
        "Return JSON with keys: title, overview, learning_objectives (array of strings), "
        "sections (array of {id, heading, level_tag, content, key_takeaway}), "
        "terminology (array of {term, definition, context}), "
        "code_and_formulas (array of {title, language, code, explanation}), "
        "comparison_tables (array of {title, headers, rows}), "
        "common_mistakes (array of {mistake, why_it_happens, fix}), "
        "practice_questions (array of {question, model_answer}), summary."
    )

    llm_data, provider = call_llm_json_fn(
        "You are an expert educator authoring rigorous, domain-appropriate, source-grounded study guides.",
        prompt,
        user_prefs=user_prefs,
    )

    out_title = _clean_text(config.get("title")) or ""
    if isinstance(llm_data, dict) and isinstance(llm_data.get("sections"), list) and len(llm_data["sections"]) >= 2:
        out_title = out_title or _clean_text(llm_data.get("title")) or f"Study Guide: {topic}"
        return {
            "title": out_title,
            "language": language,
            "overview": _clean_text(llm_data.get("overview") or f"Study guide for {topic}."),
            "learning_objectives": [_clean_text(o) for o in (llm_data.get("learning_objectives") or []) if _clean_text(o)],
            "sections": llm_data["sections"],
            "diagrams": llm_data.get("diagrams") or [],
            "terminology": llm_data.get("terminology") or [],
            "code_and_formulas": llm_data.get("code_and_formulas") or [],
            "comparison_tables": llm_data.get("comparison_tables") or [],
            "common_mistakes": llm_data.get("common_mistakes") or [],
            "practice_questions": llm_data.get("practice_questions") or [],
            "summary": _clean_text(llm_data.get("summary") or ""),
            "source_references": evidence["source_references"],
            "generation_provider": provider,
        }

    # Domain-neutral offline fallback (zero CS boilerplate!)
    provider = "local_structured_engine"
    out_title = out_title or f"Study Guide: {topic}"
    facts = evidence["fact_items"]
    if not facts:
        return {
            "title": out_title,
            "language": language,
            "overview": (
                f"No uploaded source passages were provided for '{topic}'. "
                "Select one or more ready source documents to generate a detailed, page-cited study guide."
            ),
            "learning_objectives": [
                f"Identify core definitions and principles in {topic}.",
                "Connect mechanisms, evidence, and real-world applications.",
            ],
            "sections": [
                {
                    "id": "sec-1",
                    "heading": "1. Source Limitation Notice",
                    "level_tag": audience,
                    "content": "No source document text was available to synthesize detailed explanations.",
                    "key_takeaway": "Attach a PDF, Markdown, or text source in AI Studio and regenerate.",
                }
            ],
            "diagrams": [],
            "terminology": [],
            "code_and_formulas": [],
            "comparison_tables": [],
            "common_mistakes": [],
            "practice_questions": [],
            "summary": f"Upload source materials for {topic} to unlock full explanations, terminology, and practice questions.",
            "source_references": [],
            "generation_provider": provider,
        }

    # Group facts into coherent sections by category/theme
    sections: List[Dict[str, Any]] = []
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for f in facts[:16]:
        buckets.setdefault(f["category"], []).append(f)

    for idx, (cat, items) in enumerate(buckets.items(), start=1):
        paragraphs = [f"{it['text']} [{_format_ref_citation(it)}]" for it in items[:5]]
        sections.append({
            "id": f"sec-{idx}",
            "heading": f"{idx}. {cat}: {items[0]['label']}",
            "level_tag": audience,
            "content": "\n\n".join(paragraphs),
            "key_takeaway": items[0]["text"],
        })

    terminology = [
        {
            "term": f["label"],
            "definition": f["text"],
            "context": _format_ref_citation(f),
        }
        for f in (evidence["definitions"] or facts)[:6]
    ]

    practice_questions = []
    for f in facts[:4]:
        practice_questions.append({
            "question": f"Explain {f['label']} based on the source material ({_format_ref_citation(f)}).",
            "model_answer": f["text"],
        })

    comp_tables = []
    if evidence["comparisons"]:
        comp_tables.append({
            "title": f"Key Comparisons in {topic}",
            "headers": ["Concept", "Source Finding", "Reference"],
            "rows": [
                [c["label"], c["text"], _format_ref_citation(c)]
                for c in evidence["comparisons"][:5]
            ],
        })

    return {
        "title": out_title,
        "language": language,
        "overview": " ".join(f["text"] for f in facts[:2]),
        "learning_objectives": [
            f"Understand core concepts and definitions in {topic}.",
            "Explain key mechanisms and relationships supported by the source.",
            "Apply source evidence to review questions.",
        ],
        "sections": sections,
        "diagrams": [],
        "terminology": terminology,
        "code_and_formulas": [],
        "comparison_tables": comp_tables,
        "common_mistakes": [],
        "practice_questions": practice_questions,
        "summary": facts[-1]["text"] if facts else "",
        "source_references": evidence["source_references"],
        "generation_provider": provider,
    }


# ============================================================================
# D. FLASHCARDS
# ============================================================================
def generate_flashcards_grounded(
    chunks: List[Dict[str, Any]],
    config: Dict[str, Any],
    user_prefs: Optional[Dict[str, Any]],
    call_llm_json_fn: Callable[..., Tuple[Optional[Any], str]],
    normalize_language_fn: Callable[[str], str],
    is_plausible_chunk_fn: Optional[Callable[[str], bool]] = None,
    source_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    evidence = build_studio_evidence_model(chunks, config, is_plausible_chunk_fn)
    _ensure_source_evidence_if_ids_given(source_ids, evidence)

    language = normalize_language_fn(config.get("language", "English"))
    difficulty = _clean_text(config.get("audience_level") or config.get("difficulty") or "Intermediate")
    requested_count = max(4, min(25, int(config.get("card_count") or 10)))
    topic = evidence["topic"]
    lang_note = f" Write ALL card fronts, backs, hints, and categories strictly in {language}." if language != "English" else ""

    prompt = (
        f"Generate {requested_count} concise, non-duplicate active-recall flashcards in JSON for '{topic}' ({difficulty} difficulty).{lang_note}\n"
        f"{_wrap_untrusted_context(evidence)}\n\n"
        "Requirements:\n"
        "- Mix definitions, mechanisms, applications, and conceptual distinctions.\n"
        "- Every card must be grounded in the source material with no duplicate questions.\n"
        "Return JSON with key 'cards' containing an array of objects: {front, back, hint, category}."
    )

    llm_data, provider = call_llm_json_fn(
        "You are an expert cognitive scientist designing concise, accurate spaced-repetition flashcards.",
        prompt,
        user_prefs=user_prefs,
    )

    cards: List[Dict[str, str]] = []
    seen_fronts = set()
    raw_cards = llm_data.get("cards") if isinstance(llm_data, dict) else (llm_data if isinstance(llm_data, list) else [])
    if isinstance(raw_cards, list):
        for c in raw_cards:
            if not isinstance(c, dict):
                continue
            front = _clean_text(c.get("front"))
            back = _clean_text(c.get("back"))
            if not front or not back or front.lower() in seen_fronts:
                continue
            seen_fronts.add(front.lower())
            cards.append({
                "front": front,
                "back": back,
                "hint": _clean_text(c.get("hint") or ""),
                "category": _clean_text(c.get("category") or "Core Concept"),
            })
            if len(cards) >= requested_count:
                break

    if len(cards) < 4:
        provider = "local_structured_engine"
        cards = []
        seen_fronts = set()
        facts = evidence["fact_items"]
        if not facts:
            cards = [
                {
                    "front": f"What is the central focus of {topic}?",
                    "back": "No source document was selected. Upload and attach a source to generate source-grounded flashcards.",
                    "hint": "Attach a source in AI Studio.",
                    "category": "Overview",
                },
                {
                    "front": f"How should you study {topic} using active recall?",
                    "back": "Test yourself on definitions, cause-and-effect mechanisms, and comparisons without looking at notes first.",
                    "hint": "Active recall principle.",
                    "category": "Study Method",
                },
                {
                    "front": f"What distinguishes a mechanism from a definition in {topic}?",
                    "back": "A definition states what a concept is; a mechanism explains the step-by-step process by which it operates.",
                    "hint": "What vs. How.",
                    "category": "Distinction",
                },
                {
                    "front": f"Why are page references useful when reviewing {topic}?",
                    "back": "Page references let you verify claims directly against the primary source material.",
                    "hint": "Verification.",
                    "category": "Evidence",
                },
            ]
        else:
            for item in facts:
                if len(cards) >= requested_count:
                    break
                cat = item["category"]
                lbl = item["label"]
                if cat == "Definition":
                    front = f"Define '{lbl}' in the context of {topic}."
                elif cat == "Mechanism":
                    front = f"How does {lbl} operate or produce its effect?"
                elif cat == "Comparison":
                    front = f"What key distinction or contrast is described for {lbl}?"
                else:
                    front = f"What does the source establish about {lbl}?"
                if front.lower() in seen_fronts:
                    continue
                seen_fronts.add(front.lower())
                cards.append({
                    "front": front,
                    "back": f"{item['text']} [{_format_ref_citation(item)}]",
                    "hint": f"See {_format_ref_citation(item)}",
                    "category": cat,
                })

    out_title = _clean_text(config.get("title")) or f"Flashcard Deck: {topic}"
    return {
        "title": out_title,
        "language": language,
        "description": f"{len(cards)} active-recall flashcards grounded in {topic}.",
        "cards": cards,
        "source_references": evidence["source_references"],
        "generation_provider": provider,
    }


# ============================================================================
# E. QUIZ (DOMAIN-NEUTRAL SOURCE-GROUNDED FALLBACK BANK)
# ============================================================================
def build_domain_neutral_mcq_bank(
    topic_title: str,
    difficulty: str = "Intermediate",
    source_passages: Optional[List[Dict[str, Any]]] = None,
    target_count: int = 20,
    is_plausible_chunk_fn: Optional[Callable[[str], bool]] = None,
) -> List[Dict[str, Any]]:
    """
    Generates deterministic, domain-neutral, source-grounded MCQs when LLM output is
    unavailable or needs repair. Distractors are drawn from other source statements or
    domain-neutral reversals rather than unrelated software-engineering templates.
    """
    evidence = build_studio_evidence_model(source_passages or [], {"topic": topic_title}, is_plausible_chunk_fn)
    facts = evidence["fact_items"]
    questions: List[Dict[str, Any]] = []

    if facts:
        for i in range(target_count):
            fact = facts[i % len(facts)]
            cite = _format_ref_citation(fact)
            correct_opt = fact["text"][:180]

            # Build distinct distractors from other source facts (paired with wrong attribution/negation)
            # or domain-neutral counterfactual statements
            distractors: List[str] = []
            for offset in range(1, len(facts)):
                other = facts[(i + offset) % len(facts)]["text"][:180]
                if other != correct_opt and other not in distractors:
                    distractors.append(other)
                if len(distractors) >= 3:
                    break

            generic_distractors = [
                f"The source explicitly states that {fact['label']} has no measurable role in {topic_title}.",
                f"According to {cite}, {fact['label']} is unrelated to any process described in {topic_title}.",
                f"The source concludes that {fact['label']} was disproven and omitted from {topic_title}.",
            ]
            for gd in generic_distractors:
                if len(distractors) >= 3:
                    break
                if gd != correct_opt and gd not in distractors:
                    distractors.append(gd)

            prefix = "" if i < len(facts) else f"[Review #{i + 1}] "
            q_text = f"{prefix}According to {cite}, which statement accurately describes {fact['label']}?"
            correct_idx = (i * 3 + 1) % 4
            options: List[str] = []
            d_ptr = 0
            for opt_idx in range(4):
                if opt_idx == correct_idx:
                    options.append(correct_opt)
                else:
                    options.append(distractors[d_ptr])
                    d_ptr += 1

            questions.append({
                "id": f"q_{i + 1}",
                "number": i + 1,
                "category": fact["category"],
                "difficulty": difficulty,
                "question": q_text,
                "options": options,
                "correct_index": correct_idx,
                "explanation": f"Grounded in {cite}: {fact['text']}",
            })
        return questions

    # Topic-only fallback (no sources selected) — domain-neutral study assessment prompts
    prompts = [
        ("Foundational Understanding", f"What is the primary goal when studying {topic_title}?",
         f"Understanding core definitions, mechanisms, and supporting evidence in {topic_title}.",
         f"Memorizing isolated terms without understanding how they connect.",
         f"Ignoring primary evidence and relying on unverified assumptions.",
         f"Skipping foundational concepts before attempting advanced synthesis."),
        ("Evidence & Grounding", f"How should a factual claim about {topic_title} be verified?",
         "By checking it against primary source passages and cited page references.",
         "By assuming any plausible-sounding statement is automatically true.",
         "By omitting citations whenever a claim sounds familiar.",
         "By replacing source evidence with unrelated analogies."),
        ("Conceptual Distinctions", f"Why is it important to distinguish mechanisms from definitions in {topic_title}?",
         "Definitions identify what a concept is, while mechanisms explain how and why it operates.",
         "Because definitions and mechanisms are always identical.",
         "Because mechanisms never involve cause-and-effect relationships.",
         "Because definitions are only used in introductory summaries."),
        ("Critical Analysis", f"When a source document lacks detail on a subtopic of {topic_title}, what is the rigorous approach?",
         "Acknowledge the gap honestly rather than fabricating unsupported details.",
         "Invent quantitative statistics to make the summary look complete.",
         "Copy conclusions from an unrelated subject area.",
         "Treat missing evidence as proof that the mechanism does not exist."),
    ]
    for i in range(target_count):
        cat, q_text, c_opt, d1, d2, d3 = prompts[i % len(prompts)]
        correct_idx = (i * 3 + 1) % 4
        dists = [d1, d2, d3]
        options = []
        d_ptr = 0
        for opt_idx in range(4):
            options.append(c_opt if opt_idx == correct_idx else dists[d_ptr])
            if opt_idx != correct_idx:
                d_ptr += 1
        questions.append({
            "id": f"q_{i + 1}",
            "number": i + 1,
            "category": cat,
            "difficulty": difficulty,
            "question": q_text if i < len(prompts) else f"[Concept Check #{i + 1}] {q_text}",
            "options": options,
            "correct_index": correct_idx,
            "explanation": f"Accurate study of {topic_title} relies on {c_opt.lower()}",
        })
    return questions


# ============================================================================
# F. INFOGRAPHIC
# ============================================================================
def generate_infographic_grounded(
    chunks: List[Dict[str, Any]],
    config: Dict[str, Any],
    user_prefs: Optional[Dict[str, Any]],
    call_llm_json_fn: Callable[..., Tuple[Optional[Any], str]],
    normalize_language_fn: Callable[[str], str],
    is_plausible_chunk_fn: Optional[Callable[[str], bool]] = None,
    source_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    evidence = build_studio_evidence_model(chunks, config, is_plausible_chunk_fn)
    _ensure_source_evidence_if_ids_given(source_ids, evidence)

    language = normalize_language_fn(config.get("language", "English"))
    topic = evidence["topic"]
    lang_note = f" Write ALL titles, labels, summaries, and comparison points strictly in {language}." if language != "English" else ""

    prompt = (
        f"Create a structured visual Infographic JSON for '{topic}'.{lang_note}\n"
        f"{_wrap_untrusted_context(evidence)}\n\n"
        "STRICT RULES:\n"
        "- NEVER invent percentages, mastery thresholds, or statistics unless those exact numbers appear in the source.\n"
        "- If the source has no numerical statistics, use qualitative count/scope cards (e.g. number of key concepts or source pages) instead.\n"
        "- Keep all visual_sections and comparison_callout grounded in the source subject.\n"
        "Return JSON with keys: title, subtitle, theme_accent, hero_stat_cards (array of {value, label, detail}), "
        "visual_sections (array of {step, title, summary, badge}), "
        "comparison_callout ({left_title, left_points, right_title, right_points}), footer_takeaway."
    )

    llm_data, provider = call_llm_json_fn(
        "You are an information designer creating strictly source-grounded educational infographics without fabricated statistics.",
        prompt,
        user_prefs=user_prefs,
    )

    out_title = _clean_text(config.get("title")) or ""
    if isinstance(llm_data, dict) and isinstance(llm_data.get("visual_sections"), list) and len(llm_data["visual_sections"]) >= 2:
        out_title = out_title or _clean_text(llm_data.get("title")) or f"Infographic: {topic}"
        return {
            "title": out_title,
            "language": language,
            "subtitle": _clean_text(llm_data.get("subtitle") or "Source-Grounded Visual Synthesis"),
            "theme_accent": str(llm_data.get("theme_accent") or "#38bdf8"),
            "hero_stat_cards": (llm_data.get("hero_stat_cards") or [])[:4],
            "visual_sections": llm_data["visual_sections"][:6],
            "comparison_callout": llm_data.get("comparison_callout") or {},
            "footer_takeaway": _clean_text(llm_data.get("footer_takeaway") or ""),
            "source_references": evidence["source_references"],
            "generation_provider": provider,
        }

    provider = "local_structured_engine"
    out_title = out_title or f"Infographic: {topic}"
    facts = evidence["fact_items"]
    refs = evidence["source_references"]

    # Honest non-fabricated hero cards
    hero_cards = [
        {"value": str(len(refs)), "label": "Source Sections", "detail": "Verified pages/sections"},
        {"value": str(len(facts)), "label": "Extracted Facts", "detail": "Complete source claims"},
        {"value": str(len(evidence["quantitative_facts"])), "label": "Quantitative Claims", "detail": "Explicitly stated in source"},
        {"value": str(len(evidence["mechanisms"])), "label": "Mechanisms", "detail": "Causal processes identified"},
    ]

    visual_sections = []
    for idx, f in enumerate(facts[:4], start=1):
        visual_sections.append({
            "step": f"0{idx}",
            "title": f["label"],
            "summary": f"{f['text']} [{_format_ref_citation(f)}]",
            "badge": f["category"],
        })
    if not visual_sections:
        visual_sections = [
            {
                "step": "01",
                "title": "Source Required",
                "summary": f"No source passages were attached for {topic}. Select a source document to synthesize visual sections.",
                "badge": "Notice",
            }
        ]

    comp_callout = {
        "left_title": "Key Definitions & Context",
        "left_points": [f["text"] for f in (evidence["definitions"] or facts)[:3]] or ["Attach a source document to populate definitions."],
        "right_title": "Mechanisms & Comparisons",
        "right_points": [f["text"] for f in (evidence["mechanisms"] + evidence["comparisons"] or facts[3:])[:3]] or ["Attach a source document to populate mechanisms."],
    }

    return {
        "title": out_title,
        "language": language,
        "subtitle": "Source-Grounded Visual Synthesis",
        "theme_accent": "#38bdf8",
        "hero_stat_cards": hero_cards,
        "visual_sections": visual_sections,
        "comparison_callout": comp_callout,
        "footer_takeaway": facts[-1]["text"] if facts else f"Upload a source document for {topic} to generate grounded visual takeaways.",
        "source_references": refs,
        "generation_provider": provider,
    }


# ============================================================================
# G. DATA TABLE
# ============================================================================
def extract_data_table_grounded(
    chunks: List[Dict[str, Any]],
    config: Dict[str, Any],
    user_prefs: Optional[Dict[str, Any]],
    call_llm_json_fn: Callable[..., Tuple[Optional[Any], str]],
    normalize_language_fn: Callable[[str], str],
    is_plausible_chunk_fn: Optional[Callable[[str], bool]] = None,
    source_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    evidence = build_studio_evidence_model(chunks, config, is_plausible_chunk_fn)
    _ensure_source_evidence_if_ids_given(source_ids, evidence)

    language = normalize_language_fn(config.get("language", "English"))
    topic = evidence["topic"]
    extraction_type = _clean_text(config.get("extraction_type") or "Concept Comparisons & Definitions")
    instructions = _clean_text(config.get("instructions") or "")
    lang_note = f" Write ALL columns, cell values, and missing_data_notes strictly in {language}." if language != "English" else ""

    prompt = (
        f"Extract a structured Data Table JSON from the source for '{topic}' (Extraction type: {extraction_type}).{lang_note}\n"
        f"Additional user instructions: {instructions or 'Preserve units, labels, values, and page citations.'}\n"
        f"{_wrap_untrusted_context(evidence)}\n\n"
        "STRICT RULES:\n"
        "- Preserve exact numbers, units, and labels from the source.\n"
        "- If a cell value is not stated in the source, write 'Not stated in source' instead of guessing.\n"
        "- Distinguish explicitly extracted tables/values from inferred structure in missing_data_notes.\n"
        "Return JSON with keys: title, columns (array of 3-6 column headers), "
        "rows (array of {id, cells: [strings matching column count]}), missing_data_notes."
    )

    llm_data, provider = call_llm_json_fn(
        "You are a precise data extraction specialist preserving units, labels, and honest missing-data markers.",
        prompt,
        user_prefs=user_prefs,
    )

    out_title = _clean_text(config.get("title")) or f"Data Table: {topic} ({extraction_type})"
    if isinstance(llm_data, dict) and isinstance(llm_data.get("columns"), list) and isinstance(llm_data.get("rows"), list) and llm_data["rows"]:
        cols = [_clean_text(c) for c in llm_data["columns"] if _clean_text(c)]
        valid_rows: List[Dict[str, Any]] = []
        for idx, r in enumerate(llm_data["rows"][:25], start=1):
            if not isinstance(r, dict) or not isinstance(r.get("cells"), list):
                continue
            cells = [_clean_text(c) or "Not stated in source" for c in r["cells"][:len(cols)]]
            while len(cells) < len(cols):
                cells.append("Not stated in source")
            valid_rows.append({"id": str(r.get("id") or f"row-{idx}"), "cells": cells})
        if cols and valid_rows:
            return {
                "title": _clean_text(config.get("title") or llm_data.get("title") or out_title),
                "language": language,
                "extraction_type": extraction_type,
                "instructions": instructions or "Extract structured facts, units, and page references.",
                "columns": cols,
                "rows": valid_rows,
                "missing_data_notes": _clean_text(llm_data.get("missing_data_notes") or "Extracted from selected source(s); unstated cells marked 'Not stated in source'."),
                "source_references": evidence["source_references"],
                "generation_provider": provider,
            }

    provider = "local_structured_engine"
    structured = evidence["structured_rows"]
    if structured:
        # Use genuine extracted table / key-value rows first
        max_cols = min(5, max(len(r["cells"]) for r in structured))
        if max_cols == 2:
            columns = ["Attribute / Item", "Extracted Value / Detail", "Source & Page", "Extraction Mode"]
            rows = [
                {
                    "id": f"row-{idx}",
                    "cells": [
                        r["cells"][0],
                        r["cells"][1],
                        f"{r['source_title']} (p.{r['page_number']})",
                        "Direct table/key-value extraction" if r["origin"] == "extracted_table" else "Structured line extraction",
                    ],
                }
                for idx, r in enumerate(structured[:15], start=1)
            ]
        else:
            columns = [f"Column {i}" for i in range(1, max_cols + 1)] + ["Source & Page"]
            rows = []
            for idx, r in enumerate(structured[:15], start=1):
                padded = list(r["cells"][:max_cols])
                while len(padded) < max_cols:
                    padded.append("Not stated in source")
                padded.append(f"{r['source_title']} (p.{r['page_number']})")
                rows.append({"id": f"row-{idx}", "cells": padded})
        notes = "Rows extracted directly from structured tables or key-value lines in the source; empty cells marked 'Not stated in source'."
    elif evidence["fact_items"]:
        columns = ["Concept", "Category", "Source Statement", "Source & Page"]
        rows = [
            {
                "id": f"row-{idx}",
                "cells": [
                    f["label"],
                    f["category"],
                    f["text"],
                    _format_ref_citation(f),
                ],
            }
            for idx, f in enumerate(evidence["fact_items"][:10], start=1)
        ]
        notes = (
            "No explicit tabular grid was detected in the source; rows organize extracted prose statements by concept and category "
            "(inferred structure, source-grounded content)."
        )
    else:
        columns = ["Concept", "Category", "Source Statement", "Source & Page"]
        rows = []
        notes = "No source documents were selected or no extractable structured data was found."

    return {
        "title": out_title,
        "language": language,
        "extraction_type": extraction_type,
        "instructions": instructions or "Extract structured relationships, values, units, and page references.",
        "columns": columns,
        "rows": rows,
        "missing_data_notes": notes,
        "source_references": evidence["source_references"],
        "generation_provider": provider,
    }


# ============================================================================
# H. VIDEO OVERVIEW STORYBOARD (CYCLE 2 — 6-LANGUAGE, DOMAIN-NEUTRAL)
# ============================================================================
MAX_ADAPTIVE_SCENES = 24


def _infer_scene_visual_mode(topic: str, text: str, category: str = "") -> str:
    """Selects a subject-appropriate teaching visualization mode from source text and category."""
    scene_blob = f"{text} {category}".lower()
    full_blob = f"{topic} {scene_blob}".lower()
    if category == "Comparison" or any(k in scene_blob for k in (" vs ", "versus", "compare", "comparison", "contrast", "tradeoff", "trade-off", "whereas", "advantage", "disadvantage")):
        return "comparison_matrix"
    if any(k in scene_blob for k in ("equation", "formula", "stoichiometr", "derivation", "integral", "derivative", "theorem", "proof", "o(log", "o(n", "Δ", "∑", "∫", " = ")):
        return "equation_derivation"
    if any(k in scene_blob for k in ("timeline", "historically", "century", "era", "revolution", "treaty", "176", "177", "183", "19th", "20th")):
        return "history_timeline"
    if any(k in scene_blob for k in ("spatial distribution", "distribution map", "map", "region", "continent", "topology", "geography", "ecosystem")):
        return "geo_concept_map"
    if any(k in full_blob for k in ("chloroplast", "calvin", "thylakoid", "mitochondri", "atp", "photosynthesis", "respiration", "glycolysis", "fermentation", "cell", "membrane", "proton gradient", "organelle")):
        return "biology_organelle"
    if any(k in full_blob for k in ("b-tree", "btree", "binary tree", "scheduling", "priority", "starvation", "indexing", "algorithm", "hash", "queue", "graph", "database", "node split")):
        return "cs_tree_algorithm"
    if any(k in full_blob for k in ("inflation", "interest rate", "monetary", "central bank", "reserve", "supply", "demand", "gdp", "fiscal", "bond", "equilibrium", "elasticity")):
        return "economics_curve"
    if any(k in full_blob for k in ("steam", "watt", "factory", "empire", "war", "historical")):
        return "history_timeline"
    return "diagram_flow"


def _extract_step_clauses(text: str) -> List[str]:
    """Splits a complex mechanism explanation into sequential causal/process steps."""
    parts = re.split(r"(?:\s*;\s*|\s*->\s*|\s+(?:then|next|subsequently|finally|followed by|which triggers|causing|leading to)\s+)", text, flags=re.IGNORECASE)
    cleaned = [_clean_text(p) for p in parts if len(_clean_text(p)) >= 18]
    return cleaned


def analyze_source_complexity_and_concepts(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes complete source evidence to identify distinct concepts, prerequisites,
    mechanisms, comparisons, equations, examples, and conceptual complexity tier.
    """
    facts = evidence.get("fact_items") or []
    sections = _dedupe_preserve_order([f.get("section_title") or "" for f in facts if f.get("section_title")])
    concept_groups: List[Dict[str, Any]] = []
    by_key: Dict[str, Dict[str, Any]] = {}

    for f in facts:
        label = _clean_text(f.get("label") or "Core Concept")
        sec = _clean_text(f.get("section_title") or "")
        key = f"{sec.lower()}::{label.lower()[:36]}"
        if key not in by_key:
            grp = {
                "key": key,
                "label": label,
                "section": sec,
                "category": f.get("category") or "Concept",
                "facts": [],
                "citations": [],
                "steps": [],
            }
            by_key[key] = grp
            concept_groups.append(grp)
        grp = by_key[key]
        grp["facts"].append(f)
        cite = _format_ref_citation(f)
        if cite not in grp["citations"]:
            grp["citations"].append(cite)
        step_clauses = _extract_step_clauses(f.get("text", ""))
        if len(step_clauses) >= 2 or f.get("category") == "Mechanism":
            grp["steps"].extend(step_clauses)

    n_concepts = len(concept_groups)
    n_mechanisms = len(evidence.get("mechanisms") or [])
    n_sections = max(1, len(sections))
    complexity_score = n_concepts + (n_mechanisms * 1.2) + (max(0, n_sections - 1) * 1.5)

    if complexity_score <= 4.5 and n_concepts <= 3:
        tier = "simple"
    elif complexity_score <= 11.0 and n_concepts <= 7:
        tier = "moderate"
    else:
        tier = "complex"

    return {
        "complexity_tier": tier,
        "complexity_score": round(complexity_score, 2),
        "concept_count": n_concepts,
        "mechanism_count": n_mechanisms,
        "section_count": n_sections,
        "concept_groups": concept_groups,
    }


def _clean_scene_label(raw: str) -> str:
    txt = _clean_text(raw)
    words = txt.split()
    trailing_stops = {"the", "a", "an", "as", "in", "on", "at", "to", "for", "of", "with", "by", "and", "or", "from", "into"}
    while len(words) > 2 and words[-1].lower().strip(".,;:") in trailing_stops:
        words.pop()
    return " ".join(words)


def _word_safe_clip(text: str, limit: int = 28) -> str:
    t = _clean_text(text)
    if len(t) <= limit:
        return t
    clipped = t[:limit].rsplit(" ", 1)[0]
    return clipped if len(clipped) >= 8 else t[:limit]


def _build_scene_from_facts(
    sc_num: int,
    title: str,
    topic: str,
    facts: List[Dict[str, Any]],
    cites: List[str],
    spoken_normalizer_fn: Optional[Callable[[str], str]] = None,
    objective_prefix: str = "Explain",
    step_badge: str = "",
) -> Dict[str, Any]:
    clean_title = _clean_scene_label(title)
    narr_text = " ".join(f["text"] for f in facts[:3])
    if sc_num == 1:
        narr_text = f"Welcome to this BRAINOVA video overview on {topic}. {narr_text}"
    spoken = spoken_normalizer_fn(narr_text) if spoken_normalizer_fn else narr_text
    word_count = max(12, len(spoken.split()))
    dur = max(8, min(32, int(round(word_count * 0.45))))
    primary = facts[0]
    nodes = [f"{n_i + 1}. {_word_safe_clip(f['label'], 26)}" for n_i, f in enumerate(facts[:4])]
    if len(nodes) < 3 and len(facts) == 1:
        clauses = _extract_step_clauses(facts[0]["text"])
        if len(clauses) >= 2:
            nodes = [f"{n_i + 1}. {_word_safe_clip(c, 26)}" for n_i, c in enumerate(clauses[:4])]
        else:
            # Split single sentence into meaningful phrase segments rather than generic padding
            phrase_parts = [p.strip() for p in re.split(r"\s*,\s*|\s+(?:of|and|through|across|into|using)\s+", facts[0]["text"]) if len(p.strip()) >= 8]
            if len(phrase_parts) >= 2:
                nodes = [f"{n_i + 1}. {_word_safe_clip(p, 26)}" for n_i, p in enumerate(phrase_parts[:3])]
    while len(nodes) < 3:
        fallback_lbl = clean_title if len(nodes) == 0 else (primary.get("section_title") or primary["category"])
        nodes.append(f"{len(nodes) + 1}. {_word_safe_clip(fallback_lbl, 26)}")
    v_mode = _infer_scene_visual_mode(topic, narr_text, primary["category"])
    return {
        "scene_number": sc_num,
        "title": f"{sc_num}. {clean_title}" + (f" ({step_badge})" if step_badge else ""),
        "duration_sec": dur,
        "duration_seconds": dur,
        "educational_objective": f"{objective_prefix} {clean_title} using evidence from {', '.join(cites)}.",
        "visual_mode": v_mode,
        "source_citation": ", ".join(cites),
        "narration": narr_text,
        "spoken_text": spoken,
        "caption": f"{clean_title} ({', '.join(cites)})",
        "on_screen_text": f"{clean_title} — {step_badge or primary['category']}",
        "visual_direction": f"{v_mode} Visual Explanation",
        "visual_description": f"Adaptive {primary['category'].lower()} visualization grounded in {', '.join(cites)}.",
        "key_terms": _dedupe_preserve_order([_clean_scene_label(f["label"]) for f in facts[:4]]),
        "key_points": [f["text"] for f in facts[:3]],
        "diagram_nodes": nodes,
        "covered_concepts": _dedupe_preserve_order([f["label"] for f in facts]),
    }


def _measure_conceptual_coverage(
    concept_groups: List[Dict[str, Any]],
    scenes: List[Dict[str, Any]],
) -> Tuple[float, List[Dict[str, Any]]]:
    """Measures which source concept groups are covered by planned scenes."""
    if not concept_groups:
        return 1.0, []
    scene_blob = " ".join(
        " ".join([
            str(s.get("title") or ""),
            str(s.get("narration") or ""),
            " ".join(str(k) for k in (s.get("key_points") or [])),
            " ".join(str(t) for t in (s.get("key_terms") or [])),
            " ".join(str(c) for c in (s.get("covered_concepts") or [])),
        ])
        for s in scenes
    ).lower()

    uncovered: List[Dict[str, Any]] = []
    for grp in concept_groups:
        label_words = [w for w in re.findall(r"[a-z0-9]{4,}", grp["label"].lower())]
        fact_words = [w for w in re.findall(r"[a-z0-9]{5,}", grp["facts"][0]["text"].lower())][:4] if grp["facts"] else []
        tokens = label_words or fact_words
        if tokens and not any(tok in scene_blob for tok in tokens[:3]):
            uncovered.append(grp)
    covered_count = len(concept_groups) - len(uncovered)
    ratio = round(covered_count / max(1, len(concept_groups)), 3)
    return ratio, uncovered


def generate_video_storyboard_grounded(
    chunks: List[Dict[str, Any]],
    config: Dict[str, Any],
    user_prefs: Optional[Dict[str, Any]],
    call_llm_json_fn: Callable[..., Tuple[Optional[Any], str]],
    normalize_language_fn: Callable[[str], str],
    spoken_normalizer_fn: Optional[Callable[[str], str]] = None,
    is_plausible_chunk_fn: Optional[Callable[[str], bool]] = None,
    source_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generates a source-grounded, domain-neutral educational Video Overview storyboard
    across all 6 supported languages (English, Telugu, Hindi, Kannada, Tamil, Marathi).
    Separates visual `narration`/`caption` from TTS-safe `spoken_text`.
    """
    evidence = build_studio_evidence_model(chunks, config, is_plausible_chunk_fn)
    _ensure_source_evidence_if_ids_given(source_ids, evidence)

    language = normalize_language_fn(config.get("language", "English"))
    duration_label = _clean_text(config.get("duration") or config.get("video_duration") or "Adaptive (Content-Driven)")
    style_label = _clean_text(config.get("style") or "Concept Breakdown & Visual Synthesis")
    topic = evidence["topic"]
    analysis = analyze_source_complexity_and_concepts(evidence)
    concept_groups = analysis["concept_groups"]

    lang_note = (
        f" Write ALL output fields (title, summary, scene titles, narration, spoken_text, caption, on_screen_text, key_points, diagram_nodes) strictly in {language} using native {language} script."
        if language != "English"
        else ""
    )
    prompt = (
        f"Create an adaptive, cinematic educational Video Overview storyboard JSON for '{topic}' "
        f"(Style: {style_label}, Detected Complexity: {analysis['complexity_tier']}, Concepts: {analysis['concept_count']}).{lang_note}\n"
        f"{_wrap_untrusted_context(evidence)}\n\n"
        "Requirements:\n"
        "- Do NOT use a fixed scene count. Plan as many scenes as needed so every important concept, prerequisite, mechanism, example, and comparison is clearly taught.\n"
        "- Break complicated multi-step mechanisms into multiple sequential scenes.\n"
        "- Choose the best visual_mode per scene from: biology_organelle, cs_tree_algorithm, economics_curve, history_timeline, equation_derivation, comparison_matrix, geo_concept_map, diagram_flow.\n"
        "- Ground every claim in the source material and adapt vocabulary strictly to the subject domain.\n"
        "- Each scene must include concise on_screen key_points (2-4 items) and 3-4 diagram_nodes showing the concept flow.\n"
        "- Include both visual 'narration' and TTS-friendly 'spoken_text' (spell out chemical formulas/symbols if needed).\n"
        "Return JSON with keys: title, summary, scenes (array of {scene_number, title, duration_sec, visual_mode, educational_objective, source_citation, narration, spoken_text, "
        "caption, on_screen_text, visual_direction, visual_description, key_terms, key_points, diagram_nodes})."
    )

    llm_data, provider = call_llm_json_fn(
        "You are an expert educational film director creating strictly source-grounded, adaptive video storyboards.",
        prompt,
        user_prefs=user_prefs,
    )

    scenes: List[Dict[str, Any]] = []
    out_title = _clean_text(config.get("title")) or ""
    resource_guard_applied = False
    if isinstance(llm_data, dict) and isinstance(llm_data.get("scenes"), list) and len(llm_data["scenes"]) >= 1:
        out_title = out_title or _clean_text(llm_data.get("title")) or f"Video Overview: {topic}"
        raw_scenes = llm_data["scenes"]
        if len(raw_scenes) > MAX_ADAPTIVE_SCENES:
            raw_scenes = raw_scenes[:MAX_ADAPTIVE_SCENES]
            resource_guard_applied = True
        for idx, raw_s in enumerate(raw_scenes, start=1):
            if not isinstance(raw_s, dict):
                continue
            narr = _clean_text(raw_s.get("narration") or raw_s.get("on_screen_text") or "")
            if not narr:
                continue
            spoken = _clean_text(raw_s.get("spoken_text") or narr)
            if language == "English" and spoken_normalizer_fn:
                spoken = spoken_normalizer_fn(spoken)
            dur = max(6, int(raw_s.get("duration_sec") or raw_s.get("duration_seconds") or max(8, round(len(spoken.split()) * 0.45))))
            kpts = [_clean_text(k) for k in (raw_s.get("key_points") or []) if _clean_text(k)][:4] or [narr[:90]]
            dnodes = [_clean_text(d) for d in (raw_s.get("diagram_nodes") or []) if _clean_text(d)][:4] or [
                _clean_text(raw_s.get("title") or f"Stage {idx}")[:35]
            ]
            v_mode = _clean_text(raw_s.get("visual_mode") or "") or _infer_scene_visual_mode(topic, narr)
            scenes.append({
                "scene_number": len(scenes) + 1,
                "title": _clean_text(raw_s.get("title") or f"Scene {len(scenes) + 1}"),
                "duration_sec": dur,
                "duration_seconds": dur,
                "educational_objective": _clean_text(raw_s.get("educational_objective") or f"Understand {_clean_text(raw_s.get('title') or topic)}"),
                "visual_mode": v_mode,
                "source_citation": _clean_text(raw_s.get("source_citation") or ""),
                "narration": narr,
                "spoken_text": spoken,
                "caption": _clean_text(raw_s.get("caption") or narr[:120]),
                "on_screen_text": _clean_text(raw_s.get("on_screen_text") or raw_s.get("title") or topic),
                "visual_direction": _clean_text(raw_s.get("visual_direction") or "Animated Concept Flow"),
                "visual_description": _clean_text(raw_s.get("visual_description") or "Animated 3D-layered concept diagram."),
                "key_terms": [_clean_text(t) for t in (raw_s.get("key_terms") or []) if _clean_text(t)][:4],
                "key_points": kpts,
                "diagram_nodes": dnodes,
            })

    mechanism_steps_decomposed = 0
    batch_offset = max(0, int(config.get("batch_offset") or 0))
    batch_limit = max(1, min(MAX_ADAPTIVE_SCENES, int(config.get("batch_limit") or MAX_ADAPTIVE_SCENES)))
    if not scenes:
        if language != "English":
            raise StudioGenerationError(
                f"Generating a source-grounded Video Overview in {language} requires an active Gemini, OpenAI, or Anthropic API key configured in Settings.",
                code="llm_required_for_language",
                status_code=422,
            )
        provider = "local_adaptive_engine"
        out_title = out_title or f"Video Overview: {topic}"
        facts = evidence["fact_items"]
        if not facts:
            scenes = [
                {
                    "scene_number": 1,
                    "title": f"1. Introduction: {topic}",
                    "duration_sec": 12,
                    "duration_seconds": 12,
                    "educational_objective": f"Introduce {topic}",
                    "visual_mode": "diagram_flow",
                    "source_citation": topic,
                    "narration": f"Welcome to this BRAINOVA educational video overview on {topic}. Select a source document to synthesize page-cited visual scenes.",
                    "spoken_text": f"Welcome to this BRAINOVA educational video overview on {topic}. Select a source document to synthesize page-cited visual scenes.",
                    "caption": f"{topic} — Overview",
                    "on_screen_text": f"{topic} — Visual Study Overview",
                    "visual_direction": "3D Perspective Title & Scope",
                    "visual_description": "Animated introduction card with topic scope.",
                    "key_terms": [topic],
                    "key_points": [f"Topic focus: {topic}", "Attach a ready source document for detailed, page-cited explanations."],
                    "diagram_nodes": ["1. Topic Scope", "2. Core Concepts", "3. Evidence", "4. Synthesis"],
                },
            ]
        else:
            # Adaptive scene planning driven by conceptual complexity & mechanism decomposition (no silent truncation)
            for grp in concept_groups:
                grp_facts = grp["facts"]
                if grp["category"] == "Mechanism" and len(grp_facts) >= 2:
                    for step_idx, f_step in enumerate(grp_facts, start=1):
                        mechanism_steps_decomposed += 1
                        scenes.append(
                            _build_scene_from_facts(
                                sc_num=len(scenes) + 1,
                                title=grp["label"],
                                topic=topic,
                                facts=[f_step],
                                cites=[_format_ref_citation(f_step)],
                                spoken_normalizer_fn=spoken_normalizer_fn,
                                objective_prefix="Trace step-by-step",
                                step_badge=f"Step {step_idx} of {len(grp_facts)}",
                            )
                        )
                elif len(grp["steps"]) >= 2:
                    base_fact = grp_facts[0]
                    for step_idx, step_txt in enumerate(grp["steps"], start=1):
                        mechanism_steps_decomposed += 1
                        step_fact = {**base_fact, "text": step_txt}
                        scenes.append(
                            _build_scene_from_facts(
                                sc_num=len(scenes) + 1,
                                title=grp["label"],
                                topic=topic,
                                facts=[step_fact],
                                cites=grp["citations"],
                                spoken_normalizer_fn=spoken_normalizer_fn,
                                objective_prefix="Trace step-by-step",
                                step_badge=f"Step {step_idx} of {len(grp['steps'])}",
                            )
                        )
                else:
                    scenes.append(
                        _build_scene_from_facts(
                            sc_num=len(scenes) + 1,
                            title=grp["label"],
                            topic=topic,
                            facts=grp_facts,
                            cites=grp["citations"],
                            spoken_normalizer_fn=spoken_normalizer_fn,
                        )
                    )

    # Measure conceptual coverage across the full plan & auto-append scenes for any uncovered source concepts
    coverage_ratio, uncovered_groups = _measure_conceptual_coverage(concept_groups, scenes)
    if uncovered_groups and language == "English":
        for grp in uncovered_groups:
            scenes.append(
                _build_scene_from_facts(
                    sc_num=len(scenes) + 1,
                    title=grp["label"],
                    topic=topic,
                    facts=grp["facts"],
                    cites=grp["citations"],
                    spoken_normalizer_fn=spoken_normalizer_fn,
                    objective_prefix="Cover missing concept",
                )
            )
        coverage_ratio, uncovered_groups = _measure_conceptual_coverage(concept_groups, scenes)

    total_planned_scenes = len(scenes)
    batch_scenes = scenes[batch_offset : batch_offset + batch_limit]
    for b_idx, sc in enumerate(batch_scenes, start=1):
        sc["global_scene_number"] = sc.get("scene_number", batch_offset + b_idx)
        sc["scene_number"] = b_idx
    has_more_batches = (batch_offset + len(batch_scenes)) < total_planned_scenes
    next_batch_offset = (batch_offset + len(batch_scenes)) if has_more_batches else None
    remaining_scenes = max(0, total_planned_scenes - (batch_offset + len(batch_scenes)))
    resource_guard_applied = resource_guard_applied or (total_planned_scenes > batch_limit)

    return {
        "title": out_title,
        "language": language,
        "duration_label": duration_label,
        "style_label": style_label,
        "render_status": "playable_1080p_video_ready",
        "provider_notice": f"1080p Full HD animated educational video synthesized in {language} ({len(batch_scenes)} of {total_planned_scenes} adaptive scenes).",
        "total_duration_seconds": sum(s["duration_seconds"] for s in batch_scenes),
        "scenes": batch_scenes,
        "planning_metrics": {
            "complexity_tier": analysis["complexity_tier"],
            "complexity_score": analysis["complexity_score"],
            "concept_count": analysis["concept_count"],
            "total_planned_scenes": total_planned_scenes,
            "planned_scenes": len(batch_scenes),
            "batch_offset": batch_offset,
            "batch_limit": batch_limit,
            "has_more_batches": has_more_batches,
            "next_batch_offset": next_batch_offset,
            "remaining_scenes": remaining_scenes,
            "mechanism_steps_decomposed": mechanism_steps_decomposed,
            "coverage_ratio": coverage_ratio,
            "uncovered_concepts": [g["label"] for g in uncovered_groups],
            "resource_guard_applied": resource_guard_applied,
            "max_adaptive_scenes": MAX_ADAPTIVE_SCENES,
        },
        "source_references": evidence["source_references"],
        "generation_provider": provider,
    }


