"""
StudyOS — Comprehensive Secondary Role Curricula (11 Independent Roles)
Each role has its own category hierarchy, topic IDs, DAG prerequisites,
learning objectives, and concrete subtopics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _build_categories(
    prefix: str,
    specs: List[Tuple[str, str, str, List[Tuple[str, str, str, int, List[str], str, List[str]]]]],
) -> List[Dict[str, Any]]:
    cats: List[Dict[str, Any]] = []
    for cid, ctitle, cdesc, tlist in specs:
        topics = [
            {
                "topic_id": f"{prefix}_{tid}",
                "title": title,
                "difficulty": diff,
                "estimated_hours": hrs,
                "prerequisites": [f"{prefix}_{p}" for p in pre],
                "learning_objective": obj,
                "subtopics": subs,
            }
            for (tid, title, diff, hrs, pre, obj, subs) in tlist
        ]
        cats.append(
            {
                "category_id": f"{prefix}_{cid}",
                "title": ctitle,
                "description": cdesc,
                "topics": topics,
            }
        )
    return cats


FRONTEND_CATEGORIES = _build_categories("fe", [
    ("web", "1. Internet & Web Fundamentals", "DNS, HTTP/HTTPS, and how browsers fetch and render documents.", [
        ("http", "Understand HTTP/HTTPS, DNS Resolution & Browser Request Lifecycle", "Beginner", 4, [], "Trace how URLs resolve over DNS/TLS into rendered HTML.", ["DNS & TLS handshake", "HTTP/1.1 vs HTTP/2", "Status codes & caching headers"]),
    ]),
    ("html", "2. HTML & Semantic Markup", "Accessible document outlines, landmarks, and native forms.", [
        ("sem", "Author Semantic HTML5 Landmarks & Accessible Forms", "Beginner", 5, ["http"], "Structure pages with semantic elements and native validation.", ["header/nav/main/article/footer", "Labeling & fieldsets", "Constraint validation & srcset"]),
    ]),
    ("css", "3. CSS & Layout Systems", "Cascade, tokens, Flexbox, CSS Grid, and transitions.", [
        ("box", "Master Cascade, Specificity, Box Model & Design Tokens", "Beginner", 5, ["sem"], "Control styling predictably using CSS custom properties.", ["Specificity & inheritance", "rem/em/vw units", "CSS variables (--tokens)"]),
        ("grid", "Build Two-Dimensional Layouts with Flexbox & CSS Grid", "Beginner", 6, ["box"], "Construct complex responsive grids without overflow.", ["Flexbox alignment & wrapping", "Grid areas & minmax()", "Subtle CSS transitions"]),
    ]),
    ("resp_a11y", "4. Responsive Design & Accessibility", "Mobile-first ergonomics and WCAG AA compliance.", [
        ("resp", "Implement Mobile-First Breakpoints & Fluid Typography", "Beginner", 4, ["grid"], "Ensure zero horizontal overflow across mobile, tablet, and desktop.", ["Media & container queries", "clamp() fluid scaling", "Touch target sizing (44px+)"]),
        ("a11y", "Enforce WCAG AA Contrast, Keyboard Navigation & ARIA", "Intermediate", 5, ["sem", "grid"], "Make interactive widgets usable via keyboard and screen readers.", ["Focus rings & modal focus traps", "aria-expanded & aria-live", "Color contrast verification"]),
    ]),
    ("js", "5. JavaScript & Asynchronous Execution", "Closures, prototypes, event loop, and Fetch API.", [
        ("core", "Master Lexical Scope, Closures, Prototypes & ES Modules", "Intermediate", 8, ["sem"], "Predict variable binding and module evaluation order.", ["Closures & lexical environments", "Prototypal inheritance", "ESM tree-shaking"]),
        ("async", "Control Event Loop, Promises, Async/Await & AbortController", "Intermediate", 8, ["core"], "Cancel stale requests and handle concurrent API calls safely.", ["Microtasks vs macrotasks", "Promise.allSettled & race", "AbortController cancellation"]),
    ]),
    ("ts", "6. TypeScript", "Static type safety for UI components and API contracts.", [
        ("types", "Apply TypeScript Interfaces, Unions, Narrowing & Generics", "Intermediate", 8, ["core"], "Eliminate runtime null/type errors at compile time.", ["Discriminated unions", "Generics & keyof", "Strict null checks"]),
    ]),
    ("dom", "7. DOM & Browser APIs", "Critical rendering path, storage, and web workers.", [
        ("dom", "Optimize Critical Rendering Path, DOM Events & Storage APIs", "Intermediate", 6, ["async"], "Avoid layout thrashing and choose safe client storage.", ["Event delegation", "Reflow vs repaint vs composite", "localStorage, sessionStorage & IndexedDB"]),
    ]),
    ("react", "8. React Architecture & Hooks", "Component composition, reconciliation, and custom hooks.", [
        ("comp", "Build Pure React Components, Props, State & Error Boundaries", "Intermediate", 8, ["async", "types"], "Structure predictable UI trees with stable reconciliation keys.", ["Virtual DOM & key stability", "Controlled vs uncontrolled forms", "Error boundaries & Suspense"]),
        ("hooks", "Author Custom Hooks, Context Boundaries & Memoization", "Intermediate", 8, ["comp"], "Prevent stale closures and unnecessary component re-renders.", ["useReducer & useEffect cleanup", "Custom data-fetching hooks", "useMemo/useCallback profiling"]),
    ]),
    ("state_route", "9. State Management, Routing & Forms", "Query caching, protected routes, and multi-step forms.", [
        ("state", "Implement Stale-While-Revalidate Query Caching & Optimistic UI", "Intermediate", 6, ["hooks"], "Synchronize server state cleanly with instant UI feedback.", ["Request deduplication", "Cache invalidation on mutation", "Optimistic rollback"]),
        ("route", "Configure Nested Routing, Guards & Route Chunk Prefetching", "Intermediate", 5, ["hooks"], "Keep navigation instantaneous with lazy routes and prefetching.", ["React.lazy & Suspense", "Auth route guards", "Hover/idle route prefetch"]),
    ]),
    ("api_err", "10. API Integration & Error Handling", "Typed fetch clients, retries, and resilient fallback UI.", [
        ("api", "Design Typed API Clients with Retries & Graceful Error States", "Intermediate", 5, ["state"], "Handle 401/403/5xx and offline states without breaking UX.", ["Typed ApiError envelopes", "Bounded retry & timeout", "Actionable error recovery UI"]),
    ]),
    ("ds", "11. Component Design & Design Systems", "Reusable UI primitives and multi-theme tokens.", [
        ("ds", "Architect Themeable Design Systems & Composable Primitives", "Intermediate", 6, ["grid", "a11y", "comp"], "Build consistent buttons, modals, and cards across themes.", ["Semantic color tokens", "Compound component patterns", "Reduced-motion compliance"]),
    ]),
    ("perf_sec", "12. Performance Optimization & Frontend Security", "Core Web Vitals and XSS/CSRF defenses.", [
        ("perf", "Optimize LCP, INP, CLS & Production Bundle Splits", "Advanced", 6, ["dom", "route"], "Keep initial JS small and eliminate layout shifts.", ["Bundle analysis & vendor splitting", "Non-blocking font loading", "List virtualization for long feeds"]),
        ("sec", "Prevent XSS, CSRF, Open Redirects & Unsafe URL Injection", "Intermediate", 5, ["api"], "Sanitize untrusted markdown/URLs and enforce CSP.", ["DOMPurify / safe HTML rendering", "http/https URL validation", "CSP & token storage hygiene"]),
    ]),
    ("test_build", "13. Testing, Build Tools & Deployment", "Vitest, Playwright, Vite, Git, and CI/CD.", [
        ("test", "Write Component Unit, Integration & E2E Tests", "Intermediate", 6, ["hooks", "api"], "Verify UI state transitions and accessibility automatically.", ["Testing Library user-event tests", "Mocked network error tests", "Playwright responsive E2E"]),
        ("build", "Configure Vite Bundling, Git Workflows & Static/Edge Deploys", "Intermediate", 5, ["perf"], "Ship verified production builds with preview environments.", ["Rollup manualChunks", "Git feature branches & PRs", "Vercel/CDN cache headers"]),
    ]),
    ("career", "14. Projects, Portfolio & Interview Preparation", "Production capstones and frontend machine coding.", [
        ("proj", "Build & Deploy an Accessible, High-Performance Frontend App", "Advanced", 12, ["test", "perf"], "Demonstrate end-to-end frontend craft with Lighthouse audits.", ["Lighthouse >= 90 metrics", "Responsive mobile-desktop polish", "Architecture case study"]),
        ("int", "Master JavaScript Internals, React Machine Coding & UI System Design", "Advanced", 10, ["proj"], "Solve live coding and frontend architecture prompts.", ["Debounced typeahead & virtual list coding", "State/cache architecture design", "Behavioral STAR walkthroughs"]),
    ]),
])


BACKEND_CATEGORIES = _build_categories("be", [
    ("prog_dsa", "1. Programming, OOP & Data Structures", "Complexity analysis, modular OOP, and clean error handling.", [
        ("dsa", "Apply Data Structures & Big-O Analysis to Server Workloads", "Intermediate", 10, [], "Choose optimal structures for caching, indexing, and queues.", ["Hash maps, heaps, trees, graphs", "Time/space complexity", "LRU caches & tries"]),
        ("oop", "Structure Layered Backend Services Using Clean OOP & Typing", "Beginner", 6, [], "Separate controllers, services, and repositories cleanly.", ["Dependency injection", "Composition & interfaces", "Typed DTOs & exceptions"]),
    ]),
    ("os_linux", "2. Operating Systems & Linux", "Processes, threads, file descriptors, and systemd.", [
        ("os", "Understand Processes, Threads, Memory & File I/O Syscalls", "Intermediate", 8, ["dsa"], "Diagnose CPU, memory, and I/O bottlenecks.", ["Virtual memory & page cache", "Context switching & mutexes", "epoll / async I/O event loops"]),
        ("linux", "Administer Linux Servers, Permissions & Process Diagnostics", "Intermediate", 6, ["os"], "Operate backend services safely in Linux environments.", ["chmod/chown & least privilege", "ss, lsof, top & journalctl", "Shell scripting for ops"]),
    ]),
    ("net", "3. Networking, TCP/IP, DNS & HTTP/HTTPS", "Transport protocols, TLS, and reverse proxies.", [
        ("net", "Trace TCP/IP, DNS, TLS 1.3 & HTTP/1.1-3 Semantics", "Intermediate", 7, ["os"], "Debug connection pooling, timeouts, and TLS termination.", ["TCP 3-way handshake & keep-alive", "DNS records & TTL", "HTTP methods, headers & status codes"]),
    ]),
    ("runtimes", "4. Backend Runtimes & Frameworks (Node.js / Python FastAPI)", "Async event loops, middleware, and OpenAPI.", [
        ("node", "Build Non-Blocking Services with Node.js Streams & Express", "Intermediate", 8, ["net", "oop"], "Handle concurrent HTTP traffic and streaming responses.", ["libuv thread pool & streams", "Express middleware pipelines", "Graceful SIGTERM shutdown"]),
        ("fastapi", "Build Typed Async APIs with Python, FastAPI & Pydantic", "Intermediate", 8, ["net", "oop"], "Validate payloads strictly and manage DB dependencies.", ["Pydantic v2 schema validation", "FastAPI Depends() injection", "Sync vs async route execution"]),
    ]),
    ("api", "5. API Design (REST & GraphQL)", "Resource modeling, versioning, pagination, and schemas.", [
        ("rest", "Design Idempotent, Versioned REST APIs with Cursor Pagination", "Intermediate", 6, ["fastapi"], "Keep API contracts predictable and backward-compatible.", ["Idempotency keys", "Cursor vs offset pagination", "Structured error envelopes"]),
        ("gql", "Implement GraphQL Schemas & DataLoader N+1 Batching", "Intermediate", 5, ["rest"], "Avoid N+1 query storms in nested graph resolvers.", ["SDL schema design", "Resolver authorization", "DataLoader request batching"]),
    ]),
    ("auth_sec", "6. Authentication, Authorization & API Security", "Password hashing, JWT revocation, RBAC, and OWASP API Top 10.", [
        ("auth", "Implement Argon2/bcrypt, JWT Lifecycle & RBAC Ownership", "Intermediate", 8, ["rest"], "Enforce strict per-user authorization on every endpoint.", ["Token signing & revocation lists", "RBAC & resource ownership checks", "OAuth2 / OIDC flows"]),
        ("sec", "Harden APIs Against SQLi, IDOR, SSRF & Rate-Limit Abuse", "Intermediate", 7, ["auth"], "Defend endpoints using OWASP API Security practices.", ["Parameterized SQL & input limits", "Sliding-window rate limiting", "AES-GCM secret encryption"]),
    ]),
    ("sql", "7. Relational Databases, SQL & PostgreSQL", "Normalization, B-Tree indexes, EXPLAIN plans, and ACID.", [
        ("norm", "Design Normalized Relational Schemas & Versioned Migrations", "Intermediate", 8, ["dsa"], "Enforce referential integrity without breaking existing data.", ["1NF-3NF & foreign key cascades", "Additive backward-compatible migrations", "Constraints & unique indexes"]),
        ("pg", "Optimize PostgreSQL Queries with Indexes & ACID Transactions", "Intermediate", 8, ["norm"], "Eliminate slow sequential scans and race conditions.", ["EXPLAIN (ANALYZE, BUFFERS)", "Composite & partial B-Tree indexes", "MVCC, isolation levels & deadlocks"]),
    ]),
    ("nosql_cache", "8. NoSQL, MongoDB, Redis & Caching", "Document stores, in-memory caching, and eviction.", [
        ("nosql", "Model MongoDB Collections, Indexes & Aggregation Pipelines", "Intermediate", 6, ["norm"], "Choose document embedding vs referencing wisely.", ["Compound & TTL indexes", "Aggregation pipelines", "Idempotent upserts"]),
        ("redis", "Implement Redis Cache-Aside, Distributed Locks & Queues", "Intermediate", 7, ["pg"], "Accelerate hot reads and coordinate workers safely.", ["Cache invalidation & stampede guards", "Redis hashes & sorted sets", "Distributed locks with TTL"]),
    ]),
    ("async_dist", "9. Concurrency, Queues, WebSockets & Distributed Systems", "Background workers, idempotency, and consensus basics.", [
        ("queues", "Build Resilient Background Job Queues & WebSocket Channels", "Intermediate", 8, ["redis", "fastapi"], "Process long-running tasks reliably with bounded retries.", ["Dead-letter queues & backoff", "Idempotent job execution", "WebSocket heartbeats & fan-out"]),
        ("dist", "Apply CAP Theorem, Replication & Circuit Breakers", "Advanced", 8, ["queues"], "Design services that degrade gracefully under partial failure.", ["Leader-follower replication", "Consistent hashing & partitioning", "Timeouts, retries & circuit breakers"]),
    ]),
    ("ops_test", "10. Testing, Docker, CI/CD & Cloud Deployment", "Integration suites, containers, and automated pipelines.", [
        ("test", "Write API Integration, Concurrency & Ownership Isolation Tests", "Intermediate", 7, ["sec", "pg"], "Verify transactions, rollbacks, and 401/403 boundaries.", ["Isolated test DBs", "Auth & IDOR negative tests", "Mocking external providers"]),
        ("deploy", "Containerize with Docker & Automate CI/CD Cloud Deploys", "Intermediate", 6, ["linux", "test"], "Ship reproducible builds with zero-downtime rollouts.", ["Multi-stage Dockerfiles", "GitHub Actions CI", "Serverless & managed DBs"]),
    ]),
    ("obs_sd", "11. Monitoring, Scalability & System Design", "Telemetry, capacity planning, and backend interviews.", [
        ("obs", "Instrument Structured Logs, Metrics, Traces & Latency Alerts", "Intermediate", 5, ["deploy"], "Isolate p99 latency spikes and 500 tracebacks quickly.", ["Correlation request IDs", "Prometheus/OpenTelemetry metrics", "Redacting secrets in logs"]),
        ("sd", "Architect High-Throughput Backend Systems & Ace Interviews", "Advanced", 12, ["dist", "obs"], "Design rate limiters, feeds, and storage pipelines under load.", ["Back-of-the-envelope capacity math", "Read/write path separation", "Backend coding & system design mocks"]),
    ]),
])


SOFTWARE_ENGINEER_CATEGORIES = _build_categories("se", [
    ("cs_math", "1. CS Foundations & Discrete Mathematics", "Logic, sets, graphs, and formal reasoning.", [
        ("disc", "Apply Propositional Logic, Sets, Graphs & Recurrences", "Beginner", 8, [], "Reason formally about algorithm correctness and invariants.", ["Proof by induction & contradiction", "Graph theory & trees", "Recurrence relations"]),
        ("arch", "Understand Computer Architecture, CPU Caches & Memory Hierarchy", "Intermediate", 8, ["disc"], "Write cache-friendly code aware of CPU and memory costs.", ["Registers, L1/L2/L3 cache lines", "Instruction pipelining", "Stack, heap & virtual memory"]),
    ]),
    ("dsa", "2. Data Structures & Algorithms", "Core algorithmic problem solving and complexity analysis.", [
        ("ds", "Master Linear Structures, Trees, Heaps & Hash Tables", "Intermediate", 12, ["disc"], "Select data structures with optimal amortized bounds.", ["Arrays, linked lists, stacks, queues", "Balanced BSTs & heaps", "Hash collisions & load factors"]),
        ("algo", "Implement Graph, Greedy, Divide-and-Conquer & DP Algorithms", "Intermediate", 14, ["ds"], "Solve complex optimization and search problems cleanly.", ["BFS, DFS, Dijkstra & topological sort", "Memoization & tabulation DP", "Binary search on answer"]),
    ]),
    ("os_net", "3. Operating Systems, Networking & Databases", "Concurrency primitives, TCP/HTTP, and relational storage.", [
        ("os", "Manage Processes, Threads, Deadlocks & Synchronization", "Intermediate", 9, ["arch"], "Write deadlock-free concurrent software.", ["Mutexes, semaphores & condition vars", "Scheduling & context switches", "Race condition prevention"]),
        ("net_db", "Integrate Networking Protocols & Relational Database ACID", "Intermediate", 9, ["os", "ds"], "Build reliable networked storage-backed applications.", ["TCP/IP, DNS & HTTP semantics", "SQL joins, indexes & normalization", "ACID transactions & isolation"]),
    ]),
    ("paradigms", "4. Programming Paradigms (OOP & Functional Design)", "Modeling complex domains cleanly.", [
        ("oop", "Apply Encapsulation, Polymorphism & Composition Over Inheritance", "Intermediate", 7, ["ds"], "Avoid brittle deep inheritance hierarchies.", ["Interfaces & dependency inversion", "Value objects & invariants", "Refactoring coupling"]),
        ("fp", "Use Immutability, Pure Functions & Algebraic Data Types", "Intermediate", 6, ["oop"], "Reduce side-effect bugs in state transformations.", ["Pure functions & referential transparency", "Higher-order functions", "Discriminated unions & Option/Result"]),
    ]),
    ("sdlc", "5. SDLC, Requirements & Software Architecture", "Turning ambiguous problems into maintainable systems.", [
        ("req", "Conduct Requirements Engineering & Write Architecture Decision Records", "Intermediate", 5, [], "Clarify functional/non-functional constraints before coding.", ["Functional vs NFRs (SLAs, security)", "Trade-off analysis", "Writing concise ADRs"]),
        ("pat", "Apply SOLID Principles, Clean Code & Design Patterns Judiciously", "Intermediate", 8, ["oop", "req"], "Use Strategy, Factory, Adapter, and Observer without over-engineering.", ["SOLID in real modules", "Clean boundaries & modularity", "Avoiding premature abstraction"]),
    ]),
    ("quality", "6. Testing, Debugging & Build Systems", "Verification, root-cause isolation, and reproducible builds.", [
        ("test", "Design Unit, Integration, Property-Based & Regression Suites", "Intermediate", 8, ["pat"], "Catch edge-case regressions before code reaches production.", ["Test pyramid & mocking boundaries", "Boundary & invariant testing", "Deterministic CI test suites"]),
        ("dbg", "Perform Systematic Debugging, Profiling & Root-Cause Analysis", "Intermediate", 6, ["test", "os"], "Isolate memory leaks, deadlocks, and flaky failures.", ["Binary search (git bisect)", "CPU/memory flamegraphs", "Structured logging & postmortems"]),
    ]),
    ("vcs_ci", "7. Version Control, CI/CD & Code Review", "Collaborative engineering workflows.", [
        ("git", "Master Git Workflows, Atomic Commits & Constructive Code Reviews", "Beginner", 5, [], "Review diffs for correctness, clarity, and edge cases.", ["Rebase vs merge & bisect", "Small reviewable PRs", "Reviewing concurrency & security"]),
        ("ci", "Automate Build Systems, Linting, Typechecking & CI/CD Pipelines", "Intermediate", 6, ["git", "test"], "Enforce quality gates automatically on every commit.", ["Make/Gradle/Vite build graphs", "GitHub Actions pipelines", "Canary deploys & rollbacks"]),
    ]),
    ("dist_rel", "8. Distributed Systems, Reliability & Security Engineering", "Fault tolerance, performance, and secure-by-design systems.", [
        ("dist", "Reason About Consensus, Replication, Idempotency & Backpressure", "Advanced", 10, ["os", "net_db"], "Build distributed workflows that survive network partitions.", ["Retries with jitter & idempotency", "CAP/PACELC trade-offs", "Message queues & eventual consistency"]),
        ("sec_perf", "Engineer Secure, High-Performance Production Systems", "Advanced", 8, ["dist", "dbg"], "Eliminate OWASP vulnerabilities and tail-latency bottlenecks.", ["Least privilege & input validation", "Caching & p99 latency tuning", "SLIs, SLOs & error budgets"]),
    ]),
    ("sysdes_proj", "9. System Design, Projects & Technical Interviews", "End-to-end architecture and engineering communication.", [
        ("sd", "Design Scalable Distributed Systems & Storage Architectures", "Advanced", 12, ["dist", "sec_perf"], "Articulate bottlenecks, data models, and scaling trade-offs.", ["Consistent hashing & sharding", "Rate limiters & notification pipelines", "Capacity & cost estimation"]),
        ("proj", "Deliver a Tested, Documented Production Engineering Capstone", "Advanced", 14, ["ci", "sd"], "Demonstrate end-to-end ownership from ADR to deployment.", ["Clean modular codebase", "Automated CI & integration suite", "Technical docs & runbooks"]),
        ("int", "Excel in Algorithmic Coding, OOD & System Design Interviews", "Advanced", 12, ["algo", "sd"], "Communicate invariants, complexity, and trade-offs clearly.", ["Timed DSA problem solving", "Low-level OOD rounds", "Behavioral ownership stories"]),
    ]),
])


AIML_CATEGORIES = _build_categories("ai", [
    ("math", "1. Mathematics for Machine Learning", "Linear algebra, multivariable calculus, probability, and optimization.", [
        ("la", "Apply Vectors, Matrices, Eigenvalues & SVD to ML Representations", "Intermediate", 10, [], "Manipulate embeddings, projections, and covariance matrices.", ["Dot products & norms", "SVD & PCA", "Matrix calculus shapes"]),
        ("calc_opt", "Compute Gradients, Jacobians, Hessians & Convex Optimization", "Intermediate", 10, ["la"], "Understand backpropagation and gradient-based optimizers.", ["Chain rule in computation graphs", "SGD, Momentum, AdamW", "L1/L2 regularization"]),
        ("prob", "Master Probability, Bayes Rule, Distributions & Information Theory", "Intermediate", 10, ["la"], "Formulate likelihoods, priors, and cross-entropy loss.", ["MLE & MAP estimation", "Gaussian, Bernoulli, Categorical", "KL divergence & cross-entropy"]),
    ]),
    ("py_data", "2. Python, DSA, NumPy, Pandas & Data Processing", "Vectorized computation and leakage-free data pipelines.", [
        ("py", "Write Clean Vectorized Python with NumPy & Algorithmic Complexity", "Beginner", 8, [], "Replace slow loops with broadcasting and einsum.", ["NumPy broadcasting & views", "DSA for feature pipelines", "Reproducible environments"]),
        ("eda", "Execute Data Cleaning, Wrangling, EDA & Feature Engineering", "Intermediate", 10, ["py", "prob"], "Detect leakage, outliers, and class imbalance before modeling.", ["Pandas joins & groupby", "Missingness & encoding", "Target-leakage prevention"]),
    ]),
    ("classical", "3. Classical Machine Learning & Evaluation", "Supervised, unsupervised, ensemble methods, and CV.", [
        ("sup", "Train & Diagnose Linear, Logistic, SVM & Tree-Based Models", "Intermediate", 12, ["calc_opt", "eda"], "Build strong interpretable baselines before deep learning.", ["Bias-variance trade-off", "Decision trees & Random Forests", "Gradient Boosting (XGBoost/LightGBM)"]),
        ("unsup", "Apply Clustering, Dimensionality Reduction & Rigorous CV", "Intermediate", 8, ["sup"], "Validate models with stratified/time-series splits and calibration.", ["K-Means, DBSCAN, HDBSCAN", "ROC-AUC, PR-AUC & calibration", "Nested cross-validation"]),
    ]),
    ("dl", "4. Deep Learning, CNNs & RNNs", "PyTorch autograd, normalization, and sequence/vision architectures.", [
        ("nn", "Implement Neural Networks & Training Loops in PyTorch", "Intermediate", 12, ["sup"], "Debug vanishing gradients, initialization, and learning-rate schedules.", ["Autograd & custom Datasets", "BatchNorm vs LayerNorm", "Mixed precision (AMP)"]),
        ("cnn_rnn", "Build Convolutional (CNNs) & Sequence (RNN/LSTM) Models", "Advanced", 10, ["nn"], "Extract spatial and temporal features effectively.", ["ResNet skip connections", "Transfer learning & augmentation", "Sequence masking & vanishing gradients"]),
    ]),
    ("transformers", "5. Transformers, Attention, NLP & Computer Vision", "Self-attention, positional encoding, and multimodal backbones.", [
        ("attn", "Understand Self-Attention, Multi-Head Attention & Transformers", "Advanced", 12, ["cnn_rnn"], "Trace Q/K/V matrix shapes and causal masking.", ["Scaled dot-product attention", "RoPE & positional embeddings", "Encoder vs Decoder architectures"]),
        ("nlp_cv", "Apply Modern Pretrained Models in NLP & Computer Vision", "Advanced", 10, ["attn"], "Fine-tune tokenizers, ViTs, and detection/classification models.", ["BPE/WordPiece tokenization", "Vision Transformers (ViT)", "Task-specific evaluation metrics"]),
    ]),
    ("llm_rag", "6. Large Language Models, Embeddings, Vector DBs & RAG", "Grounded retrieval, fine-tuning, and structured outputs.", [
        ("rag", "Build Grounded RAG Pipelines with Embeddings & Vector Databases", "Advanced", 10, ["attn"], "Retrieve relevant chunks and cite verifiable sources.", ["Dense + BM25 hybrid retrieval", "HNSW vector indexing & chunking", "Citation & hallucination evals"]),
        ("ft", "Fine-Tune LLMs with LoRA/QLoRA & Optimize Inference", "Advanced", 10, ["rag"], "Reduce memory and latency via quantization and KV-caching.", ["LoRA low-rank adapters", "INT8/INT4 quantization", "KV-cache & vLLM batching"]),
    ]),
    ("mlops_resp", "7. MLOps, Deployment, Responsible AI & Security", "Serving, drift monitoring, fairness, and prompt-injection defense.", [
        ("mlops", "Serve Models in Production & Monitor Data/Concept Drift", "Advanced", 9, ["ft"], "Deploy versioned inference APIs with latency SLAs.", ["FastAPI + Docker serving", "Model registries & canary rollouts", "Drift & latency dashboards"]),
        ("resp", "Enforce Responsible AI, Fairness Audits & AI Security", "Advanced", 7, ["mlops"], "Defend against prompt injection, PII leakage, and model bias.", ["Bias/subgroup evaluation", "Prompt-injection & output guards", "Model cards & audit trails"]),
    ]),
    ("proj_int", "8. Practical AI/ML Projects & Research Interviews", "End-to-end systems and ML system design.", [
        ("proj", "Ship a Benchmarked End-to-End ML/LLM Capstone with Evals", "Advanced", 14, ["mlops", "resp"], "Prove model quality with reproducible offline + online evals.", ["Baseline vs tuned ablations", "Automated eval harness", "Containerized inference demo"]),
        ("int", "Master ML Coding, Math Derivations & ML System Design Interviews", "Advanced", 10, ["proj"], "Design recommendation, search, and RAG architectures clearly.", ["Implementing k-means/attention in NumPy", "ML system design trade-offs", "Paper walkthroughs"]),
    ]),
])


DATA_SCIENTIST_CATEGORIES = _build_categories("ds", [
    ("math_stats", "1. Mathematics, Probability & Statistical Inference", "Foundations of uncertainty, estimators, and inference.", [
        ("math", "Apply Linear Algebra & Calculus to Statistical Models", "Intermediate", 8, [], "Understand least squares, covariance, and likelihood gradients.", ["Matrix projections & OLS", "Partial derivatives", "Expectation & variance"]),
        ("stats", "Master Probability, Distributions, Sampling & Confidence Intervals", "Intermediate", 10, ["math"], "Quantify estimator uncertainty and sampling distributions.", ["Central Limit Theorem", "MLE & confidence intervals", "Bootstrap resampling"]),
    ]),
    ("exp_hyp", "2. Hypothesis Testing, A/B Testing & Experimental Design", "Rigorous causal experimentation.", [
        ("hyp", "Conduct Parametric/Non-Parametric Hypothesis Tests & Power Analysis", "Intermediate", 8, ["stats"], "Prevent false positives with sample-size and multiple-testing control.", ["t-tests, chi-square, Mann-Whitney", "Type I/II errors & MDE", "Bonferroni & FDR correction"]),
        ("ab", "Design A/B Tests & Apply Causal Inference (DiD, PSM)", "Advanced", 9, ["hyp"], "Estimate treatment effects when randomization is imperfect.", ["Novelty effects & SRM checks", "CUPED variance reduction", "Difference-in-differences & propensity scores"]),
    ]),
    ("sql_py", "3. SQL, Python, Pandas & Data Wrangling", "Extracting and cleaning messy analytical datasets.", [
        ("sql", "Write Analytical SQL with CTEs, Window Functions & Cohort Queries", "Intermediate", 8, [], "Compute retention, funnels, and rolling metrics in SQL.", ["ROW_NUMBER, LAG/LEAD", "Cohort retention tables", "Query plan efficiency"]),
        ("py", "Clean, Wrangle & Explore Data Using Python, NumPy & Pandas", "Beginner", 8, [], "Build reproducible EDA and data-quality validation scripts.", ["Vectorized Pandas transforms", "Outlier & missingness diagnostics", "Schema assertions"]),
    ]),
    ("viz_story", "4. Data Visualization & Storytelling", "Clear, distortion-free visual communication.", [
        ("viz", "Design Decision-Ready Visualizations & Executive Data Narratives", "Beginner", 6, ["py", "stats"], "Communicate uncertainty and business impact without chartjunk.", ["Choosing chart encodings", "Error bars & distributions", "Executive metric memos"]),
    ]),
    ("ml_ts", "5. Predictive Modeling, Time-Series & Big Data", "Regression, classification, clustering, and forecasting.", [
        ("ml", "Build Interpretable Regression, Classification & Clustering Models", "Intermediate", 12, ["py", "hyp"], "Combine strong baselines with SHAP/feature importance.", ["Regularized GLM & trees", "Leakage-free pipelines", "SHAP & partial dependence"]),
        ("ts", "Forecast Time Series with ARIMA, ETS, Prophet & Cross-Validation", "Advanced", 8, ["ml"], "Handle seasonality, trend, and temporal leakage properly.", ["Stationarity & ACF/PACF", "Rolling-origin CV", "Prediction intervals"]),
        ("big", "Process Large-Scale Datasets with Spark / DuckDB & Parquet", "Intermediate", 6, ["sql", "py"], "Query columnar data lakes efficiently.", ["Columnar Parquet partitioning", "DuckDB/PySpark aggregations", "Skew & shuffle awareness"]),
    ]),
    ("prod_career", "6. Reproducible Research, Deployment & Interviews", "End-to-end data science portfolio and case studies.", [
        ("deploy", "Package Reproducible Notebooks, Pipelines & Model Endpoints", "Intermediate", 7, ["ml"], "Eliminate 'works on my laptop' analysis fragility.", ["Versioned datasets & seeds", "FastAPI scoring service", "Monitoring metric drift"]),
        ("int", "Master Product-Sense Cases, SQL/Stats Rounds & Portfolio Projects", "Advanced", 12, ["ab", "deploy"], "Connect statistical rigor to product and revenue decisions.", ["Metric-drop root-cause cases", "Timed SQL & probability drills", "2 end-to-end case-study projects"]),
    ]),
])


CYBER_CATEGORIES = _build_categories("cy", [
    ("net_os", "1. CS, Networking, Linux & Windows Fundamentals", "Protocol internals and operating-system architecture.", [
        ("net", "Master TCP/IP, Subnetting, DNS, HTTP/TLS & Packet Analysis", "Beginner", 10, [], "Inspect network traffic to spot anomalies and misconfigurations.", ["OSI vs TCP/IP & CIDR", "TLS 1.3 & X.509 PKI", "Wireshark/tcpdump packet dissection"]),
        ("os", "Administer Linux & Windows Internals, Permissions & Scripting", "Intermediate", 10, ["net"], "Navigate processes, registries, ACLs, and Python/Bash automation.", ["Linux capabilities & systemd", "Windows AD, SAM & Event Logs", "Python security automation"]),
    ]),
    ("crypto_iam", "2. Cryptography, Authentication & IAM", "Applied cryptography and least-privilege identity.", [
        ("crypto", "Apply Symmetric/Asymmetric Encryption, Hashing & Signatures", "Intermediate", 8, ["net"], "Select safe cryptographic primitives and avoid broken modes.", ["AES-GCM, ChaCha20 & RSA/ECC", "Argon2/bcrypt & HMAC", "Key management & rotation"]),
        ("iam", "Architect Authentication, OAuth2/OIDC & Least-Privilege IAM", "Intermediate", 7, ["crypto"], "Eliminate privilege escalation paths in identity systems.", ["MFA & session binding", "RBAC vs ABAC policies", "Cloud IAM policy auditing"]),
    ]),
    ("netsec", "3. Network Security, Firewalls & Defensive Architecture", "Segmentation, IDS/IPS, and zero-trust perimeters.", [
        ("fw", "Configure Firewalls, VPNs, Network Segmentation & IDS/IPS", "Intermediate", 8, ["net", "os"], "Isolate critical tiers and detect lateral movement.", ["Stateful firewalls & DMZs", "Zero-trust microsegmentation", "Suricata/Zeek signatures"]),
    ]),
    ("appsec", "4. Web & Application Security (OWASP Top 10 & Secure Coding)", "Preventing and auditing software vulnerabilities safely.", [
        ("owasp", "Identify & Remediate OWASP Top 10 & API Security Flaws", "Intermediate", 10, ["iam"], "Write and review code free of injection and access-control bugs.", ["IDOR, SQLi, XSS, CSRF, SSRF", "Parameterized queries & CSP", "SAST/DAST & dependency scanning"]),
        ("threat", "Conduct STRIDE Threat Modeling & Defensive Vulnerability Assessments", "Intermediate", 7, ["owasp"], "Map trust boundaries and prioritize remediation by risk.", ["STRIDE data-flow diagrams", "CVSS scoring & triage", "Authorized lab pentest methodology"]),
    ]),
    ("soc_ir", "5. Security Monitoring, SIEM, Incident Response & Forensics", "Detecting, containing, and investigating breaches.", [
        ("siem", "Correlate Telemetry in SIEMs & Map Threats to MITRE ATT&CK", "Intermediate", 9, ["fw", "os"], "Write high-signal detection rules with low false positives.", ["Log normalization & correlation", "MITRE ATT&CK tactics", "Alert triage playbooks"]),
        ("ir", "Execute Incident Response, Digital Forensics & Malware Fundamentals", "Advanced", 10, ["siem"], "Contain active incidents and preserve forensic artifacts safely.", ["PICERL IR lifecycle", "Memory/disk timeline forensics", "Static/behavioral malware basics"]),
    ]),
    ("cloud_grc", "6. Cloud Security, Governance, Risk & Compliance", "Securing cloud workloads and organizational posture.", [
        ("cloud", "Harden Cloud Accounts, Containers & Secrets Management", "Advanced", 8, ["iam", "owasp"], "Prevent public bucket exposure and container breakouts.", ["VPC security groups & KMS", "Non-root containers & SBOMs", "Vault / secret rotation"]),
        ("grc", "Apply Risk Management, NIST CSF, ISO 27001 & Security Auditing", "Intermediate", 6, ["threat"], "Align technical controls with compliance and audit evidence.", ["NIST CSF & SOC 2 controls", "Audit evidence collection", "Vendor risk assessment"]),
    ]),
    ("labs_career", "7. Defensive Labs, Projects & Certifications Prep", "Hands-on defensive portfolio and interview readiness.", [
        ("proj", "Complete Defensive Blue-Team Lab & AppSec Audit Capstone", "Advanced", 12, ["ir", "cloud"], "Demonstrate detection engineering and vulnerability remediation.", ["Home-lab SIEM detection rules", "AppSec audit & patch report", "Security+ / Blue-Team interview prep"]),
    ]),
])


CLOUD_CATEGORIES = _build_categories("cl", [
    ("found", "1. CS, Linux & Cloud Networking Foundations", "Virtualization, DNS, HTTP, and IP routing.", [
        ("linux", "Operate Linux Systems, Storage & Network Diagnostics", "Beginner", 8, [], "Troubleshoot compute instances, disks, and sockets.", ["systemd, LVM & filesystems", "ip/ss/dig/curl diagnostics", "SSH & key hardening"]),
        ("net", "Architect Cloud VPCs, Subnets, NAT, DNS & Load Balancers", "Intermediate", 9, ["linux"], "Design segmented public/private multi-AZ networks.", ["CIDR planning & route tables", "ALB/NLB health checks", "Route53/DNS & TLS termination"]),
    ]),
    ("core_svc", "2. Cloud Compute, Storage, Databases & Serverless", "IaaS, managed databases, object storage, and FaaS.", [
        ("comp", "Provision Virtual Machines, Auto-Scaling & Serverless Functions", "Intermediate", 8, ["net"], "Select compute models aligned with workload patterns.", ["VMs & autoscaling groups", "Serverless cold starts & limits", "Spot vs reserved capacity"]),
        ("stor", "Configure Object Storage, Block Volumes & Managed Databases", "Intermediate", 8, ["net"], "Design durable storage tiers with encryption and lifecycle rules.", ["S3/R2 buckets & lifecycle policies", "EBS snapshots & IOPS", "Managed RDS Multi-AZ & read replicas"]),
    ]),
    ("iam_sec", "3. Cloud IAM, Security & Compliance", "Least-privilege policies, KMS, and perimeter defense.", [
        ("iam", "Enforce Least-Privilege IAM Roles, KMS Encryption & WAF", "Intermediate", 8, ["comp", "stor"], "Eliminate wildcard permissions and exposed storage.", ["IAM roles vs long-lived keys", "KMS envelope encryption", "Security groups, NACLs & WAF"]),
    ]),
    ("containers_iac", "4. Containers, Kubernetes & Infrastructure as Code", "Docker, managed Kubernetes, and Terraform.", [
        ("k8s", "Run Containerized Workloads on Docker & Managed Kubernetes", "Intermediate", 10, ["comp"], "Deploy resilient pods with probes and autoscaling.", ["Multi-stage Dockerfiles", "EKS/GKE Pods, Services & Ingress", "HPA & PodDisruptionBudgets"]),
        ("tf", "Provision Declarative Infrastructure with Terraform & Config Mgmt", "Intermediate", 10, ["iam", "k8s"], "Prevent configuration drift with remote state locking.", ["Terraform modules & state locking", "Plan/apply in CI", "Ansible / cloud-init bootstrapping"]),
    ]),
    ("ops_rel", "5. CI/CD, Monitoring, Disaster Recovery & Cost Optimization", "Resilience, backups, and FinOps.", [
        ("obs", "Implement Cloud Monitoring, Centralized Logging & Alerting", "Intermediate", 6, ["k8s"], "Track availability, latency, and resource saturation.", ["CloudWatch/Prometheus metrics", "Log retention & correlation", "Symptom-based paging"]),
        ("dr_cost", "Design Multi-Region Backup/DR & Cloud Cost Optimization", "Advanced", 8, ["stor", "tf"], "Meet RTO/RPO targets while eliminating idle cloud spend.", ["RPO/RTO backup drills", "Right-sizing & FinOps tagging", "Multi-AZ vs multi-region trade-offs"]),
    ]),
    ("arch_career", "6. Cloud Architecture, Projects & Interviews", "Well-Architected systems and cloud interviews.", [
        ("proj", "Deploy a Multi-Tier Well-Architected Cloud Capstone via Terraform", "Advanced", 12, ["obs", "dr_cost"], "Build a documented, fault-tolerant cloud environment.", ["Terraform + CI/CD deployment", "Chaos/failover verification", "Cloud architect scenario interviews"]),
    ]),
])


DEVOPS_CATEGORIES = _build_categories("do", [
    ("linux_script", "1. Linux, Networking & Automation Scripting", "Shell, Python automation, and network troubleshooting.", [
        ("linux", "Master Linux Internals, systemd & Network Troubleshooting", "Beginner", 8, [], "Debug production services, ports, and disk pressure.", ["systemd units & cgroups", "tcpdump, ss, lsof, iostat", "Permissions & kernel sysctls"]),
        ("script", "Write Idempotent Bash & Python Automation Tooling", "Intermediate", 8, ["linux"], "Automate operational tasks safely with error handling.", ["set -euo pipefail & traps", "Python CLI tooling & APIs", "Idempotent retries"]),
    ]),
    ("git_ci", "2. Git, Build Systems & CI/CD Pipelines", "GitHub Actions, Jenkins, and artifact promotion.", [
        ("git", "Manage Branching Strategies, Releases & Artifact Registries", "Beginner", 5, [], "Standardize semantic versioning and traceable builds.", ["Trunk-based vs GitFlow", "SemVer & changelogs", "Container/package registries"]),
        ("cicd", "Build Automated CI/CD Pipelines (GitHub Actions / Jenkins)", "Intermediate", 9, ["git", "script"], "Automate lint, test, security scan, build, and deploy.", ["Pipeline-as-code YAML", "Build caching & matrix runs", "Deployment gates & rollbacks"]),
    ]),
    ("containers_k8s", "3. Docker & Kubernetes Orchestration", "Container internals, Helm/Kustomize, and progressive delivery.", [
        ("docker", "Optimize Multi-Stage Docker Builds & Runtime Security", "Intermediate", 7, ["linux"], "Shrink images and enforce non-root container execution.", ["Layer caching & distroless", "Non-root & read-only rootfs", "Docker Compose"]),
        ("k8s", "Orchestrate Production Kubernetes with Helm, Probes & GitOps", "Intermediate", 12, ["docker", "cicd"], "Manage rolling, blue-green, and canary deployments.", ["Deployments, StatefulSets, Ingress", "Readiness/liveness & requests/limits", "Blue-green & canary rollouts"]),
    ]),
    ("iac_cfg", "4. Infrastructure as Code (Terraform & Ansible)", "Declarative provisioning and configuration management.", [
        ("tf", "Automate Cloud Infrastructure with Terraform Modules & State", "Intermediate", 9, ["cicd"], "Review infra changes via PR plan outputs.", ["Remote state & locking", "Workspaces & reusable modules", "Drift detection"]),
        ("ans", "Configure Hosts & Middleware Idempotently with Ansible", "Intermediate", 6, ["script", "tf"], "Standardize OS hardening and fleet configuration.", ["Playbooks, roles & inventory", "Vault-encrypted variables", "Idempotent handlers"]),
    ]),
    ("obs_sre", "5. Observability (Prometheus, Grafana) & SRE", "Metrics, logs, traces, SLOs, and incident command.", [
        ("prom", "Deploy Prometheus, Grafana Dashboards & Log Aggregation", "Intermediate", 8, ["k8s"], "Visualize Golden Signals and eliminate blind spots.", ["PromQL queries & exporters", "Loki/ELK structured logs", "OpenTelemetry tracing"]),
        ("sre", "Define SLIs/SLOs, Error Budgets & Incident Runbooks", "Advanced", 8, ["prom"], "Balance release velocity with reliability targets.", ["Multi-burn-rate alerts", "On-call incident command", "Blameless postmortems"]),
    ]),
    ("devsecops", "6. DevSecOps, Secrets Management & Scaling", "Shift-left security, Vault, backups, and performance.", [
        ("sec", "Integrate DevSecOps Scanning & Dynamic Secrets Management", "Advanced", 7, ["cicd", "tf"], "Keep secrets out of Git and scan images/IaC in CI.", ["SAST/SCA/Trivy/tfsec gates", "HashiCorp Vault / OIDC", "Backup & disaster recovery"]),
        ("proj", "Build an End-to-End GitOps + Observability Capstone & Interview Prep", "Advanced", 12, ["sre", "sec"], "Demonstrate automated delivery, monitoring, and failover.", ["CI/CD + Terraform + K8s + Grafana", "Load-test & autoscaling proof", "DevOps troubleshooting interviews"]),
    ]),
])


QUANT_DEV_CATEGORIES = _build_categories("qd", [
    ("math", "1. Advanced Mathematics, Probability & Stochastic Processes", "Mathematical rigor for pricing and quantitative systems.", [
        ("la_calc", "Apply Linear Algebra, Multivariable Calculus & Numerical Stability", "Intermediate", 10, [], "Avoid ill-conditioned matrices in portfolio and factor solvers.", ["Cholesky, QR & SVD", "Gradients & Hessians", "IEEE-754 floating-point error"]),
        ("prob", "Master Probability, Statistics & Stochastic Processes", "Intermediate", 12, ["la_calc"], "Model asset paths, jump processes, and tail distributions.", ["Conditional expectation & martingales", "Brownian motion & Ito's Lemma", "Monte Carlo variance reduction"]),
        ("opt", "Solve Convex Optimization & Numerical PDE / Root-Finding Problems", "Intermediate", 9, ["la_calc"], "Implement fast numerical solvers with convergence guarantees.", ["Quadratic programming", "Newton-Raphson & Brent", "Finite-difference PDE grids"]),
    ]),
    ("dsa_cpp", "2. Algorithms, Data Structures & Modern/Advanced C++", "Zero-allocation data structures and systems C++.", [
        ("dsa", "Implement Cache-Friendly Data Structures & Graph/DP Algorithms", "Intermediate", 12, [], "Optimize worst-case and amortized execution latency.", ["Flat hash maps & B-trees", "Priority queues & order books", "Dynamic programming"]),
        ("cpp", "Master Modern C++ (RAII, Templates, Move Semantics & Memory)", "Advanced", 14, ["dsa"], "Eliminate hidden heap allocations on critical execution paths.", ["RAII, smart pointers & custom allocators", "Templates, constexpr & SFINAE/concepts", "Object pools & arena allocation"]),
    ]),
    ("conc_lowlat", "3. Concurrency, Multithreading & Low-Latency Engineering", "Lock-free programming, CPU caches, and kernel bypass.", [
        ("conc", "Build Lock-Free Ring Buffers with Atomics & Memory Ordering", "Advanced", 12, ["cpp"], "Prevent false sharing and mutex contention across cores.", ["std::atomic & acquire-release", "SPSC/MPSC lock-free queues", "Cache-line padding (64B)"]),
        ("os_net", "Tune Linux Kernel, Multicast Networking & Tail Latency (p99.9)", "Advanced", 10, ["conc"], "Minimize jitter from context switches, syscalls, and NICs.", ["CPU pinning & NUMA awareness", "UDP multicast & TCP_NODELAY", "perf, valgrind & flamegraphs"]),
    ]),
    ("py_fin", "4. Python Numerical Computing, Financial Math & Microstructure", "Vectorized research tooling and market mechanics.", [
        ("py", "Build Fast Numerical Pipelines in Python, NumPy & Cython/PyBind11", "Intermediate", 8, ["prob"], "Bridge Python research notebooks with C++ execution libraries.", ["Vectorized NumPy/Pandas", "PyBind11 C++ bindings", "Time-series alignment"]),
        ("mkt", "Model Market Microstructure, Order Books & Financial Mathematics", "Advanced", 10, ["prob", "py"], "Understand matching engines, tick sizes, and market impact.", ["Limit order book (LOB) dynamics", "Bid-ask spread & slippage", "Greeks, yield curves & arbitrage"]),
    ]),
    ("backtest_dist", "5. Backtesting, Distributed Systems & Testing", "Leakage-free simulation and fault-tolerant execution.", [
        ("bt", "Engineer Event-Driven Backtesters Without Look-Ahead Bias", "Advanced", 10, ["mkt", "cpp"], "Validate strategies with realistic fills, fees, and walk-forward CV.", ["Point-in-time data replay", "Survivorship & look-ahead guards", "VaR, Expected Shortfall & drawdown"]),
        ("dist", "Design Distributed Market-Data Feeds, Kill Switches & Determinism", "Advanced", 8, ["os_net", "bt"], "Ensure deterministic replay and automated risk circuit breakers.", ["Sequenced event logs", "Pre-trade risk checks", "Unit/property tests for matching"]),
    ]),
    ("proj_int", "6. Practical Quant Projects & Technical Interviews", "Low-latency matching engine and quant developer interviews.", [
        ("proj", "Build a Benchmarked C++ Limit Order Book & Event Backtester", "Advanced", 14, ["bt", "dist"], "Demonstrate sub-microsecond matching and clean numerical code.", ["1M-order p99 latency benchmark", "Deterministic replay verification", "Quant C++/probability interview prep"]),
    ]),
])


UPSC_IAS_CATEGORIES = _build_categories("ias", [
    ("orient", "1. UPSC CSE Structure & Official Syllabus Orientation", "Official UPSC Civil Services Examination framework (Prelims + Mains + Personality Test).", [
        ("struct", "Map UPSC CSE 3-Stage Architecture, Eligibility & Service Allocation", "Beginner", 6, [], "Understand how IAS is allocated via rank and preference in the unified CSE.", ["Prelims (GS I + CSAT), Mains (1750), Interview (275)", "Official UPSC CSE 2025-2026 syllabus", "Optional subject selection"]),
    ]),
    ("pre_hist_cult", "2. Prelims & Mains: Indian History, Art & Culture, National Movement", "Ancient, Medieval, Art & Culture, and Modern Indian History.", [
        ("anc_med", "Master Ancient & Medieval Indian History, Art & Architecture", "Beginner", 18, ["struct"], "Connect cultural traditions, temple architecture, and literary heritage.", ["Indus Valley to Gupta period", "Bhakti & Sufi movements", "Temple architecture & classical arts"]),
        ("mod_hist", "Trace Modern Indian History & the Indian National Movement (1857–1947)", "Intermediate", 22, ["anc_med"], "Analyze constitutional acts, mass movements, and social reforms.", ["1857 Revolt & socio-religious reforms", "Gandhian era & Civil Disobedience", "Acts of 1909, 1919, 1935 & Independence"]),
    ]),
    ("pre_geo", "3. Prelims & Mains: Indian and World Geography", "Geomorphology, climatology, oceanography, and Indian resources.", [
        ("phys_geo", "Understand Physical Geography (Geomorphology, Climatology, Oceanography)", "Beginner", 16, ["struct"], "Explain plate tectonics, jet streams, ENSO, and ocean currents.", ["Interior of earth & landforms", "Pressure belts & cyclones", "Ocean currents & salinity"]),
        ("ind_geo", "Master Indian Physical, Drainage, Soil, Agricultural & Resource Geography", "Intermediate", 16, ["phys_geo"], "Link monsoon dynamics to Indian cropping, minerals, and maps.", ["Himalayan & Peninsular rivers", "Soils & cropping patterns", "Atlas mapping of passes & parks"]),
    ]),
    ("pre_polity", "4. Prelims & GS II: Indian Polity & Governance", "Constitutional framework, federalism, and public institutions.", [
        ("const", "Master Constitution, Fundamental Rights, DPSP, Parliament & Judiciary", "Beginner", 24, ["struct"], "Interpret constitutional provisions and landmark SC rulings accurately.", ["Preamble, FRs, DPSP & Duties", "Parliament, Executive & Federalism", "Supreme Court & Judicial Review"]),
        ("gov", "Analyze Constitutional Bodies, Governance, Welfare & Citizen Charters", "Intermediate", 16, ["const"], "Evaluate institutional accountability and e-governance reforms.", ["ECI, CAG, UPSC, Finance Commission", "73rd/74th Amendments (PRIs)", "2nd ARC & accountability tools"]),
    ]),
    ("pre_econ_env", "5. Prelims & GS III: Economy, Environment, Ecology & Science", "Macroeconomics, biodiversity, climate change, and General Science.", [
        ("econ", "Analyze National Income, RBI Monetary Policy, Budget & Inclusive Growth", "Intermediate", 22, ["struct"], "Connect fiscal/monetary indicators to inflation, banking, and BoP.", ["GDP, CPI/WPI & RBI tools", "Union Budget, FRBM & Economic Survey", "Agriculture, infrastructure & WTO"]),
        ("env", "Master Ecology, Biodiversity, Protected Areas & Climate Conventions", "Intermediate", 16, ["phys_geo"], "Distinguish conservation statutes and international climate frameworks.", ["WPA 1972, EPA 1986 & Forest Acts", "IUCN categories & Ramsar/Tiger reserves", "UNFCCC COPs, CBD & Paris Agreement"]),
        ("sci", "Cover General Science, Space (ISRO), Biotech & Emerging Technologies", "Beginner", 12, ["struct"], "Understand applied science in space, health, AI, and DPI.", ["ISRO missions & orbits", "Vaccines, CRISPR & public health", "Digital Public Infrastructure & AI"]),
    ]),
    ("csat", "6. Prelims Paper II: CSAT (Qualifying 33%)", "Comprehension, reasoning, numeracy, and data interpretation.", [
        ("rc_log", "Build UPSC Reading Comprehension, Logical Reasoning & Decision-Making Accuracy", "Intermediate", 12, ["struct"], "Extract strict inferences without external assumptions.", ["Assumption vs inference vs corollary", "Syllogisms & analytical puzzles", "Decision-making frameworks"]),
        ("num_di", "Practice Basic Numeracy, Permutations & Data Interpretation", "Intermediate", 12, ["rc_log"], "Achieve comfortable >95/200 buffer under 2-hour pacing.", ["Percentages, ratios & number systems", "Tabular & chart DI", "Timed PYQ pacing"]),
    ]),
    ("mains_gs", "7. Mains Examination: Qualifying Languages, Essay & GS I–IV", "Analytical writing across Society, IR, Security, and Ethics.", [
        ("qual_essay", "Prepare Qualifying Indian Language/English & Philosophical/Policy Essays", "Intermediate", 16, ["const", "econ"], "Draft coherent 1000–1200 word multi-dimensional essays.", ["Qualifying paper minimums", "PESTEL & chronological essay structuring", "Balanced synthesis & transitions"]),
        ("gs123", "Synthesize Mains GS I (Society), GS II (IR) & GS III (Internal Security)", "Advanced", 24, ["mod_hist", "gov", "econ"], "Write 10/15-marker answers in 7 minutes with data and citations.", ["Indian society & urbanization", "India's neighborhood, Quad, BRICS", "Border/cyber security & disaster mgmt"]),
        ("gs4", "Master GS IV: Ethics, Integrity, Aptitude & Administrative Case Studies", "Advanced", 18, ["gov"], "Resolve administrative dilemmas balancing law, empathy, and probity.", ["Foundational civil service values", "Moral thinkers & emotional intelligence", "Stakeholder case-study templates"]),
    ]),
    ("opt_prep", "8. Optional Subject (Papers I–II), Preparation & Personality Test", "Distinct from syllabus: answer writing, PYQs, mocks, and interview.", [
        ("opt", "Complete Optional Subject Papers I & II Syllabus with Scholarly Depth", "Advanced", 36, ["gs123"], "Build high-scoring Optional mastery (500 marks).", ["Paper I foundational theories", "Paper II applied/Indian context", "Interlinking with GS papers"]),
        ("prep", "Execute Answer Writing, Current Affairs Revision, PYQs, Mocks & IAS Interview", "Advanced", 24, ["gs4", "opt"], "Refine speed, revision cycles, and DAF-based Personality Test composure.", ["Daily timed answer writing & PYQs", "3-cycle spaced revision", "DAF profiling & district-admin mock boards"]),
    ]),
])


UPSC_IPS_CATEGORIES = _build_categories("ips", [
    ("orient", "1. UPSC CSE Common Structure & IPS Service Allocation", "IPS is recruited through the same official UPSC CSE (no separate written exam).", [
        ("struct", "Understand Unified UPSC CSE Stages & IPS Allocation Mechanics", "Beginner", 6, [], "Separate common UPSC CSE papers from IPS-specific service preparation.", ["Prelims, Mains & Personality Test", "Service preference & rank allocation", "IPS physical & medical standards"]),
    ]),
    ("prelims", "2. Prelims Examination: GS Paper I & CSAT Paper II", "Same official UPSC Prelims syllabus across Polity, History, Geo, Economy, Env & CSAT.", [
        ("gs_core", "Master Prelims GS I Core (Polity, History, Geography, Economy, Environment)", "Intermediate", 48, ["struct"], "Clear Prelims GS I cutoff with negative-marking discipline.", ["Constitution, Rights & Parliament", "1857–1947 National Movement & Maps", "RBI/Budget, Ecology & ISRO/Tech"]),
        ("csat", "Master CSAT Paper II (Comprehension, Reasoning & Numeracy)", "Intermediate", 16, ["struct"], "Clear the 33% qualifying CSAT requirement reliably.", ["UPSC RC inference passages", "Logical reasoning & puzzles", "Basic numeracy & DI"]),
    ]),
    ("mains", "3. Mains Examination: Essay, GS I–IV, Optional & Current Affairs", "Same official UPSC Mains papers (1750 marks) determining rank.", [
        ("gs12", "Write Structured Mains Essay, GS I & GS II Answers", "Advanced", 26, ["gs_core"], "Integrate constitutional law, governance, and international affairs.", ["Essay structuring & clarity", "Society & modern history", "Polity, governance & diplomacy"]),
        ("gs34", "Master GS III (Internal Security Focus), GS IV (Ethics) & Optional Subject", "Advanced", 38, ["gs_core"], "Excel in internal security, ethical policing dilemmas, and Optional Papers I–II.", ["Cyber/border/LWE internal security", "Ethics in law enforcement case studies", "Optional Papers I & II mastery"]),
    ]),
    ("ips_service", "4. IPS Service Orientation, Policing, Law & Order & Interview", "Service-specific competencies and Personality Test (not separate UPSC written papers).", [
        ("law_order", "Study Police Administration, Criminal Justice System & Public Safety", "Intermediate", 12, ["gs34"], "Understand BNS/BNSS/BSA frameworks, community policing, and forensic readiness.", ["Criminal justice & statutory updates", "Crowd management & crisis leadership", "Cybercrime & forensic coordination"]),
        ("interview", "Prepare Physical/Medical Standards, DAF & IPS Personality Test Board", "Advanced", 16, ["law_order"], "Demonstrate integrity, composure, and field leadership in mock boards.", ["Official physical/medical norms check", "DAF & home-state policing questions", "SVPNPA training & field orientation"]),
    ]),
])
