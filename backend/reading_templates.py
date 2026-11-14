"""Topic-aware educational reading material & diagram builders for BRAINOVA."""

from typing import Any, Dict, List


def normalize_diagrams(
    raw_diagrams: Any,
    topic_title: str,
    subtopics: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """Validate and normalize diagram payloads into consistent node-flow structures."""
    valid: List[Dict[str, Any]] = []
    if isinstance(raw_diagrams, list):
        for idx, diag in enumerate(raw_diagrams):
            if not isinstance(diag, dict):
                continue
            nodes_in = diag.get("nodes") or diag.get("steps") or diag.get("stages") or []
            if not isinstance(nodes_in, list) or len(nodes_in) < 2:
                continue
            norm_nodes: List[Dict[str, str]] = []
            for n_idx, nd in enumerate(nodes_in[:6]):
                if isinstance(nd, dict):
                    label = str(nd.get("label") or nd.get("title") or nd.get("name") or f"Step {n_idx + 1}").strip()
                    sublabel = str(nd.get("sublabel") or nd.get("detail") or nd.get("description") or "").strip()
                    role = str(nd.get("role") or nd.get("tag") or "").strip()
                    step = str(nd.get("step") or f"{n_idx + 1:02d}").strip()
                    norm_nodes.append(
                        {
                            "id": str(nd.get("id") or f"n{n_idx + 1}"),
                            "step": step,
                            "label": label,
                            "sublabel": sublabel,
                            "role": role,
                        }
                    )
                elif isinstance(nd, str) and nd.strip():
                    norm_nodes.append(
                        {
                            "id": f"n{n_idx + 1}",
                            "step": f"{n_idx + 1:02d}",
                            "label": nd.strip(),
                            "sublabel": "",
                            "role": "",
                        }
                    )
            if len(norm_nodes) >= 2:
                valid.append(
                    {
                        "id": str(diag.get("id") or f"diag-{idx + 1}"),
                        "title": str(diag.get("title") or f"{topic_title} — Visual Concept Flow"),
                        "type": str(diag.get("type") or "flow").lower(),
                        "caption": str(diag.get("caption") or diag.get("explanation") or ""),
                        "nodes": norm_nodes,
                    }
                )
    if valid:
        return valid

    # Fallback: build topic-specific diagram from matched domain or subtopics
    matched = match_domain_template(topic_title, "", subtopics or [], "Intermediate", "Developer")
    if matched and matched.get("diagrams"):
        return matched["diagrams"]

    subs = [s.strip() for s in (subtopics or []) if str(s).strip()]
    if len(subs) >= 2:
        nodes = [
            {
                "id": f"s{i + 1}",
                "step": f"{i + 1:02d}",
                "label": s[:40],
                "sublabel": f"Core stage {i + 1} of {topic_title}",
                "role": "Concept" if i == 0 else ("Apply" if i < len(subs) - 1 else "Verify"),
            }
            for i, s in enumerate(subs[:5])
        ]
        return [
            {
                "id": "diag-subtopic-flow",
                "title": f"{topic_title} — Conceptual Progression",
                "type": "flow",
                "caption": f"How the key concepts of {topic_title} build sequentially from foundations to application.",
                "nodes": nodes,
            }
        ]
    return []


def match_domain_template(
    topic_title: str,
    topic_description: str,
    subtopics: List[str],
    difficulty: str,
    target_role: str,
) -> Dict[str, Any] | None:
    """Return high-signal domain-specific reading content & diagrams for common CS/engineering topics."""
    text = f"{topic_title} {topic_description} {' '.join(subtopics)}".lower()

    if any(k in text for k in ("event loop", "microtask", "callback queue", "async javascript", "promises & async")):
        return {
            "overview": (
                f"JavaScript executes code on a single main thread, yet handles network requests, timers, and UI events without freezing. "
                f"Understanding the **Event Loop**—and how the **Call Stack**, **Web APIs**, **Microtask Queue**, and **Callback (Task) Queue** "
                f"coordinate—is essential for writing bug-free asynchronous code as a {target_role}."
            ),
            "sections": [
                {
                    "id": "sec-1",
                    "heading": "1. Call Stack & Synchronous Execution",
                    "level_tag": "Foundational",
                    "content": (
                        "Every synchronous function call pushes a stack frame onto the **Call Stack** (LIFO: Last-In, First-Out). "
                        "While a synchronous function is running, the JavaScript engine cannot paint the screen or run other callbacks.\n\n"
                        "Once a function returns, its frame is popped. Only when the Call Stack becomes completely empty can the Event Loop "
                        "pick up pending asynchronous callbacks."
                    ),
                    "key_takeaway": "Long synchronous loops block the Call Stack and freeze UI rendering.",
                },
                {
                    "id": "sec-2",
                    "heading": "2. Web APIs, Microtask Queue & Callback Queue",
                    "level_tag": "Core Mechanics",
                    "content": (
                        "Asynchronous operations like `fetch()`, `setTimeout()`, and DOM listeners are handed off to **Browser Web APIs** "
                        "(or libuv in Node.js). When they complete, their callbacks are placed into one of two queues:\n\n"
                        "- **Microtask Queue (High Priority):** `Promise.then/catch/finally`, `queueMicrotask()`, `await` continuations.\n"
                        "- **Callback / Macrotask Queue (Normal Priority):** `setTimeout`, `setInterval`, DOM click/input events.\n\n"
                        "After each synchronous turn finishes and the Call Stack is empty, the Event Loop drains **every** item in the Microtask Queue "
                        "before taking **one** task from the Callback Queue."
                    ),
                    "key_takeaway": "All microtasks run before the next macrotask (e.g., Promise callbacks always beat setTimeout(..., 0)).",
                },
                {
                    "id": "sec-3",
                    "heading": "3. Real-World Execution Order & Starvation",
                    "level_tag": "Production",
                    "content": (
                        "Because microtasks drain completely before rendering or macrotasks, recursively scheduling `Promise.resolve().then(...)` "
                        "starves the browser's UI thread just like an infinite `while` loop.\n\n"
                        "Use `await` cleanly for sequential async steps, `Promise.all()` for independent parallel I/O, and `setTimeout(..., 0)` "
                        "or `requestAnimationFrame` when you intentionally want to yield back to the browser renderer."
                    ),
                    "key_takeaway": "Never chain unbounded recursive microtasks; yield to macrotasks for heavy background work.",
                },
            ],
            "diagrams": [
                {
                    "id": "diag-event-loop",
                    "title": "JavaScript Event Loop Execution Pipeline",
                    "type": "flow",
                    "caption": (
                        "Synchronous frames execute on the Call Stack. Async work delegates to Web APIs, which enqueue resolved Promises into "
                        "the high-priority Microtask Queue and timers/events into the Callback Queue. The Event Loop drains all Microtasks before "
                        "moving the next Callback onto an empty Call Stack."
                    ),
                    "nodes": [
                        {"id": "cs", "step": "01", "label": "Call Stack", "sublabel": "LIFO synchronous execution frames", "role": "Main Thread"},
                        {"id": "wa", "step": "02", "label": "Web APIs", "sublabel": "Timers, fetch(), DOM events run off-stack", "role": "Host Runtime"},
                        {"id": "mq", "step": "03", "label": "Microtask Queue", "sublabel": "Promise.then & await continuations (drained first)", "role": "High Priority"},
                        {"id": "cq", "step": "04", "label": "Callback Queue", "sublabel": "setTimeout & UI event callbacks (1 per tick)", "role": "Macrotask"},
                        {"id": "el", "step": "05", "label": "Event Loop", "sublabel": "Moves queued work when Call Stack is empty", "role": "Coordinator"},
                    ],
                }
            ],
            "key_definitions": [
                {"term": "Call Stack", "definition": "LIFO data structure tracking currently executing synchronous functions.", "context": "Single-threaded execution"},
                {"term": "Microtask Queue", "definition": "High-priority queue for Promise reactions and queueMicrotask callbacks, drained completely after each stack turn.", "context": "Runs before macrotasks"},
                {"term": "Callback (Macrotask) Queue", "definition": "Queue holding timer callbacks (setTimeout) and I/O or DOM event handlers.", "context": "One task executed per Event Loop tick"},
                {"term": "Event Loop", "definition": "Continuous coordinator that checks if the Call Stack is empty and schedules microtasks then macrotasks.", "context": "Enables non-blocking concurrency"},
            ],
            "code_examples": [
                {
                    "title": "Predicting Exact Execution Order (Stack vs Microtask vs Macrotask)",
                    "language": "javascript",
                    "code": (
                        "console.log('1. Sync start');\n\n"
                        "setTimeout(() => console.log('4. Macrotask (setTimeout)'), 0);\n\n"
                        "Promise.resolve()\n"
                        "  .then(() => console.log('3. Microtask (Promise)'));\n\n"
                        "console.log('2. Sync end');\n"
                        "// Output order: 1 -> 2 -> 3 -> 4"
                    ),
                    "explanation": "Synchronous logs (1, 2) run immediately on the Call Stack. Next, the Event Loop drains the Microtask Queue (3) before dequeuing the setTimeout macrotask (4).",
                }
            ],
            "comparison_tables": [
                {
                    "title": "Microtask Queue vs Callback (Macrotask) Queue",
                    "headers": ["Feature", "Microtask Queue", "Callback (Macrotask) Queue"],
                    "rows": [
                        ["Sources", "Promise.then, await, queueMicrotask", "setTimeout, setInterval, DOM events, I/O"],
                        ["Priority", "Highest — drained completely after each turn", "Standard — 1 task per Event Loop tick"],
                        ["Rendering Impact", "Can starve UI paint if endlessly queued", "Browser can paint between ticks"],
                    ],
                }
            ],
            "common_mistakes": [
                {
                    "mistake": "Assuming setTimeout(fn, 0) runs immediately after the current line",
                    "why_it_happens": "0ms only means minimum delay before entering the Callback Queue; synchronous code and all Microtasks still run first.",
                    "fix": "Use Promise.resolve().then() or await for microtask ordering, and never rely on setTimeout(..., 0) to beat Promises.",
                },
                {
                    "mistake": "Awaiting independent requests sequentially inside a loop",
                    "why_it_happens": "Writing `await fetch(...)` one-by-one blocks each iteration until the previous network round-trip completes.",
                    "fix": "Launch independent async operations concurrently with `await Promise.all(urls.map(fetch))`.",
                },
            ],
            "interview_questions": [
                {
                    "question": "Why does a resolved Promise callback execute before setTimeout(..., 0)?",
                    "model_answer": "Promise callbacks enter the Microtask Queue, whereas setTimeout enters the Callback (Macrotask) Queue. After the Call Stack clears, the Event Loop drains the entire Microtask Queue before dequeuing a single macrotask.",
                }
            ],
            "takeaways": [
                "JavaScript has one Call Stack; long synchronous code blocks everything.",
                "Microtasks (Promises, await) always drain before the next macrotask (setTimeout).",
                "Use Promise.all() for concurrent I/O and avoid recursive microtask starvation.",
            ],
            "summary": "The Event Loop coordinates the Call Stack, Web APIs, Microtask Queue, and Callback Queue to keep single-threaded JavaScript responsive under asynchronous I/O.",
        }

    if any(k in text for k in ("normalization", "1nf", "2nf", "3nf", "bcnf", "normal form")):
        return {
            "overview": (
                f"**Database Normalization** systematically organizes relational tables to eliminate redundant data, prevent insertion/update/deletion "
                f"anomalies, and enforce clear **Primary Key (PK)** and **Foreign Key (FK)** relationships."
            ),
            "sections": [
                {
                    "id": "sec-1",
                    "heading": "1. Why Unnormalized Tables Fail (Anomalies)",
                    "level_tag": "Foundational",
                    "content": (
                        "Storing repeating groups or mixed entities (e.g., Student + Course + Instructor all in one wide table) causes three classic bugs:\n\n"
                        "- **Insertion Anomaly:** Cannot add a new course until at least one student enrolls.\n"
                        "- **Update Anomaly:** Changing an instructor's email requires updating dozens of duplicate rows.\n"
                        "- **Deletion Anomaly:** Deleting the last student in a course accidentally erases the course record."
                    ),
                    "key_takeaway": "Redundant attributes across rows create update, insert, and delete anomalies.",
                },
                {
                    "id": "sec-2",
                    "heading": "2. First, Second & Third Normal Forms (1NF -> 2NF -> 3NF)",
                    "level_tag": "Step-by-Step",
                    "content": (
                        "- **1NF (Atomic Values):** Every column holds a single atomic value (no comma-separated lists) and each row has a unique Primary Key.\n"
                        "- **2NF (No Partial Dependencies):** Every non-key column must depend on the *entire* composite Primary Key, not just part of it.\n"
                        "- **3NF (No Transitive Dependencies):** Non-key columns must depend *only* on the Primary Key—never on another non-key column (e.g., move `dept_name` out if it depends on `dept_id`)."
                    ),
                    "key_takeaway": "Each normal form narrows every table to a single entity linked via Foreign Keys.",
                },
            ],
            "diagrams": [
                {
                    "id": "diag-normalization",
                    "title": "Progressive Database Normalization (UNF -> 1NF -> 2NF -> 3NF)",
                    "type": "process",
                    "caption": (
                        "An unnormalized Orders+Products table is split step-by-step: 1NF enforces atomic columns, 2NF separates composite-key "
                        "dependencies into Orders & OrderItems, and 3NF extracts transitive attributes (like CustomerCity) into a Customers table."
                    ),
                    "nodes": [
                        {"id": "unf", "step": "UNF", "label": "Unnormalized Table", "sublabel": "Repeating item lists in one row", "role": "Anomalies"},
                        {"id": "1nf", "step": "1NF", "label": "Atomic Columns + PK", "sublabel": "One value per cell; unique row key", "role": "Atomicity"},
                        {"id": "2nf", "step": "2NF", "label": "Split Partial Deps", "sublabel": "Orders(order_id PK) + Items(item_id PK, order_id FK)", "role": "Full Key Dep"},
                        {"id": "3nf", "step": "3NF", "label": "Remove Transitive Deps", "sublabel": "Customers(customer_id PK) linked by FK", "role": "Clean Schema"},
                    ],
                }
            ],
            "key_definitions": [
                {"term": "Primary Key (PK)", "definition": "Column(s) that uniquely identify every row in a table (non-null and unique).", "context": "Entity integrity"},
                {"term": "Foreign Key (FK)", "definition": "Column referencing the Primary Key of another table to enforce relational integrity.", "context": "Referential integrity"},
                {"term": "Transitive Dependency", "definition": "When non-key attribute C depends on non-key B, which depends on key A (A -> B -> C).", "context": "Eliminated in 3NF"},
            ],
            "code_examples": [
                {
                    "title": "3NF Relational Schema with Primary & Foreign Keys (SQL)",
                    "language": "sql",
                    "code": (
                        "CREATE TABLE customers (\n"
                        "  customer_id INTEGER PRIMARY KEY,\n"
                        "  full_name   TEXT NOT NULL,\n"
                        "  city        TEXT NOT NULL\n"
                        ");\n\n"
                        "CREATE TABLE orders (\n"
                        "  order_id    INTEGER PRIMARY KEY,\n"
                        "  customer_id INTEGER NOT NULL REFERENCES customers(customer_id),\n"
                        "  created_at  TEXT NOT NULL\n"
                        ");"
                    ),
                    "explanation": "Customer attributes live once in `customers`. `orders` references `customer_id` via a Foreign Key, eliminating update anomalies.",
                }
            ],
            "comparison_tables": [
                {
                    "title": "Normal Forms Summary",
                    "headers": ["Form", "Rule Enforced", "Problem Solved"],
                    "rows": [
                        ["1NF", "Atomic values, no repeating groups", "Multi-valued cells & missing keys"],
                        ["2NF", "No partial dependency on composite PK", "Duplicated parent attributes in join tables"],
                        ["3NF", "No transitive dependency (A -> B -> C)", "Update anomalies on indirect attributes"],
                    ],
                }
            ],
            "common_mistakes": [
                {
                    "mistake": "Storing comma-separated IDs (e.g., '12,45,78') in a single column",
                    "why_it_happens": "Avoids creating a junction table during quick prototyping, but violates 1NF.",
                    "fix": "Create a normalized join table with `(parent_id, child_id)` Foreign Keys and a composite/unique constraint.",
                },
                {
                    "mistake": "Over-normalizing read-heavy analytics tables without considering joins",
                    "why_it_happens": "Applying strict 3NF/BCNF blindly to reporting warehouses where denormalized star schemas are faster.",
                    "fix": "Use 3NF as the default for OLTP transactional databases; selectively denormalize or index for proven read bottlenecks.",
                },
            ],
            "interview_questions": [
                {
                    "question": "What is the difference between 2NF and 3NF?",
                    "model_answer": "2NF removes partial dependencies where a non-key column depends on only part of a composite Primary Key. 3NF removes transitive dependencies where a non-key column depends on another non-key column.",
                }
            ],
            "takeaways": [
                "1NF = atomic values; 2NF = full key dependency; 3NF = no transitive dependencies.",
                "Connect normalized tables cleanly using Primary Keys and Foreign Keys.",
            ],
            "summary": "Normalization eliminates anomalies and protects data integrity by decomposing tables into single-purpose entities linked by Foreign Keys.",
        }

    return None


def build_topic_reading_fallback(
    topic_title: str,
    topic_description: str,
    subtopics: List[str],
    prerequisites: List[str],
    difficulty: str,
    target_role: str,
) -> Dict[str, Any]:
    """Build structured, topic-aware educational reading material when external LLM is unavailable."""
    matched = match_domain_template(topic_title, topic_description, subtopics, difficulty, target_role)
    if matched:
        return matched

    subs = [s.strip() for s in subtopics if str(s).strip()] or [
        f"Core Principles of {topic_title}",
        f"Practical Implementation in {topic_title}",
        f"Edge Cases & Reliability in {topic_title}",
    ]
    desc = topic_description.strip() or f"Essential concepts, architecture, and practical application of {topic_title} for {target_role}."

    overview = (
        f"**{topic_title}** ({difficulty} level) is a core skill for {target_role}. {desc} "
        f"Below you will learn its core building blocks ({', '.join(subs[:3])}), how components interact visually, "
        f"practical examples, and common pitfalls to avoid."
    )

    sections = []
    levels = ["Foundational", "Core Mechanics", "Applied Practice", "Production"]
    for idx, sub in enumerate(subs[:4]):
        lvl = levels[min(idx, len(levels) - 1)]
        sections.append(
            {
                "id": f"sec-{idx + 1}",
                "heading": f"{idx + 1}. {sub}",
                "level_tag": lvl,
                "content": (
                    f"**{sub}** focuses on how {topic_title} structures data, responsibilities, and execution flow at the {lvl.lower()} stage. "
                    f"Start by identifying the inputs, constraints, and expected outputs for {sub}.\n\n"
                    f"In real projects, engineers apply **{sub}** by keeping responsibilities focused, validating assumptions early, "
                    f"and verifying behavior with concrete examples before scaling."
                ),
                "key_takeaway": f"Master the core rules and boundaries of {sub} before combining it with later stages.",
            }
        )

    diagrams = normalize_diagrams(None, topic_title, subs)

    key_definitions = [
        {
            "term": sub,
            "definition": f"A foundational pillar of {topic_title} responsible for handling {sub.lower()} cleanly and predictably.",
            "context": f"Core {difficulty} concept in {topic_title}",
        }
        for sub in subs[:3]
    ]

    code_examples = [
        {
            "title": f"Worked Example — Applying {topic_title}",
            "language": "text",
            "code": (
                f"Topic: {topic_title} ({difficulty})\n"
                + "\n".join(f"Step {i + 1}: {s}" for i, s in enumerate(subs[:4]))
            ),
            "explanation": f"Walk through each stage in order when designing or debugging {topic_title} solutions.",
        }
    ]

    comparison_tables = [
        {
            "title": f"Key Focus Areas in {topic_title}",
            "headers": ["Focus Area", "Primary Goal", "When to Prioritize"],
            "rows": [
                [subs[0], "Build accurate mental model & clean structure", "At project design & setup"],
                [subs[min(1, len(subs) - 1)], "Correct behavior & edge-case handling", "During implementation & review"],
            ],
        }
    ]

    common_mistakes = [
        {
            "mistake": f"Skipping fundamentals of {subs[0]} before jumping into advanced {topic_title} patterns",
            "why_it_happens": "Rushing directly to complex implementations without understanding the underlying rules causes fragile code.",
            "fix": f"Verify a minimal working example of {subs[0]} first, then layer complexity incrementally.",
        },
        {
            "mistake": f"Ignoring edge cases and error states in {topic_title}",
            "why_it_happens": "Testing only happy-path inputs leaves unexpected failures uncovered.",
            "fix": "Explicitly test empty inputs, invalid formats, and boundary conditions.",
        },
    ]

    interview_questions = [
        {
            "question": f"How do the core parts of {topic_title} ({', '.join(subs[:2])}) work together?",
            "model_answer": f"{subs[0]} establishes the core structure and contracts, while {subs[min(1, len(subs) - 1)]} applies those rules reliably to handle real workloads and edge cases.",
        }
    ]

    return {
        "overview": overview,
        "sections": sections,
        "diagrams": diagrams,
        "key_definitions": key_definitions,
        "code_examples": code_examples,
        "comparison_tables": comparison_tables,
        "common_mistakes": common_mistakes,
        "interview_questions": interview_questions,
        "takeaways": [f"Understand {s}" for s in subs[:3]],
        "summary": f"Understanding {topic_title} means connecting {', '.join(subs[:3])} with practical examples and disciplined edge-case checks.",
    }

