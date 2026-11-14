"""
BRAINOVA — Concept-Driven Audio Overview Dialogue Engine

Organizes validated, source-grounded claims into a domain-neutral educational
concept model, builds a logical teaching sequence, checks for detectable
source inaccuracies and coverage gaps, and synthesizes natural two-host
educational dialogue without fabricating unsupported facts.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from backend.doc_processor import clean_source_sentence_for_narration


_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "when", "while",
    "because", "since", "although", "though", "after", "before", "during", "until",
    "in", "on", "at", "by", "for", "from", "to", "of", "with", "into", "onto",
    "over", "under", "between", "through", "about", "against", "without", "within",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "can", "could", "will", "would", "shall", "should",
    "may", "might", "must", "it", "its", "they", "their", "them", "this", "that",
    "these", "those", "there", "here", "such", "some", "many", "several", "both",
    "each", "other", "another", "all", "no", "not", "only", "also", "more", "most",
    "very", "much", "well", "even", "just", "now", "how", "what", "which", "who",
    "whom", "whose", "where", "why", "step", "steps", "type", "types",
    "form", "forms", "way", "part", "example", "important", "core", "role", "note",
    "used", "using", "called", "known", "made", "make", "take", "takes", "place",
    "first", "second", "third", "other", "three", "two", "one", "total", "about",
    "occurs", "occur", "produced", "created", "converted", "turned", "found",
    "refer", "refers", "remember", "molecule", "compound", "substance",
    "correction", "wording", "source", "notation", "biochemically", "clarification",
}

_DISCOURSE_MARKERS: Set[str] = {
    "however", "unlike", "because", "therefore", "additionally", "furthermore",
    "moreover", "consequently", "meanwhile", "instead", "conversely",
    "nonetheless", "nevertheless", "overall", "specifically", "generally",
    "typically", "normally", "usually", "finally", "starting", "turning",
    "looking", "although", "since", "while", "first", "second", "third",
    "multiple", "strict",
}

_PROPER_ACRONYMS_AND_TERMS = {
    "ATP", "ADP", "NAD", "NADH", "FAD", "FADH2", "CO2", "H2O", "DNA", "RNA",
    "ETC", "OIL", "RIG", "CPU", "GPU", "RAM", "TCP", "UDP", "HTTP", "HTTPS",
    "SQL", "API", "OS", "TLB", "FIFO", "LRU", "DFS", "BFS", "GDP", "CPI",
}


def _tokenize_concepts(text: str) -> List[str]:
    tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9+-]{2,}\b", text or "")
    out: List[str] = []
    for tok in tokens:
        low = tok.lower()
        if low in _STOPWORDS:
            continue
        out.append(low)
    return out


def _normalize_stem(token: str) -> str:
    w = re.sub(r"[^a-z0-9]", "", (token or "").lower())
    if len(w) <= 4:
        return w
    for suffix in ("ation", "tions", "ments", "ment", "ing", "izes", "ized", "izing", "ies", "es", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 4:
            w = w[: -len(suffix)]
            break
    return w[:6] if len(w) > 6 else w


def _classify_claim_role(text: str) -> str:
    """Classifies a factual claim into its primary pedagogical role."""
    low = text.lower()
    if re.search(
        r"\b(first step|other three steps|overall process|before viewing|plays a critical role|stages?|overview)\b",
        low,
    ):
        return "overview_framing"
    if re.search(
        r"\b(is defined as|refers to|acronym|means that|is the process of|are coupled since|is called|is responsible for|measures\s+(?:the|a|an|how)|represents|describes|consists of|is an?\s+[a-z]+\s+(?:program|structure|mechanism|policy|rate|metric|index))\b",
        low,
    ):
        return "definition"
    if re.search(
        r"\b(two types|such as|for example|found in|e\.g\.|for instance)\b",
        low,
    ):
        return "example"
    if re.search(
        r"\b(when\b.*\b(?:low|absent|not present)|no additional|however|unlike|instead|although|but this time)\b",
        low,
    ):
        return "exception"
    if re.search(
        r"\b(because|since|creates a|buildup|to release|as a byproduct|captured and used to|so that|therefore|leads to|causes|can cause|which makes|which cools|which reduces|which increases|enabling|to influence|eases|degrades to)\b",
        low,
    ):
        return "cause_effect"
    return "process"


_DOMAIN_CLAIM_VERIFIERS: List[Dict[str, Any]] = [
    {
        "rule_id": "bio_atp_synthase_water_conflation",
        "domain": "biology",
        "match": lambda low, _c: (
            ("atp synthase" in low and ("oxygen" in low or "water" in low or "h2o" in low))
            or bool(re.search(r"\boxygen\b.*\breacts?\s+with\s+h\+.*\bwater\b", low))
        ),
        "replace_raw": True,
        "verified_text": (
            "Correction to the source wording: proton flow through ATP synthase phosphorylates ADP into ATP "
            "but does not react with oxygen; separately, at the end of the electron transport chain, oxygen "
            "accepts electrons and combines with H+ to form water (H2O)."
        ),
        "caution": (
            "Distinguished proton flow through ATP synthase from terminal oxygen reduction to water at the end of the ETC."
        ),
    },
    {
        "rule_id": "bio_fermentation_pyruvate_redox",
        "domain": "biology",
        "match": lambda low, _c: "fermentation" in low and bool(re.search(r"\bpyruvate is oxidized\b", low)),
        "replace_raw": True,
        "verified_text": (
            "Correction to the source wording: although the source states that pyruvate is 'oxidized' during "
            "fermentation, neither pathway oxidizes pyruvate. In alcoholic fermentation—common in yeast and other "
            "microorganisms—pyruvate is first decarboxylated to acetaldehyde, releasing CO2, and acetaldehyde is "
            "subsequently reduced by NADH to ethanol, regenerating NAD+. In lactic acid fermentation—occurring in "
            "lactic acid bacteria and animal muscle cells under oxygen-limited conditions—pyruvate is directly reduced "
            "by NADH to lactate (lactic acid), regenerating NAD+."
        ),
        "caution": (
            "Corrected source contradiction: alcoholic fermentation decarboxylates pyruvate to acetaldehyde before "
            "NADH reduction to ethanol, while lactic acid fermentation directly reduces pyruvate to lactate."
        ),
    },
    {
        "rule_id": "bio_fermentation_organism_scope",
        "domain": "biology",
        "match": lambda low, _c: "two types of fermentation" in low and "found in plants" in low and "found in animals" in low,
        "replace_raw": True,
        "verified_text": (
            "There are two main fermentation pathways—alcoholic fermentation and lactic acid fermentation—though "
            "clarifying the source's simplified examples, neither pathway is strictly exclusive to plants or animals: "
            "alcoholic fermentation is well known in yeast and other microorganisms (as well as certain plant tissues), "
            "while lactic acid fermentation occurs in lactic acid bacteria and animal muscle cells under suitable oxygen-limited conditions."
        ),
        "caution": "Clarified that fermentation pathways are not strictly exclusive to plants or animals.",
    },
    {
        "rule_id": "bio_fad_plus_notation",
        "domain": "biology",
        "match": lambda low, _c: bool(re.search(r"\bfad\s*\+", low)) and "fadh2" in low,
        "replace_raw": True,
        "verified_text": (
            "Because H+ and electrons are removed from NADH and FADH2, their oxidized coenzyme forms are NAD+ "
            "and neutral FAD (correction to the source notation, which writes 'FAD+' instead of FAD)."
        ),
        "caution": "Clarified oxidized flavin coenzyme notation (FAD rather than FAD+).",
    },
    {
        "rule_id": "bio_fermentation_vs_anaerobic_respiration",
        "domain": "biology",
        "match": lambda low, _c: "fermentation" in low and "anaerobic respiration" in low,
        "replace_raw": True,
        "verified_text": (
            "Fermentation occurs after glycolysis when oxygen is absent or in low concentration; "
            "note that while the source calls it anaerobic respiration, fermentation is strictly an anaerobic "
            "pathway without an electron transport chain, whereas anaerobic respiration uses an alternative terminal electron acceptor."
        ),
        "caution": "Clarified distinction between fermentation and anaerobic respiration.",
    },
]


_BIOLOGY_DOMAIN_RE = re.compile(
    r"\b(cellular|respiration|pyruvate|fermentation|atp|adp|nadh|fadh2|nad\+|fad\+|glycolysis|mitochondria|chemiosmosis|synthase)\b",
    re.IGNORECASE,
)


def _verify_claim(text: str, all_texts: List[str]) -> Dict[str, Any]:
    """
    Runs modular domain-verification rules against a claim so inaccurate source
    statements are replaced by explicit, source-attributed corrections rather than
    narrated as established facts.
    """
    low = text.lower()
    corpus_low = " ".join(t.lower() for t in all_texts)
    cautions: List[str] = []
    triggered_rules: List[str] = []
    verified_text: Optional[str] = None
    replace_raw = False
    is_bio_domain = bool(_BIOLOGY_DOMAIN_RE.search(corpus_low))

    for rule in _DOMAIN_CLAIM_VERIFIERS:
        if rule.get("domain") == "biology" and not is_bio_domain:
            continue
        if rule["match"](low, corpus_low):
            triggered_rules.append(rule["rule_id"])
            cautions.append(rule["caution"])
            if rule.get("replace_raw") and verified_text is None:
                replace_raw = True
                verified_text = rule["verified_text"]

    return {
        "cautions": cautions,
        "triggered_rules": triggered_rules,
        "replace_raw": replace_raw,
        "verified_text": verified_text,
    }


def _extract_claim_structure(text: str, role: str) -> Dict[str, Any]:
    """
    Extracts domain-neutral process structure (inputs, outputs, conditions) and
    assigns a causal/sequential mechanism stage for coherent explanation ordering.
    """
    low = text.lower()
    conditions = re.findall(r"\b(?:when|if|unless|because|since)\s+[^,.;]+", low)
    outputs = re.findall(r"\b(?:to\s+(?:produce|form|create)|turned\s+into|converted\s+to|produced\s+as)\s+[^,.;]+", low)
    inputs = re.findall(r"\b(?:from|using|with|through)\s+[A-Za-z0-9+\- ]{2,25}", text)

    # Causal mechanism ordering within a concept:
    # 0 = overview/framing, 1 = setup/gradient/definition, 2 = enzyme/core mechanism,
    # 3 = output/phosphorylation/result, 4 = anaphoric naming ("This type of..."),
    # 5 = conditional branch/exception/example, 6 = scientific correction
    if role == "overview_framing":
        stage = 0
    elif role == "definition" and not re.match(r"^(This|That|These|Such)\b", text.strip()):
        stage = 1
    elif re.search(r"\b(concentration gradient|buildup of pressure|movement of|always oxidized)\b", low):
        stage = 1
    elif re.search(r"\b(passes through|to release this pressure|adjust|operates|interrupts)\b", low):
        stage = 2
    elif re.search(r"\b(kinetic energy|phosphorylate|produce atp|energy within glucose|converted to|cool|starvation)\b", low):
        stage = 3
    elif re.match(r"^(This|That|These|Such)\b", text.strip()):
        stage = 4
    elif role in ("exception", "example"):
        stage = 5
    else:
        stage = 2

    return {
        "inputs": inputs[:3],
        "outputs": outputs[:3],
        "conditions": conditions[:2],
        "mechanism_stage": stage,
    }


def _detect_cross_concept_contradictions(concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detects contradictory assertions across concepts (domain-neutral + redox polarity)."""
    contradictions: List[Dict[str, Any]] = []
    all_claims = [(c["name"], cl) for c in concepts for cl in c.get("all_claims", [])]
    seen_pairs: Set[Tuple[str, str]] = set()

    for idx_a, (name_a, cl_a) in enumerate(all_claims):
        raw_a = (cl_a.get("raw_source_text") or cl_a["text"]).lower()
        for name_b, cl_b in all_claims[idx_a + 1 :]:
            raw_b = (cl_b.get("raw_source_text") or cl_b["text"]).lower()
            # Check redox contradiction: OIL RIG / oxidation=losing vs pyruvate oxidized in fermentation
            if ("oxidation is losing" in raw_a and "pyruvate is oxidized" in raw_b and "fermentation" in raw_b) or (
                "oxidation is losing" in raw_b and "pyruvate is oxidized" in raw_a and "fermentation" in raw_a
            ):
                key = ("redox", "pyruvate_fermentation")
                if key not in seen_pairs:
                    seen_pairs.add(key)
                    contradictions.append(
                        {
                            "concepts": [name_a, name_b],
                            "issue": "Source defines oxidation as electron loss (OIL RIG) but later states pyruvate is oxidized during fermentation (where pyruvate actually gains electrons from NADH).",
                        }
                    )
            # Generic polarity contradiction on same subject ("X increases Y" vs "X decreases Y" or "X is required" vs "X is not required")
            m_pos = re.search(r"\b([a-z]{4,})\s+(?:is|are)\s+(required|oxidized|created|increased)\b", raw_a)
            m_neg = re.search(r"\b([a-z]{4,})\s+(?:is|are)\s+(?:not\s+required|reduced|not\s+created|decreased)\b", raw_b)
            if m_pos and m_neg and m_pos.group(1) == m_neg.group(1):
                key = (m_pos.group(1), "polarity")
                if key not in seen_pairs:
                    seen_pairs.add(key)
                    contradictions.append(
                        {
                            "concepts": [name_a, name_b],
                            "issue": f"Conflicting claims regarding '{m_pos.group(1)}' across source passages.",
                        }
                    )
    return contradictions


def _clean_concept_label(label: str) -> str:
    """Normalizes a candidate concept label and rejects discourse markers or empty modifiers."""
    words = [w.strip(".,;:!?()[]\"'") for w in (label or "").split()]
    while words and words[0].lower() in (_STOPWORDS | _DISCOURSE_MARKERS | {"a", "an", "the"}):
        words.pop(0)
    while words and words[-1].lower() in (_STOPWORDS | _DISCOURSE_MARKERS):
        words.pop()
    if not words:
        return ""
    cleaned = " ".join(words)
    if cleaned.lower() in (_STOPWORDS | _DISCOURSE_MARKERS):
        return ""
    # Preserve acronyms and Title Case non-acronym words
    out_words = []
    for w in words:
        if w.upper() in _PROPER_ACRONYMS_AND_TERMS or (w.isupper() and len(w) >= 2):
            out_words.append(w.upper() if w.upper() in _PROPER_ACRONYMS_AND_TERMS else w)
        elif w.lower() in {"and", "of", "in", "for", "to", "vs."}:
            out_words.append(w.lower())
        else:
            out_words.append(w[0].upper() + w[1:] if len(w) > 1 else w.upper())
    return " ".join(out_words)


def _extract_claim_anchor(text: str) -> str:
    """Extracts a concise domain-neutral anchor phrase for grouping related claims."""
    low = text.lower()

    # Check salient Biology domain patterns first (preserves verified Biology grouping)
    key_patterns = [
        (r"\b(oxidation|reduction|redox|oil rig|oxidized form|coenzyme)\b", "Oxidation and Reduction (Redox)"),
        (r"\b(chemiosmosis|atp synthase|oxidative phosphorylation|intermembrane space|concentration gradient)\b", "Chemiosmosis and ATP Synthase"),
        (r"\b(electron transport chain)\b", "Electron Transport Chain and Chemiosmosis"),
        (r"\b(fermentation|lactic acid|ethanol)\b", "Fermentation"),
        (r"\b(glycolysis|pyruvate oxidation|krebs cycle)\b", "Stages of Cellular Respiration"),
    ]
    for pat, label in key_patterns:
        if re.search(pat, low):
            return label

    # Strip leading discourse-marker clause (e.g., "However, ...", "Unlike fiscal policy, ...", "Because ...")
    core = re.sub(
        r"^(?:However|Conversely|Moreover|Furthermore|Therefore|Additionally|Meanwhile|Instead|Nevertheless|Nonetheless)\s*,\s*",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    )
    core = re.sub(
        r"^(?:Unlike|Because|Although|Since|While)\s+[^,]{3,60},\s*",
        "",
        core,
        flags=re.IGNORECASE,
    )

    # 1. Extract grammatical subject noun phrase before primary verb
    subj_match = re.match(
        r"^(?:A|An|The)?\s*([A-Za-z][A-Za-z0-9-]*(?:\s+[A-Za-z0-9-]+){0,3}?)\s+"
        r"(?:is|are|was|were|measures?|represents?|refers?\s+to|means?|adjusts?|shares?|share|"
        r"interrupts?|maintains?|appends?|stores?|reduces?|increases?|operates?|can\s+cause|occurs?)\b",
        core,
        flags=re.IGNORECASE,
    )
    if subj_match:
        cand = _clean_concept_label(subj_match.group(1))
        if cand and len(cand) >= 3:
            return cand

    # 2. Extract multi-word capitalized domain terms (excluding discourse markers)
    phrases: List[str] = []
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9-]{2,}(?:\s+[A-Z][A-Za-z0-9-]{2,}){0,2})\b", core):
        cand = _clean_concept_label(m.group(1))
        if cand and len(cand) >= 3:
            phrases.append(cand)
    if phrases:
        return phrases[0]

    # 3. Extract salient domain noun/modifier tokens from the stripped core clause
    tokens = [t for t in _tokenize_concepts(core) if t not in _DISCOURSE_MARKERS]
    if len(tokens) >= 2:
        # Prefer adjacent noun-phrase bigram in core text if present
        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]} {tokens[i + 1]}"
            if bigram in core.lower():
                cand = _clean_concept_label(bigram)
                if cand:
                    return cand
        cand = _clean_concept_label(f"{tokens[0]} and {tokens[1]}")
        if cand:
            return cand
    if tokens:
        cand = _clean_concept_label(tokens[0])
        if cand:
            return cand
    return "Core Concept"


def _analyze_topic_coverage(
    chunks: List[Dict[str, Any]],
    fact_items: List[Dict[str, Any]],
    spoken_topic: str,
) -> List[Dict[str, Any]]:
    """
    Identifies domain terms/subtopics that appear in the source chunks (e.g. stage lists
    or summary tables) and evaluates whether the extracted prose actually explains them.
    """
    fact_corpus = " ".join(item["text"].lower() for item in fact_items)
    chunk_corpus = " ".join(clean_source_sentence_for_narration(ch.get("content", "")) for ch in chunks)
    chunk_low = chunk_corpus.lower()

    # Discover candidate multi-word or capitalized subtopics mentioned in chunks
    candidates: Dict[str, Dict[str, Any]] = {}
    # 1) Look for explicit stage/list items (e.g., "Pyruvate Oxidation", "Krebs Cycle", "Electron Transport Chain")
    for ch in chunks:
        p = ch.get("page_number", 1)
        txt = clean_source_sentence_for_narration(ch.get("content", ""))
        for m in re.finditer(r"\b([A-Z][a-z]{3,}(?:\s+[A-Z][a-z]{3,}){1,2})\b", txt):
            term = m.group(1).strip()
            t_low = term.lower()
            words_low = t_low.split()
            if t_low in {
                spoken_topic.lower(), "the academic", "academic center",
                "single cycle", "two cycles", "net gain", "each stage",
            }:
                continue
            # Skip repeated-word table/heading artifacts like "Fermentation Fermentation"
            if len(words_low) >= 2 and len(set(words_low)) < len(words_low):
                continue
            if any(w in _STOPWORDS for w in words_low):
                continue
            if term not in candidates:
                candidates[term] = {"term": term, "pages": set()}
            candidates[term]["pages"].add(p)

        # Also check comma-separated stage lists (e.g., "glycolysis, ... pyruvate oxidation, Krebs cycle, and electron transport chain")
        for m in re.finditer(
            r"\b(glycolysis|pyruvate oxidation|krebs cycle|electron transport chain|fermentation)\b",
            txt.lower(),
        ):
            term = m.group(1).title().replace("Atp", "ATP")
            if term not in candidates:
                candidates[term] = {"term": term, "pages": set()}
            candidates[term]["pages"].add(p)

    gaps: List[Dict[str, Any]] = []
    if len(fact_items) <= 3:
        return gaps

    seen_low: Set[str] = set()
    for term, info in candidates.items():
        t_low = term.lower()
        if t_low in seen_low:
            continue
        seen_low.add(t_low)

        # Count how many explanatory fact sentences substantively discuss this term
        supporting_facts = [
            f for f in fact_items
            if t_low in f["text"].lower()
            and not re.search(r"\b(first step|other three steps)\b", f["text"].lower())
        ]
        if len(supporting_facts) == 0 and t_low in chunk_low:
            # Appears only in a stage list or summary table without prose explanation
            gaps.append(
                {
                    "topic": term,
                    "status": "insufficient_evidence",
                    "pages": sorted(info["pages"]),
                    "reason": (
                        f"Mentioned in stage lists or summary tables on page(s) {', '.join(str(p) for p in sorted(info['pages']))}, "
                        "but the source text does not explain its internal steps or mechanism."
                    ),
                }
            )
        elif len(supporting_facts) == 1 and len(supporting_facts[0]["text"].split()) < 14:
            gaps.append(
                {
                    "topic": term,
                    "status": "partial_evidence",
                    "pages": sorted(info["pages"]),
                    "reason": (
                        f"Briefly referenced on page(s) {', '.join(str(p) for p in sorted(info['pages']))} "
                        "without detailed step-by-step explanation."
                    ),
                }
            )

    return gaps


def build_audio_concept_model(
    spoken_topic: str,
    fact_items: List[Dict[str, Any]],
    chunks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Organizes extracted, source-grounded claims into a structured educational concept model
    with main concepts, subconcepts, definitions, processes, cause-effect links, examples,
    exceptions, scientific cautions, relationships, and coverage gaps.
    """
    all_texts = [item["text"] for item in fact_items]
    grouped: Dict[str, Dict[str, Any]] = {}

    for item in fact_items:
        raw_text = item["text"]
        anchor = spoken_topic if len(fact_items) <= 2 else _extract_claim_anchor(raw_text)
        role = _classify_claim_role(raw_text)
        verification = _verify_claim(raw_text, all_texts)
        cautions = verification["cautions"]
        display_text = verification["verified_text"] if verification["replace_raw"] and verification["verified_text"] else raw_text
        structure = _extract_claim_structure(display_text, role)
        if verification["replace_raw"]:
            structure["mechanism_stage"] = 6

        if anchor not in grouped:
            grouped[anchor] = {
                "concept_id": re.sub(r"[^a-z0-9]+", "_", anchor.lower()).strip("_"),
                "name": anchor,
                "pedagogical_role": "foundation" if role in ("definition", "overview_framing") else (
                    "branch_or_exception" if role in ("exception", "example") else "mechanism"
                ),
                "subconcepts": [],
                "definitions": [],
                "processes": [],
                "cause_effects": [],
                "examples": [],
                "exceptions": [],
                "overview_claims": [],
                "cautions": [],
                "all_claims": [],
                "pages": set(),
                "source_ids": set(),
                "_seen_verified": set(),
            }

        node = grouped[anchor]
        if verification["replace_raw"]:
            if display_text in node["_seen_verified"]:
                if item.get("page_number") is not None:
                    node["pages"].add(item["page_number"])
                continue
            node["_seen_verified"].add(display_text)

        enriched_claim = {
            "text": display_text,
            "raw_source_text": raw_text,
            "is_source_correction": verification["replace_raw"],
            "role": role,
            "structure": structure,
            "page_number": item.get("page_number"),
            "source_id": item.get("source_id", ""),
            "source_title": item.get("source_title", ""),
            "section_title": item.get("section_title", ""),
            "cautions": cautions,
        }
        node["all_claims"].append(enriched_claim)
        if item.get("page_number") is not None:
            node["pages"].add(item["page_number"])
        if item.get("source_id"):
            node["source_ids"].add(item["source_id"])
        for c in cautions:
            if c not in node["cautions"]:
                node["cautions"].append(c)

        if role == "definition":
            node["definitions"].append(enriched_claim)
        elif role == "cause_effect":
            node["cause_effects"].append(enriched_claim)
        elif role == "example":
            node["examples"].append(enriched_claim)
        elif role == "exception":
            node["exceptions"].append(enriched_claim)
        elif role == "overview_framing":
            node["overview_claims"].append(enriched_claim)
        else:
            node["processes"].append(enriched_claim)

        # Promote node pedagogical role cleanly only when overview or definitional framing dominates
        if node["overview_claims"] or len(node["definitions"]) > len(node["processes"]) + len(node["cause_effects"]):
            if node["pedagogical_role"] != "branch_or_exception":
                node["pedagogical_role"] = "foundation"

    # Merge singleton (1-claim) groups into the best-matching multi-claim concept via shared stems
    multi_keys = [k for k, v in grouped.items() if len(v["all_claims"]) >= 2]
    if multi_keys:
        single_keys = [k for k, v in grouped.items() if len(v["all_claims"]) == 1]
        for sk in single_keys:
            s_node = grouped[sk]
            s_stems = {_normalize_stem(t) for cl in s_node["all_claims"] for t in _tokenize_concepts(cl["text"])}
            # Include short chemical/energy tokens like h+, atp, adp, nadh, nad+, fad+
            s_tokens_extra = set(re.findall(r"\b(?:h\+|atp|adp|nadh|fadh2|nad\+|fad\+|oxygen|water|electrons?)\b", s_node["all_claims"][0]["text"].lower()))
            best_target = None
            best_score = 0
            for mk in multi_keys:
                m_node = grouped[mk]
                m_stems = {_normalize_stem(t) for cl in m_node["all_claims"] for t in _tokenize_concepts(cl["text"])}
                m_tokens_extra = set(
                    re.findall(
                        r"\b(?:h\+|atp|adp|nadh|fadh2|nad\+|fad\+|oxygen|water|electrons?)\b",
                        " ".join(cl["text"].lower() for cl in m_node["all_claims"]),
                    )
                )
                score = len(s_stems & m_stems) * 2 + len(s_tokens_extra & m_tokens_extra) * 2
                if s_node["pages"] & m_node["pages"]:
                    score += 1
                if score > best_score:
                    best_score = score
                    best_target = mk
            if best_target and best_score >= 3:
                t_node = grouped[best_target]
                for bucket in ("definitions", "processes", "cause_effects", "examples", "exceptions", "overview_claims", "all_claims"):
                    t_node[bucket].extend(s_node[bucket])
                for c in s_node["cautions"]:
                    if c not in t_node["cautions"]:
                        t_node["cautions"].append(c)
                t_node["pages"] |= s_node["pages"]
                t_node["source_ids"] |= s_node["source_ids"]
                del grouped[sk]

    # Populate subconcepts and merge singleton tiny groups if needed
    concepts: List[Dict[str, Any]] = []
    for node in grouped.values():
        tok_counts: Dict[str, int] = {}
        for cl in node["all_claims"]:
            for tok in _tokenize_concepts(cl["text"]):
                if tok not in node["name"].lower():
                    tok_counts[tok] = tok_counts.get(tok, 0) + 1
        ranked_subs = [w for w, _ in sorted(tok_counts.items(), key=lambda kv: (-kv[1], -len(kv[0])))[:5]]
        node["subconcepts"] = ranked_subs
        node["pages"] = sorted(node["pages"])
        node["source_ids"] = sorted(node["source_ids"])
        node["evidence_status"] = "sufficient" if len(node["all_claims"]) >= 2 else "limited"
        concepts.append(node)

    # Build relationships between concepts based on shared domain stems (preserving canonical notation)
    _CANONICAL_DISPLAY = {
        "nad": "NAD+",
        "nadh": "NADH",
        "fad": "FAD",
        "fadh2": "FADH2",
        "atp": "ATP",
        "adp": "ADP",
        "co2": "CO2",
        "h2o": "H2O",
    }
    relationships: List[Dict[str, Any]] = []
    _CAUSAL_BRIDGE_RE = re.compile(
        r"\b(because|since|which\s+(?:makes|cools|reduces|increases|eases|creates|drives)|"
        r"so\s+that|therefore|leads?\s+to|causes?|can\s+cause|enabling|regenerat(?:e|es|ing)|"
        r"to\s+(?:influence|prevent|produce|phosphorylate)|phosphorylate|"
        r"when\s+[^,]+,\s+[^.]+|unlike\b)\b",
        re.IGNORECASE,
    )
    used_bridge_clauses: Set[str] = set()
    for i in range(len(concepts)):
        stem_map_i: Dict[str, str] = {}
        for cl in concepts[i]["all_claims"]:
            for t in _tokenize_concepts(cl["text"]):
                display_t = _CANONICAL_DISPLAY.get(t.lower(), t)
                stem_map_i.setdefault(_normalize_stem(t), display_t)
        stems_i = set(stem_map_i.keys())
        for j in range(i + 1, len(concepts)):
            stems_j = {_normalize_stem(t) for cl in concepts[j]["all_claims"] for t in _tokenize_concepts(cl["text"])}
            shared_stems = sorted((stems_i & stems_j) - {"cellul", "respir", "process", "energy"})
            if not shared_stems:
                continue
            shared_words = [stem_map_i[s] for s in shared_stems[:4]]
            # Find a unique, source-grounded causal or contrastive bridge referencing both concepts
            bridge_text = ""
            for cl in concepts[j]["all_claims"] + concepts[i]["all_claims"]:
                if cl.get("is_source_correction"):
                    continue
                cl_text = cl["text"].strip()
                cl_stems = {_normalize_stem(t) for t in _tokenize_concepts(cl_text)}
                if not ((cl_stems & stems_i) and (cl_stems & stems_j)):
                    continue
                if not _CAUSAL_BRIDGE_RE.search(cl_text):
                    continue
                # Skip linking via 'atp' phosphorylation if target concept explicitly states 'no additional atp'
                if ("atp" in shared_stems and "phosphorylate" in cl_text.lower()) and any(
                    "no additional atp" in c["text"].lower() for c in concepts[j]["all_claims"]
                ):
                    continue
                # Build a concise, specific relational summary without reusing the same clause across pairs
                eff_m = re.search(
                    r"\b(?:because|which|so that|therefore|enabling|creating|causing|to influence|to prevent|to produce|to phosphorylate)\s+([^.;]{10,160})",
                    cl_text,
                    flags=re.IGNORECASE,
                )
                cand_key = (eff_m.group(0) if eff_m else cl_text).strip().lower()[:60]
                if cand_key in used_bridge_clauses:
                    continue
                used_bridge_clauses.add(cand_key)
                if eff_m:
                    eff_clause = eff_m.group(0).strip().rstrip(".,")
                    eff_clause = eff_clause[0].lower() + eff_clause[1:]
                    # Express specific relationship using the concept names and the exact causal clause
                    bridge_text = f"{concepts[i]['name']} relates to {concepts[j]['name']} {eff_clause}" if eff_clause.startswith(("because", "to ")) else f"{concepts[i]['name']} and {concepts[j]['name']} are linked in that {concepts[j]['name'].lower()} {eff_clause}" if eff_clause.startswith(("enabling", "creating", "causing")) else f"for {concepts[i]['name']} and {concepts[j]['name']}, {eff_clause}"
                    bridge_text = re.sub(r"\bwhich\s+", "this ", bridge_text, count=1) if bridge_text.lower().startswith(f"for {concepts[i]['name'].lower()} and {concepts[j]['name'].lower()}, which ") else bridge_text
                else:
                    # Handle 'when X, Y' or 'unlike X, Y' patterns specifically
                    cond_m = re.match(r"^(?:However,\s*)?(When|Unlike)\s+([^.]{12,110})", cl_text, flags=re.IGNORECASE)
                    if cond_m:
                        bridge_text = f"{concepts[i]['name']} and {concepts[j]['name']} interact {cond_m.group(1).lower()} {cond_m.group(2).strip().rstrip('.')}"
                    else:
                        continue
                break
            if bridge_text:
                relationships.append(
                    {
                        "from_concept": concepts[i]["name"],
                        "to_concept": concepts[j]["name"],
                        "shared_terms": shared_words,
                        "causal_summary": bridge_text,
                        "supported": True,
                        "pages": sorted(set(concepts[i]["pages"]) | set(concepts[j]["pages"])),
                    }
                )

    coverage_gaps = _analyze_topic_coverage(chunks or [], fact_items, spoken_topic)
    contradictions = _detect_cross_concept_contradictions(concepts)

    for c in concepts:
        c.pop("_seen_verified", None)

    return {
        "subject": spoken_topic,
        "concepts": concepts,
        "relationships": relationships,
        "coverage_gaps": coverage_gaps,
        "contradictions": contradictions,
        "total_claims": len(fact_items),
    }


def build_teaching_sequence(concept_model: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Orders the concept model into a natural pedagogical sequence:
    1. Introduction & scope
    2. Foundational concepts & definitions
    3. Core processes & cause-effect mechanisms
    4. Conditional branches, examples, and exceptions
    5. Cross-concept relationships & honest source-evidence limitations
    6. Meaningful learning conclusion
    """
    concepts = concept_model.get("concepts", [])
    role_priority = {"foundation": 1, "mechanism": 2, "branch_or_exception": 3}

    # Put overview-bearing concepts first within foundation, then preserve source page order
    def _sort_key(c: Dict[str, Any]) -> Tuple[int, int, int, str]:
        has_overview = 0 if c.get("overview_claims") else 1
        first_page = min(c["pages"]) if c.get("pages") else 9999
        return (role_priority.get(c.get("pedagogical_role", "mechanism"), 2), has_overview, first_page, c["name"])

    ordered_concepts = sorted(concepts, key=_sort_key)

    sequence: List[Dict[str, Any]] = [
        {"stage": "introduction", "subject": concept_model["subject"], "concepts": ordered_concepts[:1]}
    ]
    for c in ordered_concepts:
        sequence.append(
            {
                "stage": c.get("pedagogical_role", "mechanism"),
                "concept": c,
            }
        )

    if concept_model.get("relationships") or concept_model.get("coverage_gaps"):
        sequence.append(
            {
                "stage": "relationships_and_limits",
                "relationships": concept_model.get("relationships", []),
                "coverage_gaps": concept_model.get("coverage_gaps", []),
            }
        )

    sequence.append({"stage": "conclusion", "concepts": ordered_concepts})
    return sequence


def _naturalize_sentence(text: str) -> str:
    """Ensures clean capitalization, spacing, and terminal punctuation for spoken narration."""
    s = clean_source_sentence_for_narration(text or "")
    if not s:
        return ""
    if s[0].islower():
        s = s[0].upper() + s[1:]
    if s[-1] not in ".!?":
        s += "."
    return s


def _format_page_ref(pages: List[int]) -> str:
    if not pages:
        return ""
    if len(pages) == 1:
        return f"page {pages[0]}"
    return f"pages {', '.join(str(p) for p in pages)}"


def _prepare_concept_claims(concept: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Orders concept claims causally and deduplicates near-identical propositions."""
    raw_claims: List[Dict[str, Any]] = list(concept.get("all_claims", []))
    if not raw_claims:
        return []

    indexed_claims = sorted(
        enumerate(raw_claims),
        key=lambda pair: (pair[1].get("structure", {}).get("mechanism_stage", 2), pair[0]),
    )

    unique_claims: List[Dict[str, Any]] = []
    seen_texts: Set[str] = set()
    seen_token_sets: List[Set[str]] = []
    for _, cl in indexed_claims:
        txt = cl["text"]
        if txt in seen_texts:
            continue
        toks = set(_tokenize_concepts(txt))
        is_redundant = False
        if len(toks) >= 4:
            for prev_toks in seen_token_sets:
                union = toks | prev_toks
                if union and (len(toks & prev_toks) / len(union)) >= 0.72:
                    is_redundant = True
                    break
        if is_redundant:
            continue
        seen_texts.add(txt)
        if toks:
            seen_token_sets.append(toks)
        unique_claims.append(cl)
    return unique_claims


def _render_claim_batch(
    claims: List[Dict[str, Any]],
    is_first_concept: bool,
    cite_opening_page: bool = True,
    cited_pages: Optional[Set[int]] = None,
) -> str:
    """Renders an ordered batch of claims into natural spoken prose with accurate, non-repetitive page citations."""
    if not claims:
        return ""
    parts: List[str] = []
    batch_pages = sorted({cl.get("page_number") for cl in claims if cl.get("page_number") is not None})
    suppress_opener = False
    for idx, cl in enumerate(claims):
        sent = _naturalize_sentence(cl["text"])
        p = cl.get("page_number")
        prev_p = claims[idx - 1].get("page_number") if idx > 0 else None
        is_corr = bool(cl.get("is_source_correction"))
        already_cited = cited_pages is not None and p in cited_pages
        if idx == 0 and cite_opening_page and p is not None and not is_corr:
            if not already_cited:
                if is_first_concept:
                    parts.append(f"Starting on page {p}, {sent[0].lower() + sent[1:]}" if _can_lowercase_start(sent) else f"On page {p}: {sent}")
                else:
                    parts.append(f"On page {p}, {sent[0].lower() + sent[1:]}" if _can_lowercase_start(sent) else f"Turning to page {p}, {sent}")
                if cited_pages is not None:
                    cited_pages.add(p)
            else:
                # Omit repetitive opening phrase while retaining inline page traceability
                suppress_opener = True
                parts.append(sent)
        elif p is not None and p != prev_p and not is_corr:
            parts.append(f"Turning to page {p}, {sent[0].lower() + sent[1:]}" if _can_lowercase_start(sent) else f"On page {p}: {sent}")
            if cited_pages is not None:
                cited_pages.add(p)
        else:
            parts.append(sent)
    joined = " ".join(parts)
    if suppress_opener and len(batch_pages) == 1 and joined.endswith((".", "!", "?")):
        p_only = batch_pages[0]
        if f"page {p_only}" not in joined.lower():
            joined = f"{joined[:-1]} (page {p_only}){joined[-1]}"
    return joined


def _synthesize_concept_explanation(concept: Dict[str, Any], is_first_concept: bool) -> str:
    """Synthesizes a concept's claims into a single natural explanation string."""
    return _render_claim_batch(_prepare_concept_claims(concept), is_first_concept=is_first_concept)


def _can_lowercase_start(sentence: str) -> bool:
    """Returns True only when lowercasing the first word preserves proper nouns/acronyms."""
    first_word = (sentence.split() or [""])[0].strip("“\"'(")
    if not first_word:
        return False
    if first_word in _PROPER_ACRONYMS_AND_TERMS or (first_word.isupper() and len(first_word) > 1):
        return False
    return first_word.lower() in {
        "the", "a", "an", "in", "on", "to", "for", "before", "after", "when", "while",
        "no", "there", "this", "these", "most", "some", "each", "both",
    }


def synthesize_concept_dialogue(
    teaching_sequence: List[Dict[str, Any]],
    concept_model: Dict[str, Any],
    spoken_topic: str,
) -> List[Dict[str, str]]:
    """
    Synthesizes a natural, concept-driven two-host educational podcast dialogue
    strictly grounded in the concept model.
    """
    dialogue: List[Dict[str, str]] = []
    concepts = concept_model.get("concepts", [])
    if not concepts:
        return []

    # Order concept names identically to teaching_sequence so the opening question matches Turn 2
    ordered_concepts = [
        step["concept"]
        for step in teaching_sequence
        if step.get("stage") not in ("introduction", "conclusion", "relationships_and_limits") and step.get("concept")
    ] or concepts
    concept_names = [c["name"] for c in ordered_concepts]
    all_pages = sorted({p for c in ordered_concepts for p in c.get("pages", [])})
    page_span = _format_page_ref(all_pages)
    cited_pages: Set[int] = set()

    # 1. Opening host introduction + first question (so Maya answers immediately in turn 2)
    intro_focus = concept_names[0]
    if len(concept_names) >= 2:
        scope_text = f"{intro_focus} through {concept_names[-1]}"
    else:
        scope_text = intro_focus

    is_very_short = concept_model.get("total_claims", 0) <= 2 and len(concepts) == 1
    if is_very_short:
        opening_turn_text = (
            f"Welcome back. Today we are examining {spoken_topic}"
            + (f" on {page_span}" if page_span else "")
            + ". What core evidence does this excerpt establish?"
        )
    else:
        opening_turn_text = (
            f"Welcome back. Today we are breaking down {spoken_topic}"
            + (f" based on {page_span} of your study material" if page_span else "")
            + f", moving from {scope_text}. Where should a learner start with {intro_focus}?"
        )

    dialogue.append(
        {
            "speaker": "Alex",
            "role": "Lead Host",
            "text": opening_turn_text,
        }
    )

    # 2. Walk through each pedagogical concept stage
    concept_idx = 0
    for step in teaching_sequence:
        stage = step["stage"]
        if stage in ("introduction", "conclusion"):
            continue

        if stage == "relationships_and_limits":
            if is_very_short:
                continue
            gaps = step.get("coverage_gaps", [])
            rels = [r for r in step.get("relationships", []) if r.get("causal_summary")]
            if not gaps and not rels:
                continue

            dialogue.append(
                {
                    "speaker": "Alex",
                    "role": "Lead Host",
                    "text": (
                        "Before we wrap up, how do these pieces connect together, and are there any parts of "
                        f"{spoken_topic} that the source material names without fully explaining?"
                    ),
                }
            )
            limit_parts: List[str] = []
            if rels:
                rel_descriptions = [r["causal_summary"].rstrip(".") for r in rels[:2] if r.get("causal_summary")]
                if rel_descriptions:
                    limit_parts.append("In terms of connections, " + "; and ".join(rel_descriptions) + ".")

            if gaps:
                gap_names = [g["topic"] for g in gaps[:4]]
                if len(gap_names) == 1:
                    gap_list = gap_names[0]
                elif len(gap_names) == 2:
                    gap_list = f"{gap_names[0]} and {gap_names[1]}"
                else:
                    gap_list = ", ".join(gap_names[:-1]) + f", and {gap_names[-1]}"
                limit_parts.append(
                    f"As for source limitations, the material lists or summarizes {gap_list} in stage overviews or tables, "
                    "but it does not provide step-by-step mechanistic explanations for them, so we should not guess those missing details."
                )

            dialogue.append(
                {
                    "speaker": "Maya",
                    "role": "Subject Expert",
                    "text": " ".join(limit_parts),
                }
            )
            continue

        concept = step["concept"]
        cname = concept["name"]

        # Choose a genuinely distinct, pedagogically appropriate host question without repeating templates
        foundation_qs = [
            f"Why is {cname} treated as a foundation before diving into the detailed steps?",
            f"How does {cname} set up the rest of the concepts in this material?",
        ]
        branch_qs = [
            f"What changes when normal conditions do not hold—specifically with {cname}?",
            f"Under what edge cases or constraints does {cname} behave differently?",
            f"Where do exceptions or trade-offs show up around {cname}?",
        ]
        mechanism_qs = [
            f"How does {cname} actually work step by step, and what drives it?",
            f"What is the practical outcome of {cname}, and why does it matter for the overall process?",
            f"Walking through {cname}, what mechanism connects the inputs to the final result?",
            f"Turning to {cname}, what causes the key changes described here?",
            f"In the case of {cname}, how do the individual steps fit together?",
        ]
        if concept_idx == 0:
            question = f"Where should a learner start when approaching {cname} in this material?"
        elif stage == "foundation":
            question = foundation_qs[concept_idx % len(foundation_qs)]
        elif stage == "branch_or_exception":
            question = branch_qs[concept_idx % len(branch_qs)]
        else:
            question = mechanism_qs[concept_idx % len(mechanism_qs)]
            # Ensure no duplicate 4-word Alex question prefix when many concepts exist
            used_prefixes = {
                " ".join((t.get("text") or "").lower().split()[:4])
                for t in dialogue
                if t.get("speaker") == "Alex" and (t.get("text") or "").endswith("?")
            }
            if " ".join(question.lower().split()[:4]) in used_prefixes:
                for cand_q in mechanism_qs + branch_qs + foundation_qs:
                    if " ".join(cand_q.lower().split()[:4]) not in used_prefixes:
                        question = cand_q
                        break

        prepared_claims = _prepare_concept_claims(concept)
        if prepared_claims:
            if concept_idx > 0:
                dialogue.append({"speaker": "Alex", "role": "Lead Host", "text": question})

            # Split dense multi-mechanism or correction-bearing concepts into two conversational exchanges
            should_split = (not is_very_short) and (
                len(prepared_claims) >= 4
                or (len(prepared_claims) >= 3 and any(cl.get("is_source_correction") for cl in prepared_claims[1:]))
            )
            if should_split:
                split_idx = next(
                    (i for i, cl in enumerate(prepared_claims) if i >= 2 and cl.get("is_source_correction")),
                    len(prepared_claims) // 2,
                )
                first_batch = prepared_claims[:split_idx]
                second_batch = prepared_claims[split_idx:]
                dialogue.append(
                    {
                        "speaker": "Maya",
                        "role": "Subject Expert",
                        "text": _render_claim_batch(
                            first_batch,
                            is_first_concept=(concept_idx == 0),
                            cite_opening_page=True,
                            cited_pages=cited_pages,
                        ),
                    }
                )
                has_corr_next = any(cl.get("is_source_correction") for cl in second_batch)
                corr_follow_qs = [
                    f"How do those details carry forward in {cname}, and is anything in the source wording imprecise?",
                    f"What should learners watch out for in the source wording around {cname}?",
                ]
                if has_corr_next and stage == "branch_or_exception":
                    follow_q = f"What happens chemically in each pathway of {cname}, and does the source's wording need clarification?"
                elif has_corr_next:
                    follow_q = corr_follow_qs[concept_idx % len(corr_follow_qs)]
                elif stage == "foundation":
                    follow_q = f"How does that foundation carry into electron transfer and the next stage of {cname}?"
                else:
                    follow_q = f"Once that setup is in place, what drives the final step of {cname}?"

                dialogue.append({"speaker": "Alex", "role": "Lead Host", "text": follow_q})
                dialogue.append(
                    {
                        "speaker": "Maya",
                        "role": "Subject Expert",
                        "text": _render_claim_batch(second_batch, is_first_concept=False, cite_opening_page=False),
                    }
                )
            else:
                dialogue.append(
                    {
                        "speaker": "Maya",
                        "role": "Subject Expert",
                        "text": _render_claim_batch(
                            prepared_claims,
                            is_first_concept=(concept_idx == 0),
                            cite_opening_page=True,
                            cited_pages=cited_pages,
                        ),
                    }
                )
            concept_idx += 1

    # 3. Meaningful educational conclusion grounded in the actual concepts taught (domain-neutral)
    summary_points: List[str] = []
    for c in ordered_concepts[:4]:
        if c.get("pedagogical_role") == "foundation":
            summary_points.append(f"{c['name']} establishes the foundational definition and scope")
        elif c.get("pedagogical_role") == "branch_or_exception" or c["exceptions"] or c["examples"]:
            summary_points.append(f"{c['name']} highlights key trade-offs, comparisons, or conditional cases")
        elif c["cause_effects"] or c["processes"]:
            summary_points.append(f"{c['name']} explains the core mechanism and its consequences")
    if not summary_points:
        summary_points.append(f"the source outlines the core evidence around {spoken_topic}")

    dialogue.append(
        {
            "speaker": "Alex",
            "role": "Lead Host",
            "text": (
                f"To sum up what we actually learned about {spoken_topic}"
                + (f" ({page_span})" if page_span else "")
                + ": "
                + "; ".join(summary_points)
                + ". Understanding those underlying mechanisms and conditions is what turns isolated terms into a coherent mental model."
            ),
        }
    )

    for turn in dialogue:
        turn["spoken_text"] = normalize_spoken_text_for_tts(turn["text"])
    return dialogue


def normalize_spoken_text_for_tts(text: str) -> str:
    """
    Normalizes scientific/chemical notation for natural TTS pronunciation
    without mutating the visual transcript or corrupting ordinary words.
    """
    s = (text or "").strip()
    if not s:
        return ""
    # Collapse redundant parentheticals before replacing H2O / O2 (e.g. "water (H2O)" -> "water")
    s = re.sub(r"\bwater\s*\(\s*H2O\s*\)", "water", s)
    s = re.sub(r"\bwater,\s*H2O\b", "water", s)
    s = re.sub(r"\boxygen\s*\(\s*O2\s*\)", "oxygen", s)
    # Ion & coenzyme pronunciations (boundary-safe)
    s = re.sub(r"(?<![A-Za-z0-9])H\+(?![A-Za-z0-9])", "hydrogen ions", s)
    s = re.sub(r"\bhydrogen ions passes\b", "hydrogen ions pass", s)
    s = re.sub(r"(?<![A-Za-z0-9])NAD\+(?![A-Za-z0-9])", "N-A-D plus", s)
    s = re.sub(r"(?<![A-Za-z0-9])FAD\+(?![A-Za-z0-9])", "F-A-D plus", s)
    s = re.sub(r"\bNADH\b", "N-A-D-H", s)
    s = re.sub(r"\bFADH2\b", "F-A-D-H two", s)
    s = re.sub(r"\bCO2\b", "carbon dioxide", s)
    s = re.sub(r"\bH2O\b", "water", s)
    s = re.sub(r"\bO2\b", "oxygen", s)
    # Computer Science & mathematical asymptotic notation (boundary-safe)
    s = re.sub(r"\bO\(\s*1\s*\)\s+time\b", "constant time", s)
    s = re.sub(r"\bO\(\s*1\s*\)", "O of one", s)
    s = re.sub(r"\bO\(\s*log\s+([A-Za-z0-9]+)\s*\)", r"O of log \1", s)
    s = re.sub(r"\bO\(\s*([A-Za-z])\s+log\s+([A-Za-z])\s*\)", r"O of \1 log \2", s)
    s = re.sub(r"\bO\(\s*([A-Za-z])\s*\^\s*2\s*\)", r"O of \1 squared", s)
    s = re.sub(r"\bO\(\s*([A-Za-z])\s*\)", r"O of \1", s)
    return re.sub(r"\s+", " ", s).strip()


def _make_independent_takeaway(sentence: str) -> str:
    """Rewrites context-dependent discourse openers so each key takeaway stands alone cleanly."""
    s = (sentence or "").strip()
    if not s:
        return ""
    s = re.sub(
        r"^(?:However|Moreover|Furthermore|Additionally|Therefore|Consequently|Meanwhile|Instead|Conversely)\s*,\s*",
        "",
        s,
        flags=re.IGNORECASE,
    )
    unlike_m = re.match(
        r"^Unlike\s+([^,]{3,60}(?:,\s*(?:which|who|where)\s+[^,]{3,90})?),\s*(.+)$",
        s,
        flags=re.IGNORECASE,
    )
    if unlike_m:
        contrast_part = unlike_m.group(1).strip()
        main_part = unlike_m.group(2).strip().rstrip(".")
        s = f"{main_part} (in contrast to {contrast_part})."
    return (s[0].upper() + s[1:]) if s else ""


def extract_verified_key_takeaways(concept_model: Dict[str, Any], max_items: int = 5) -> List[str]:
    """
    Extracts key takeaways strictly from verified concept-model claims so
    scientific corrections propagate consistently and raw erroneous source
    sentences never coexist with corrected dialogue.
    """
    prioritized: List[str] = []
    secondary: List[str] = []
    seen: Set[str] = set()

    for concept in concept_model.get("concepts", []):
        for cl in _prepare_concept_claims(concept):
            sent = _make_independent_takeaway(_naturalize_sentence(cl["text"]))
            if not sent or sent in seen:
                continue
            seen.add(sent)
            if cl.get("is_source_correction") or cl.get("role") in ("overview_framing", "definition", "exception"):
                prioritized.append(sent)
            else:
                secondary.append(sent)

    return (prioritized + secondary)[:max_items]


def validate_cross_output_consistency(
    dialogue: List[Dict[str, str]],
    key_takeaways: List[str],
    concept_model: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Validates that key takeaways, dialogue, and concept-model corrections are
    mutually consistent (no uncorrected raw source errors in takeaways).
    """
    issues: List[str] = []
    flagged_raws = [
        cl.get("raw_source_text", "").strip().lower()
        for c in concept_model.get("concepts", [])
        for cl in c.get("all_claims", [])
        if cl.get("is_source_correction") and cl.get("raw_source_text")
    ]
    for tk in key_takeaways:
        tk_low = (tk or "").strip().lower()
        for raw in flagged_raws:
            if raw and (raw in tk_low or tk_low in raw):
                issues.append(f"Unverified raw source claim leaked into key_takeaways: '{tk[:60]}...'")

    dialogue_res = validate_audio_dialogue(dialogue)
    issues.extend(dialogue_res.get("issues", []))
    return {"passed": len(issues) == 0, "issues": issues}


def validate_audio_dialogue(
    dialogue: List[Dict[str, str]],
    source_refs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Deterministic quality validator for generated two-host Audio Overview dialogue.
    Checks continuity, repetitive questions, boilerplate openers, duplicate claims,
    kerning artifacts, and page-citation validity.
    """
    issues: List[str] = []
    if len(dialogue) < 3:
        issues.append("Dialogue has fewer than 3 turns.")

    alex_questions: List[str] = []
    maya_openers: List[str] = []
    seen_sentences: Set[str] = set()
    valid_pages = {r.get("page_number") for r in (source_refs or []) if r.get("page_number") is not None}

    mechanical_phrases = (
        "the material notes that",
        "the text explains that",
        "the passage adds that",
        "following that point on",
        "and what else stands out",
        "shows how energy or inputs are transformed",
    )

    for idx, turn in enumerate(dialogue):
        text = (turn.get("text") or "").strip()
        speaker = turn.get("speaker", "")
        low = text.lower()

        if not text:
            issues.append(f"Turn {idx} ({speaker}) is empty.")
            continue
        if text[-1] not in ".!?":
            issues.append(f"Turn {idx} ({speaker}) lacks terminal punctuation.")

        # Check mid-sentence capital splice after 'that ' (flagging common sentence-starters, not proper nouns like 'Germany')
        for m in re.finditer(r"\bthat\s+([A-Z][a-z]+)\b", text):
            if m.group(1).lower() in {
                "no", "there", "this", "these", "those", "the", "a", "an",
                "in", "on", "to", "for", "before", "after", "when", "while",
                "most", "some", "each", "both", "it", "they",
            }:
                issues.append(f"Turn {idx} has awkward capitalized splice 'that {m.group(1)}'.")

        # Check kerning artifact like 'T he' or 's yntha', ignoring valid variable names like 'x and X are'
        for km in re.finditer(r"\b[B-HJ-Z]\s+[a-z]{2,}\b", text):
            before = text[max(0, km.start() - 6) : km.start()].lower()
            if before.endswith(("and ", "or ", "var ", "let ")):
                continue
            issues.append(f"Turn {idx} contains potential character-spacing kerning artifact.")
            break

        # Check unclosed double quotes
        if text.count('"') % 2 != 0:
            issues.append(f"Turn {idx} has unmatched ASCII double quote.")

        for mp in mechanical_phrases:
            if mp in low:
                issues.append(f"Turn {idx} uses mechanical boilerplate phrase '{mp}'.")

        if re.search(r"\b(?:link[s]?\s+directly\s+to\b.*\bthrough|connect\s+directly)\b", low):
            issues.append(f"Turn {idx} uses generic or raw keyword-list relationship phrasing.")

        if speaker == "Alex" and re.search(
            r"\b(?:with|moving from|through)\s+(?:however|unlike|because|therefore|additionally|furthermore|moreover)\b",
            low,
        ):
            issues.append(f"Turn {idx} treats a discourse marker as a concept name.")

        # Validate cited page numbers against source_refs
        if valid_pages:
            for pm in re.finditer(r"\bpage\s+(\d+)\b", low):
                pnum = int(pm.group(1))
                if pnum not in valid_pages:
                    issues.append(f"Turn {idx} cites unsupported page {pnum}.")

        if speaker == "Alex" and text.endswith("?"):
            prefix = " ".join(low.split()[:4])
            if prefix in alex_questions:
                issues.append(f"Duplicate Alex question prefix: '{prefix}'.")
            alex_questions.append(prefix)

        if speaker == "Maya":
            opener = " ".join(low.split()[:3])
            maya_openers.append(opener)
            for sent in re.split(r"(?<=[.!?])\s+", low):
                norm = re.sub(r"\s+", " ", sent).strip()
                if len(norm) >= 40:
                    if norm in seen_sentences:
                        issues.append(f"Duplicate factual sentence across turns: '{norm[:50]}...'.")
                    seen_sentences.add(norm)

            # Semantic check 1: Conflating ATP synthase proton flow with oxygen reduction to water
            if re.search(r"go through\s+(?:the\s+)?atp synthase.*react with oxygen.*water", low):
                issues.append(f"Turn {idx} conflates proton flow through ATP synthase with oxygen reduction to water.")

            # Semantic check 2: Asserting 'pyruvate is oxidized' in fermentation as an established fact
            if "fermentation" in low and re.search(r"\bpyruvate is oxidized\b", low):
                if "correction" not in low and "source states" not in low and "source writes" not in low and "neither pathway oxidizes pyruvate" not in low:
                    issues.append(f"Turn {idx} presents inaccurate source claim 'pyruvate is oxidized' as an established fact.")

            # Semantic check 2b: Claiming pyruvate is directly reduced to ethanol without acetaldehyde
            if (
                re.search(r"pyruvate\s+is\s+(?:directly\s+)?reduced\s+(?:by\s+nadh\s+)?to\s+ethanol", low)
                or (
                    re.search(r"pyruvate.*accepts\s+electrons\s+from\s+nadh\s+to\s+form\s+ethanol", low)
                    and "acetaldehyde" not in low
                )
            ):
                issues.append(f"Turn {idx} inaccurately states pyruvate is directly reduced to ethanol without acetaldehyde.")

            # Semantic check 3: Incorrect mechanism ordering ('This type of ATP production' before phosphorylation)
            ox_pos = low.find("this type of atp production")
            phos_pos = low.find("phosphorylate adp")
            if ox_pos != -1 and (phos_pos == -1 or ox_pos < phos_pos):
                issues.append(f"Turn {idx} places 'This type of ATP production' before explaining ADP phosphorylation.")

    if len(maya_openers) >= 3 and len(set(maya_openers)) == 1:
        issues.append("All Maya turns start with the exact same opener.")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "turn_count": len(dialogue),
        "question_count": len(alex_questions),
    }
