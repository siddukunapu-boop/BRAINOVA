"""
StudyOS — Authoritative Versioned Career Roadmap Registry
Provides hierarchical curricula: Career Role -> Main Categories -> Topics -> Subtopics
with stable topic IDs, prerequisites, difficulty, estimated hours, authority references,
and explicit coverage audit metadata.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

CURRICULUM_VERSION = "2026.1"


def _t(
    tid: str,
    title: str,
    difficulty: str,
    hours: int,
    prereqs: List[str],
    objective: str,
    subtopics: List[str],
) -> Dict[str, Any]:
    return {
        "topic_id": tid,
        "title": title,
        "difficulty": difficulty,
        "estimated_hours": hours,
        "prerequisites": prereqs,
        "learning_objective": objective,
        "subtopics": subtopics,
    }


def _c(cid: str, title: str, description: str, topics: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "category_id": cid,
        "title": title,
        "description": description,
        "topics": topics,
    }


# ============================================================================
# A. FULL STACK DEVELOPER (43 Categories, Comprehensive Topic & Subtopic Tree)
# ============================================================================

FULL_STACK_CATEGORIES: List[Dict[str, Any]] = [
    _c("fs_cs_foundations", "1. Computer Science Foundations", "Core computing abstractions, memory, and complexity.", [
        _t("fs_cs_01", "Binary, Memory Model & Execution Stack", "Beginner", 4, [], "Understand how code executes in memory across stack and heap.", ["Bits, bytes & character encodings (UTF-8)", "Call stack frames vs heap allocation", "Processes vs threads"]),
        _t("fs_cs_02", "Data Structures & Asymptotic Complexity (Big-O)", "Intermediate", 10, ["fs_cs_01"], "Analyze time/space complexity and choose optimal structures.", ["Big-O, Omega, Theta bounds", "Arrays, hash maps, stacks, queues", "Trees, heaps, graphs & traversal"]),
    ]),
    _c("fs_prog_fund", "2. Programming Fundamentals", "Clean control flow, modularity, and problem decomposition.", [
        _t("fs_pf_01", "Variables, Scope, Functions & Error Handling", "Beginner", 6, ["fs_cs_01"], "Write modular, predictable functions with explicit error paths.", ["Lexical scope & pure functions", "Recursion & iteration", "Exceptions vs Result/error returns"]),
        _t("fs_pf_02", "Object-Oriented & Functional Patterns", "Intermediate", 6, ["fs_pf_01"], "Model domain entities cleanly using composition and immutability.", ["Encapsulation & composition over inheritance", "Map, filter, reduce & higher-order functions", "SOLID principles in practice"]),
    ]),
    _c("fs_html", "3. HTML", "Semantic document structure and standards-compliant markup.", [
        _t("fs_html_01", "Semantic HTML5 Elements & Document Outline", "Beginner", 4, [], "Structure accessible web documents using semantic tags.", ["header, nav, main, article, section, footer", "Headings hierarchy & landmarks", "Meta tags & SEO document structure"]),
        _t("fs_html_02", "Forms, Validation & Media Elements", "Beginner", 4, ["fs_html_01"], "Build native accessible forms and responsive media.", ["Input types, labels & fieldsets", "Native constraint validation attributes", "Picture, srcset, audio & video"]),
    ]),
    _c("fs_css", "4. CSS", "Modern styling, cascade control, and layout systems.", [
        _t("fs_css_01", "Cascade, Specificity, Box Model & Custom Properties", "Beginner", 5, ["fs_html_01"], "Control styling predictably with CSS variables and box-sizing.", ["Specificity & inheritance rules", "Box model, margin collapse & units (rem/em/vh)", "CSS custom properties (--tokens)"]),
        _t("fs_css_02", "Flexbox, CSS Grid & Transitions", "Beginner", 6, ["fs_css_01"], "Construct complex two-dimensional layouts and subtle motion.", ["Flexbox alignment & wrapping", "CSS Grid tracks, areas & minmax()", "Transforms, transitions & prefers-reduced-motion"]),
    ]),
    _c("fs_js", "5. JavaScript", "Modern ECMAScript internals, closures, and async execution.", [
        _t("fs_js_01", "Closures, Prototypes, `this` & ES Modules", "Intermediate", 8, ["fs_pf_01", "fs_html_01"], "Master JavaScript execution context and module boundaries.", ["Execution context & lexical closures", "Prototypal inheritance & class syntax", "ESM import/export & tree-shaking"]),
        _t("fs_js_02", "Event Loop, Promises, Async/Await & Fetch", "Intermediate", 8, ["fs_js_01"], "Handle asynchronous flows, cancellation, and concurrency safely.", ["Call stack, microtask queue & macrotask queue", "Promise.all / allSettled / race", "Fetch API & AbortController cancellation"]),
    ]),
    _c("fs_ts", "6. TypeScript", "Static type safety for scalable frontend and backend code.", [
        _t("fs_ts_01", "Type Inference, Interfaces, Unions & Narrowing", "Intermediate", 6, ["fs_js_01"], "Eliminate runtime type bugs with strict compiler checks.", ["Primitive, literal & union types", "Type guards & discriminated unions", "strictNullChecks & unknown vs any"]),
        _t("fs_ts_02", "Generics, Utility Types & Typed API Contracts", "Intermediate", 6, ["fs_ts_01"], "Author reusable generic components and API wrappers.", ["Generic constraints (extends, keyof)", "Partial, Pick, Omit, Record", "Typing async fetch & form payloads"]),
    ]),
    _c("fs_fe_eng", "7. Frontend Engineering", "Component-driven UI engineering and build tooling.", [
        _t("fs_fe_01", "Module Bundlers, Vite & Asset Pipelines", "Intermediate", 4, ["fs_js_02", "fs_ts_01"], "Configure fast builds, env variables, and code splitting.", ["Vite dev server & Rollup production chunks", "Dynamic import() & lazy loading", "Environment variables & CSP safety"]),
    ]),
    _c("fs_react", "8. React", "Declarative UI, hooks, and rendering optimization.", [
        _t("fs_react_01", "Components, JSX, Props & Virtual DOM Reconciliation", "Intermediate", 6, ["fs_js_02", "fs_ts_01"], "Build composable React components with stable keys.", ["Pure render functions & key stability", "Controlled vs uncontrolled inputs", "Error boundaries & Suspense"]),
        _t("fs_react_02", "React Hooks, Custom Hooks & Memoization", "Intermediate", 8, ["fs_react_01"], "Manage side effects, refs, and performance cleanly.", ["useState, useReducer, useEffect cleanup", "useRef, useMemo & useCallback", "Designing reusable custom hooks"]),
    ]),
    _c("fs_state", "9. State Management", "Predictable client, server, and URL state synchronization.", [
        _t("fs_state_01", "Context API, Query Caching & Optimistic Updates", "Intermediate", 6, ["fs_react_02"], "Separate server cache state from local UI state.", ["Context boundaries & avoiding render storms", "Stale-while-revalidate query caching", "Optimistic mutations & rollback"]),
    ]),
    _c("fs_routing", "10. Routing and Application Architecture", "Client-side routing, guards, and modular folder structure.", [
        _t("fs_route_01", "Declarative Routing, Protected Routes & Prefetching", "Intermediate", 5, ["fs_react_02"], "Implement nested routes, auth guards, and route prefetching.", ["Nested routes & URL search params", "Auth guards & fallback redirects", "Hover/idle route chunk prefetching"]),
    ]),
    _c("fs_a11y", "11. Accessibility", "Inclusive WCAG-compliant interfaces and keyboard navigation.", [
        _t("fs_a11y_01", "ARIA Roles, Focus Management & Contrast", "Intermediate", 4, ["fs_html_02", "fs_css_02"], "Ensure full keyboard and screen-reader usability.", ["Keyboard tab order & focus traps in modals", "aria-expanded, aria-pressed & live regions", "WCAG AA contrast ratios"]),
    ]),
    _c("fs_responsive", "12. Responsive Design", "Fluid interfaces across mobile, tablet, and desktop viewports.", [
        _t("fs_resp_01", "Mobile-First Breakpoints, Fluid Typography & Touch Targets", "Beginner", 4, ["fs_css_02"], "Prevent horizontal overflow and ensure touch ergonomics.", ["Media queries & container queries", "clamp() fluid spacing & type", "44px+ touch targets & collapsible drawers"]),
    ]),
    _c("fs_browser", "13. Browser Internals and Web APIs", "Rendering pipeline, storage, and security boundaries.", [
        _t("fs_br_01", "Critical Rendering Path, DOM/CSSOM & Storage APIs", "Intermediate", 5, ["fs_js_02"], "Optimize paint/layout and choose safe browser storage.", ["Layout, paint & composite layers", "localStorage, sessionStorage & IndexedDB", "CORS, SameSite cookies & Web Workers"]),
    ]),
    _c("fs_be_eng", "14. Backend Engineering", "Server architecture, request lifecycles, and concurrency.", [
        _t("fs_be_01", "HTTP Server Architecture, Middleware & Validation", "Intermediate", 6, ["fs_js_02"], "Build layered backend services with strict boundary validation.", ["Controller-service-repository layering", "Middleware pipelines & structured logging", "Schema validation & error envelopes"]),
    ]),
    _c("fs_node", "15. Node.js", "Event-driven server runtime, streams, and async I/O.", [
        _t("fs_node_01", "Node.js Runtime, Streams, Buffers & File I/O", "Intermediate", 6, ["fs_js_02", "fs_be_01"], "Handle streaming payloads and non-blocking I/O safely.", ["EventEmitter & libuv thread pool", "Readable/Writable streams & backpressure", "Path traversal prevention & fs promises"]),
    ]),
    _c("fs_express", "16. Express.js or Equivalent Framework (FastAPI)", "Routing, dependency injection, and middleware design.", [
        _t("fs_exp_01", "Express.js / FastAPI Routing & Dependency Injection", "Intermediate", 6, ["fs_be_01"], "Structure modular routers, guards, and OpenAPI schemas.", ["Router modules & route parameters", "Auth & rate-limit middleware", "Typed request/response models"]),
    ]),
    _c("fs_rest", "17. REST APIs", "Resource-oriented API design, versioning, and idempotency.", [
        _t("fs_rest_01", "REST Semantics, Pagination, Filtering & Idempotency", "Intermediate", 5, ["fs_exp_01"], "Design predictable, backward-compatible HTTP APIs.", ["Idempotent PUT/DELETE vs POST", "Cursor vs offset pagination", "HTTP status codes & problem+json errors"]),
    ]),
    _c("fs_graphql", "18. GraphQL", "Typed graph schemas, resolvers, and N+1 mitigation.", [
        _t("fs_gql_01", "GraphQL Schemas, Queries, Mutations & DataLoader", "Intermediate", 5, ["fs_rest_01"], "Expose flexible typed graphs without N+1 database storms.", ["SDL types, queries & mutations", "Resolver context & auth checks", "Batching with DataLoader"]),
    ]),
    _c("fs_auth", "19. Authentication and Authorization", "Identity verification, session lifecycle, and RBAC.", [
        _t("fs_auth_01", "Password Hashing, JWTs, OAuth2 & RBAC Ownership", "Intermediate", 7, ["fs_rest_01"], "Implement secure login, token revocation, and ownership checks.", ["Argon2 / bcrypt password hashing", "JWT signing, expiry & token revocation", "Role-based & per-resource ownership guards"]),
    ]),
    _c("fs_sec", "20. Security", "OWASP Top 10 defenses and secure data handling.", [
        _t("fs_sec_01", "OWASP Top 10, XSS/CSRF/SQLi Prevention & Secrets", "Intermediate", 6, ["fs_auth_01"], "Harden full-stack apps against common web exploits.", ["Parameterized queries & output escaping", "CSP, CORS & rate limiting", "AES-GCM secret encryption & key rotation"]),
    ]),
    _c("fs_sql", "21. SQL", "Relational querying, joins, aggregations, and CTEs.", [
        _t("fs_sql_01", "Joins, Groupings, Window Functions & CTEs", "Intermediate", 6, ["fs_cs_02"], "Write expressive, performant analytical and transactional SQL.", ["INNER/LEFT/FULL JOIN semantics", "GROUP BY, HAVING & window functions", "Common Table Expressions (CTEs)"]),
    ]),
    _c("fs_db_design", "22. Database Design", "Normalization, constraints, and safe schema migrations.", [
        _t("fs_dbd_01", "ER Modeling, Normalization (1NF-3NF) & Migrations", "Intermediate", 6, ["fs_sql_01"], "Model relational integrity and zero-downtime migrations.", ["Primary/foreign keys & ON DELETE CASCADE", "1NF, 2NF, 3NF trade-offs", "Additive versioned schema migrations"]),
    ]),
    _c("fs_postgres", "23. PostgreSQL", "Production RDBMS indexing, query plans, and ACID.", [
        _t("fs_pg_01", "B-Tree/GIN Indexes, EXPLAIN ANALYZE & Transactions", "Intermediate", 6, ["fs_dbd_01"], "Diagnose slow queries and enforce ACID isolation.", ["EXPLAIN (ANALYZE, BUFFERS)", "Composite & partial indexes", "MVCC & isolation levels"]),
    ]),
    _c("fs_nosql", "24. NoSQL", "Document, key-value, and wide-column modeling trade-offs.", [
        _t("fs_nosql_01", "NoSQL Data Models & CAP Theorem Trade-Offs", "Intermediate", 4, ["fs_dbd_01"], "Select SQL vs NoSQL based on access patterns.", ["Document vs relational embedding vs referencing", "Consistency vs availability trade-offs", "Idempotent upserts & TTL indexes"]),
    ]),
    _c("fs_mongo", "25. MongoDB", "Document schemas, aggregation pipelines, and indexing.", [
        _t("fs_mongo_01", "MongoDB Collections, Indexes & Aggregation Pipelines", "Intermediate", 5, ["fs_nosql_01"], "Design high-throughput MongoDB collections cleanly.", ["Compound & unique indexes", "Aggregation stages ($match, $group, $lookup)", "Atomic updates & connection pooling"]),
    ]),
    _c("fs_caching", "26. Caching", "HTTP, CDN, and application-layer caching strategies.", [
        _t("fs_cache_01", "Cache-Aside, Write-Through & HTTP Cache Headers", "Intermediate", 5, ["fs_rest_01"], "Accelerate reads while preventing stale data bugs.", ["Cache-Control, ETag & stale-while-revalidate", "Cache invalidation & thundering-herd protection", "TTL vs event-driven eviction"]),
    ]),
    _c("fs_redis", "27. Redis", "In-memory data structures, rate limiting, and queues.", [
        _t("fs_redis_01", "Redis Strings, Hashes, Sorted Sets & Rate Limiters", "Intermediate", 5, ["fs_cache_01"], "Use Redis for sub-millisecond caching and distributed locks.", ["TTL keys & sliding-window rate limiters", "Pub/Sub & Streams", "Eviction policies (allkeys-lru)"]),
    ]),
    _c("fs_api_int", "28. API Integration", "Resilient third-party webhooks, retries, and timeouts.", [
        _t("fs_api_01", "Timeouts, Exponential Backoff & Webhook Verification", "Intermediate", 4, ["fs_rest_01"], "Integrate external APIs without cascading failures.", ["Bounded timeouts & jittered retries", "Circuit breakers & fallback states", "HMAC webhook signature verification"]),
    ]),
    _c("fs_testing", "29. Testing", "Unit, integration, and end-to-end automated verification.", [
        _t("fs_test_01", "Unit, Integration & E2E Testing Pyramid", "Intermediate", 6, ["fs_react_02", "fs_rest_01"], "Prevent regressions with fast, deterministic test suites.", ["Unit tests & boundary assertions", "API integration & auth isolation tests", "Playwright/Cypress critical user-flow E2E"]),
    ]),
    _c("fs_git", "30. Git and GitHub", "Branching, code review, and clean commit history.", [
        _t("fs_git_01", "Branching, Rebasing, PR Reviews & Bisect", "Beginner", 4, [], "Collaborate cleanly and isolate regressions rapidly.", ["Feature branches, rebase vs merge", "Resolving merge conflicts safely", "git bisect & atomic commits"]),
    ]),
    _c("fs_linux", "31. Linux", "Shell proficiency, permissions, and process diagnostics.", [
        _t("fs_linux_01", "Shell Scripting, Permissions, Processes & systemd", "Intermediate", 5, [], "Operate and debug Linux production servers confidently.", ["chmod/chown, users & SSH keys", "ps, top, lsof, ss & journalctl", "Bash pipes, grep & automation scripts"]),
    ]),
    _c("fs_net", "32. Networking and HTTP", "DNS, TCP/TLS, and reverse proxies.", [
        _t("fs_net_01", "DNS, TCP/IP, TLS 1.3 & Reverse Proxies", "Intermediate", 5, ["fs_linux_01"], "Trace end-to-end request routing and TLS termination.", ["DNS A/CNAME/TXT & TTL", "TCP handshake & HTTP/2 multiplexing", "Nginx/CDN reverse proxy headers"]),
    ]),
    _c("fs_docker", "33. Docker", "Reproducible containers and multi-stage builds.", [
        _t("fs_docker_01", "Dockerfiles, Multi-Stage Builds & Compose", "Intermediate", 5, ["fs_linux_01"], "Package full-stack services cleanly with minimal images.", ["Layer caching & .dockerignore", "Non-root container execution", "Docker Compose multi-service networking"]),
    ]),
    _c("fs_cicd", "34. CI/CD", "Automated build, test, and deployment pipelines.", [
        _t("fs_cicd_01", "GitHub Actions, Automated Checks & Rollbacks", "Intermediate", 4, ["fs_git_01", "fs_test_01"], "Automate lint, typecheck, tests, and safe deploys.", ["CI workflow triggers & matrix builds", "Secret management in CI", "Preview environments & rollback strategy"]),
    ]),
    _c("fs_cloud", "35. Cloud and Deployment", "Serverless, managed DBs, and edge distribution.", [
        _t("fs_cloud_01", "Serverless Functions, Object Storage & Env Config", "Intermediate", 5, ["fs_docker_01", "fs_cicd_01"], "Deploy full-stack apps under serverless constraints.", ["Cold starts & stateless handlers", "Managed DBs & S3/R2 object storage", "CDN caching & custom domains"]),
    ]),
    _c("fs_perf", "36. Performance Optimization", "Core Web Vitals, bundle splitting, and query tuning.", [
        _t("fs_perf_01", "LCP/INP/CLS, Bundle Splitting & N+1 Elimination", "Advanced", 6, ["fs_react_02", "fs_pg_01"], "Measure and eliminate frontend and backend bottlenecks.", ["Code splitting & route prefetching", "Eliminating layout shifts (CLS)", "Profiling slow SQL & API endpoints"]),
    ]),
    _c("fs_scale", "37. Scalability", "Horizontal scaling, queues, and stateless design.", [
        _t("fs_scale_01", "Load Balancing, Sharding & Async Job Queues", "Advanced", 6, ["fs_cloud_01", "fs_redis_01"], "Scale reads, writes, and background workloads safely.", ["Stateless services & sticky-session avoidance", "Read replicas & partitioning", "Background worker queues & dead-letter queues"]),
    ]),
    _c("fs_sysdes", "38. System Design", "End-to-end architecture trade-offs and ADRs.", [
        _t("fs_sd_01", "Designing High-Throughput Web Systems", "Advanced", 8, ["fs_scale_01", "fs_perf_01"], "Synthesize storage, caching, queues, and consistency.", ["Capacity estimation & bottleneck identification", "Rate limiters, feeds & real-time notifications", "Architecture Decision Records (ADRs)"]),
    ]),
    _c("fs_obs", "39. Monitoring and Logging", "Structured logs, metrics, traces, and alerts.", [
        _t("fs_obs_01", "Golden Signals, Correlation IDs & Error Tracking", "Intermediate", 4, ["fs_cloud_01"], "Observe production health without leaking secrets.", ["Structured JSON logging with request IDs", "Latency percentiles (p50/p95/p99)", "Actionable alerts vs alert fatigue"]),
    ]),
    _c("fs_debug", "40. Production Debugging", "Root-cause analysis, incident triage, and postmortems.", [
        _t("fs_dbg_01", "Reproducing 500s, Memory Leaks & Blameless Postmortems", "Advanced", 4, ["fs_obs_01"], "Diagnose live failures methodically without guesswork.", ["Reading server tracebacks & heap profiles", "Isolating cold-start & env-var regressions", "Writing blameless postmortems"]),
    ]),
    _c("fs_best", "41. Software Engineering Best Practices", "Maintainability, documentation, and code review.", [
        _t("fs_best_01", "Clean Code, Refactoring & Technical Documentation", "Intermediate", 4, ["fs_git_01"], "Keep codebases legible and safe for team velocity.", ["Small single-purpose functions", "Meaningful PR descriptions & ADRs", "Incremental safe refactoring"]),
    ]),
    _c("fs_proj", "42. Projects and Portfolio", "Production-grade capstones demonstrating full-stack mastery.", [
        _t("fs_proj_01", "End-to-End Deployed Full Stack Capstone", "Advanced", 16, ["fs_auth_01", "fs_test_01", "fs_cloud_01"], "Build and deploy a tested, documented full-stack app.", ["Auth + RBAC + normalized DB", "Automated CI tests & performance budget", "Live deployment & architecture README"]),
    ]),
    _c("fs_int", "43. Interview Preparation", "Coding rounds, system design, and behavioral mastery.", [
        _t("fs_int_01", "DSA Problem Solving, System Design & STAR Stories", "Advanced", 12, ["fs_cs_02", "fs_sd_01", "fs_proj_01"], "Communicate trade-offs and solve problems under time pressure.", ["Timed DSA patterns (sliding window, trees, DP)", "Frontend/backend machine coding rounds", "Behavioral STAR project deep-dives"]),
    ]),
]


# ============================================================================
# B. QUANTUM COMPUTING ENGINEER (40 Categories, Domain-Authentic Curriculum)
# ============================================================================

QUANTUM_CATEGORIES: List[Dict[str, Any]] = [
    _c("qc_math", "1. Mathematics Foundations", "Mathematical maturity for quantum mechanics and algorithms.", [
        _t("qc_math_01", "Proof Techniques, Sets, Functions & Vector Spaces", "Beginner", 6, [], "Read and verify formal mathematical derivations.", ["Direct, contradiction & induction proofs", "Mappings, bijections & group basics", "Vector space axioms"]),
    ]),
    _c("qc_linalg", "2. Linear Algebra", "The core mathematical language of quantum computing.", [
        _t("qc_la_01", "Matrices, Eigenvalues, Unitary & Hermitian Operators", "Intermediate", 10, ["qc_math_01"], "Manipulate quantum operators and spectral decompositions.", ["Inner products & orthonormal bases", "Unitary (U†U = I) & Hermitian (H† = H) matrices", "Eigenvalues, eigenvectors & spectral theorem"]),
    ]),
    _c("qc_complex", "3. Complex Numbers", "Phases, amplitudes, and Euler geometry.", [
        _t("qc_cx_01", "Complex Plane, Polar Form, Euler's Formula & Conjugates", "Beginner", 5, ["qc_math_01"], "Compute probability amplitudes and global vs relative phases.", ["Cartesian vs polar representation", "Complex conjugate & modulus squared |α|²", "Roots of unity (critical for QFT)"]),
    ]),
    _c("qc_prob", "4. Probability and Statistics", "Born rule, expectation values, and shot noise.", [
        _t("qc_prob_01", "Distributions, Expectation, Variance & Sampling Error", "Beginner", 6, ["qc_math_01"], "Interpret measurement statistics and finite-shot uncertainty.", ["Discrete probability distributions", "Expectation value & standard deviation", "Monte Carlo shot-noise scaling (1/√N)"]),
    ]),
    _c("qc_calc", "5. Calculus", "Continuous optimization and Hamiltonian evolution.", [
        _t("qc_calc_01", "Multivariable Gradients, Jacobians & Matrix Exponentials", "Intermediate", 6, ["qc_la_01"], "Compute parameter-shift gradients and time-evolution operators.", ["Partial derivatives & chain rule", "Gradient descent in variational circuits", "Matrix exponential e^(-iHt)"]),
    ]),
    _c("qc_discrete", "6. Discrete Mathematics", "Boolean logic, modular arithmetic, and number theory.", [
        _t("qc_disc_01", "Boolean Functions, Modular Arithmetic & Continued Fractions", "Intermediate", 6, ["qc_math_01"], "Master number theory required for Shor's algorithm.", ["XOR, reversible Boolean logic & truth tables", "Modular exponentiation & Euler's totient", "Euclidean algorithm & continued fractions"]),
    ]),
    _c("qc_classical", "7. Classical Computing Foundations", "Reversible computing and classical simulation limits.", [
        _t("qc_cl_01", "Turing Machines, Reversible Gates (Toffoli/Fredkin) & Complexity", "Intermediate", 5, ["qc_disc_01"], "Bridge classical logic gates to unitary quantum circuits.", ["Landauer's principle & reversibility", "Toffoli (CCNOT) universality", "P, NP, BPP & exponential state-vector scaling"]),
    ]),
    _c("qc_python", "8. Python Programming", "Scientific Python and numerical array computing.", [
        _t("qc_py_01", "Python, NumPy Linear Algebra & Complex Array Operations", "Beginner", 8, [], "Implement state-vector simulators in clean vectorized Python.", ["NumPy complex128 arrays & einsum", "Matrix multiplication & Kronecker products", "Unit testing numerical tolerances"]),
    ]),
    _c("qc_dsa", "9. Algorithms and Data Structures", "Classical algorithmic baselines for quantum comparison.", [
        _t("qc_dsa_01", "Graph Algorithms, FFT & Dynamic Programming", "Intermediate", 8, ["qc_py_01"], "Understand classical FFT and graph baselines.", ["Classical Fast Fourier Transform (FFT)", "Graph coloring & Max-Cut formulations", "Branch-and-bound & classical heuristics"]),
    ]),
    _c("qc_info", "10. Classical Information Theory", "Shannon entropy, mutual information, and error bounds.", [
        _t("qc_info_01", "Shannon Entropy, Channel Capacity & Classical Error Codes", "Intermediate", 5, ["qc_prob_01"], "Contrast classical parity codes with quantum error correction.", ["Shannon entropy H(X) & KL divergence", "Hamming distance & linear block codes", "No-cloning contrast with classical copying"]),
    ]),
    _c("qc_qm", "11. Quantum Mechanics Foundations", "Postulates of quantum mechanics for computation.", [
        _t("qc_qm_01", "State Postulate, Unitary Evolution & Schrödinger Equation", "Intermediate", 8, ["qc_la_01", "qc_cx_01"], "Connect physical postulates to circuit operations.", ["Closed-system unitary evolution", "Observables as Hermitian operators", "Commutators & Heisenberg uncertainty"]),
    ]),
    _c("qc_states", "12. Quantum States", "Pure states, mixed states, and density matrices.", [
        _t("qc_st_01", "Pure vs Mixed States, Bloch Sphere & Density Operators", "Intermediate", 7, ["qc_qm_01"], "Represent single-qubit states on the Bloch sphere and density matrices.", ["Bloch vector (θ, φ) visualization", "Density matrix ρ = Σ p_i |ψ_i⟩⟨ψ_i|", "Purity Tr(ρ²) & partial trace"]),
    ]),
    _c("qc_super", "13. Superposition", "Coherent linear combinations and interference.", [
        _t("qc_sup_01", "Superposition, Relative Phase & Constructive Interference", "Beginner", 4, ["qc_st_01"], "Explain why interference—not parallelism alone—powers quantum speedups.", ["|0⟩, |1⟩, |+⟩, |−⟩ bases", "Global phase invariance vs relative phase", "Mach-Zehnder & Hadamard interference"]),
    ]),
    _c("qc_meas", "14. Measurement", "Projective measurements, Born rule, and POVMs.", [
        _t("qc_meas_01", "Projective Measurement, Born Rule & Mid-Circuit Collapse", "Intermediate", 5, ["qc_st_01"], "Calculate measurement probabilities and post-measurement states.", ["Projection operators P_m", "Computational vs Hadamard/Bell basis measurement", "POVMs & deferred measurement principle"]),
    ]),
    _c("qc_dirac", "15. Dirac Notation", "Fluency in bra-ket algebra.", [
        _t("qc_dir_01", "Bras, Kets, Inner/Outer Products & Completeness", "Beginner", 4, ["qc_la_01"], "Translate effortlessly between matrices and bra-ket notation.", ["|ψ⟩, ⟨ψ|, ⟨φ|ψ⟩ & |ψ⟩⟨φ|", "Spectral decomposition Σ λ_i |i⟩⟨i|", "Expectation ⟨ψ|A|ψ⟩"]),
    ]),
    _c("qc_hilbert", "16. Hilbert Spaces", "Complex inner-product spaces for multi-qubit systems.", [
        _t("qc_hilb_01", "Finite-Dimensional Hilbert Spaces & Subspaces", "Intermediate", 5, ["qc_dir_01"], "Work with 2^n-dimensional state spaces cleanly.", ["Completeness & orthonormal basis expansion", "Projections onto computational subspaces", "Operator norms & trace distance"]),
    ]),
    _c("qc_qubits", "17. Qubits", "Physical and logical qubit modalities.", [
        _t("qc_qbt_01", "Logical Qubits vs Physical Qubit Realizations", "Intermediate", 4, ["qc_st_01"], "Compare superconducting, trapped-ion, photonic, and neutral-atom qubits.", ["Two-level system physics", "T1 relaxation & T2 dephasing times", "Gate fidelity & connectivity trade-offs"]),
    ]),
    _c("qc_gates", "18. Quantum Gates", "Single-qubit and multi-qubit unitary transformations.", [
        _t("qc_gt_01", "Pauli, Hadamard, Phase, Rotation & CNOT/CZ Gates", "Intermediate", 6, ["qc_hilb_01"], "Compose universal gate sets and matrix representations.", ["X, Y, Z, H, S, T & Rx/Ry/Rz rotations", "Controlled gates: CNOT, CZ, SWAP, Toffoli", "Clifford+T universal gate set & Solovay-Kitaev"]),
    ]),
    _c("qc_circuits", "19. Quantum Circuits", "Circuit diagrams, depth, and transpilation.", [
        _t("qc_circ_01", "Circuit Synthesis, Depth Optimization & Hardware Transpilation", "Intermediate", 6, ["qc_gt_01"], "Compile abstract circuits onto constrained qubit topologies.", ["Circuit width, depth & 2-qubit gate count", "Gate identities & cancellation rules", "SWAP routing for limited coupling maps"]),
    ]),
    _c("qc_tensor", "20. Tensor Products", "Multi-qubit composite state spaces.", [
        _t("qc_ten_01", "Kronecker Products of States & Multi-Qubit Operators", "Intermediate", 5, ["qc_hilb_01"], "Compute 2-qubit and n-qubit state vectors and operators.", ["|ψ⟩ ⊗ |φ⟩ & tensor order conventions", "I ⊗ X vs X ⊗ I operator action", "Separable vs non-separable states"]),
    ]),
    _c("qc_entangle", "21. Entanglement", "Non-classical correlations and Bell inequalities.", [
        _t("qc_ent_01", "Bell States, GHZ/W States & CHSH Inequality", "Intermediate", 6, ["qc_ten_01", "qc_meas_01"], "Generate and verify maximally entangled states.", ["Four Bell states |Φ±⟩, |Ψ±⟩", "Reduced density matrices & entanglement entropy", "CHSH game & Bell's theorem"]),
    ]),
    _c("qc_teleport", "22. Quantum Teleportation", "Entanglement-assisted state transfer and superdense coding.", [
        _t("qc_tel_01", "Quantum Teleportation & Superdense Coding Protocols", "Intermediate", 5, ["qc_ent_01"], "Implement teleportation with classical feedforward.", ["Bell-basis measurement & Pauli corrections", "Why no-cloning & causality hold", "Superdense coding (2 classical bits per qubit)"]),
    ]),
    _c("qc_algos", "23. Quantum Algorithms", "Oracle models and query complexity.", [
        _t("qc_alg_01", "Phase Kickback & Quantum Oracle Construction", "Intermediate", 6, ["qc_circ_01", "qc_ent_01"], "Understand phase kickback as the engine of quantum algorithms.", ["Bit-flip vs phase-oracle encodings", "Phase kickback on CNOT & controlled-U", "Query complexity separations"]),
    ]),
    _c("qc_dj", "24. Deutsch-Jozsa Algorithm", "First exponential deterministic query separation.", [
        _t("qc_dj_01", "Deutsch, Deutsch-Jozsa & Bernstein-Vazirani Algorithms", "Intermediate", 5, ["qc_alg_01"], "Prove single-query balanced vs constant function detection.", ["Hadamard transform H^⊗n", "Deutsch-Jozsa interference cancellation", "Bernstein-Vazirani hidden bitstring recovery"]),
    ]),
    _c("qc_grover", "25. Grover's Algorithm", "Quadratic speedup for unstructured search.", [
        _t("qc_grov_01", "Amplitude Amplification & Grover Diffusion Operator", "Intermediate", 7, ["qc_alg_01"], "Derive optimal O(√N) iteration count geometrically.", ["Oracle reflection & inversion about the mean", "2D subspace rotation angle θ", "Multi-solution Grover & amplitude estimation"]),
    ]),
    _c("qc_shor", "26. Shor's Algorithm", "Exponential speedup for period finding and factoring.", [
        _t("qc_shor_01", "Order Finding, Modular Exponentiation & RSA Implications", "Advanced", 10, ["qc_disc_01", "qc_qft_01"], "Trace Shor's reduction from factoring to quantum phase estimation.", ["Classical reduction: factoring -> order finding", "Quantum order-finding circuit", "Continued fractions post-processing"]),
    ]),
    _c("qc_qft", "27. Quantum Fourier Transform", "Exponentially fast Fourier transform on amplitudes.", [
        _t("qc_qft_01", "QFT Circuit, Controlled Rotations & Phase Estimation (QPE)", "Advanced", 8, ["qc_cx_01", "qc_alg_01"], "Implement QFT and Quantum Phase Estimation.", ["QFT gate decomposition O(n²)", "Approximate QFT", "Quantum Phase Estimation (QPE) precision & ancillas"]),
    ]),
    _c("qc_qec", "28. Quantum Error Correction", "Protecting fragile quantum information redundantly.", [
        _t("qc_qec_01", "Shor 9-Qubit, Steane, Stabilizer Formalism & Surface Codes", "Advanced", 10, ["qc_ent_01", "qc_info_01"], "Detect bit-flip and phase-flip syndromes without collapsing logical states.", ["3-qubit bit-flip & phase-flip codes", "Pauli stabilizer groups & syndrome extraction", "Surface codes & fault-tolerant thresholds"]),
    ]),
    _c("qc_noise", "29. Noise and Decoherence", "Open quantum systems and error mitigation.", [
        _t("qc_noise_01", "Kraus Operators, Depolarizing Channels & Error Mitigation", "Advanced", 7, ["qc_st_01", "qc_qec_01"], "Model realistic hardware noise and apply mitigation.", ["Amplitude & phase damping channels", "Readout error mitigation & zero-noise extrapolation (ZNE)", "Randomized benchmarking"]),
    ]),
    _c("qc_hw", "30. Quantum Hardware", "Control electronics, cryogenics, and calibration.", [
        _t("qc_hw_01", "Transmons, Trapped Ions, Pulse Control & Cryogenics", "Advanced", 6, ["qc_qbt_01", "qc_noise_01"], "Understand hardware constraints shaping circuit compilation.", ["Microwave pulse shaping (DRAG) & cross-resonance", "Laser addressing in ion traps", "Dilution refrigerators & wiring bottlenecks"]),
    ]),
    _c("qc_frameworks", "31. Quantum Programming Frameworks", "Ecosystem SDKs and OpenQASM.", [
        _t("qc_fw_01", "OpenQASM 3, Cirq, PennyLane & Qiskit Architecture", "Intermediate", 5, ["qc_py_01", "qc_circ_01"], "Navigate modern quantum SDKs and intermediate representations.", ["OpenQASM 3 classical control flow", "PennyLane differentiable circuits", "Provider backends & job queues"]),
    ]),
    _c("qc_qiskit", "32. Qiskit and Equivalent Tools", "Hands-on circuit construction, transpilation, and primitives.", [
        _t("qc_qsk_01", "Qiskit Circuits, Sampler/Estimator Primitives & Transpiler", "Intermediate", 8, ["qc_fw_01"], "Build, transpile, and execute parameterized circuits in Qiskit.", ["QuantumCircuit & Parameter bindings", "SamplerV2 & EstimatorV2 primitives", "Transpiler pass managers & optimization levels"]),
    ]),
    _c("qc_sim", "33. Simulation", "Statevector, density-matrix, and tensor-network simulators.", [
        _t("qc_sim_01", "Statevector, Stabilizer (Clifford) & MPS Simulation", "Advanced", 6, ["qc_qsk_01", "qc_noise_01"], "Choose the right classical simulator for circuit structure.", ["Memory scaling 2^n for statevector", "Gottesman-Knill theorem for Clifford circuits", "Matrix Product States (MPS) for low entanglement"]),
    ]),
    _c("qc_comp", "34. Quantum Complexity", "BQP, QMA, and limits of quantum advantage.", [
        _t("qc_cmp_01", "BQP, QMA, Oracle Separations & Dequantization", "Advanced", 6, ["qc_cl_01", "qc_shor_01"], "Assess rigorously where quantum advantage is proven or conjectured.", ["BPP vs BQP vs NP relationships", "BBBV lower bound for unstructured search", "Quantum-inspired classical dequantization"]),
    ]),
    _c("qc_crypto", "35. Quantum Cryptography", "QKD and post-quantum cryptography.", [
        _t("qc_cry_01", "BB84, E91 QKD & NIST Post-Quantum Cryptography", "Advanced", 6, ["qc_tel_01", "qc_shor_01"], "Analyze quantum key distribution and lattice-based PQC.", ["BB84 eavesdropper detection", "E91 entanglement-based QKD", "ML-KEM / ML-DSA post-quantum transition"]),
    ]),
    _c("qc_nisq", "36. NISQ Computing", "Noisy Intermediate-Scale Quantum algorithms and limits.", [
        _t("qc_nisq_01", "NISQ Constraints, Barren Plateaus & Circuit Expressibility", "Advanced", 5, ["qc_noise_01", "qc_qsk_01"], "Design shallow circuits viable on current noisy devices.", ["Coherence-limited circuit depth", "Barren plateau gradient vanishing", "Hardware-efficient ansatz trade-offs"]),
    ]),
    _c("qc_vqa", "37. Variational Quantum Algorithms", "Hybrid quantum-classical optimization loops.", [
        _t("qc_vqa_01", "VQE, QAOA & Parameter-Shift Rule", "Advanced", 8, ["qc_calc_01", "qc_nisq_01"], "Implement VQE for ground-state energy and QAOA for Max-Cut.", ["Variational principle ⟨ψ(θ)|H|ψ(θ)⟩ ≥ E_0", "QAOA cost & mixer Hamiltonians", "Parameter-shift gradient rule"]),
    ]),
    _c("qc_papers", "38. Research Paper Reading", "Critical evaluation of arXiv quant-ph literature.", [
        _t("qc_pap_01", "Reading & Reproducing Quantum Computing Papers", "Advanced", 6, ["qc_cmp_01", "qc_vqa_01"], "Verify claims, assumptions, and resource estimates in papers.", ["Checking qubit/T-gate overhead & asymptotics", "Distinguishing heuristic vs proven speedups", "Reproducing figures in Qiskit/NumPy"]),
    ]),
    _c("qc_proj", "39. Practical Quantum Projects", "End-to-end implemented quantum software projects.", [
        _t("qc_prj_01", "Statevector Simulator + VQE/QAOA Benchmark Capstone", "Advanced", 14, ["qc_sim_01", "qc_vqa_01"], "Build a tested quantum simulator and noisy VQE benchmark.", ["From-scratch NumPy statevector simulator", "Qiskit noisy vs mitigated VQE comparison", "Reproducible benchmark report"]),
    ]),
    _c("qc_adv", "40. Advanced Research Topics", "Fault-tolerant compilation, qLDPC, and Hamiltonian simulation.", [
        _t("qc_adv_01", "Trotterization, Qubitization & qLDPC Error Correction", "Advanced", 8, ["qc_qec_01", "qc_pap_01"], "Explore frontier fault-tolerant algorithms and codes.", ["Lie-Trotter-Suzuki product formulas", "Block encoding & QSVT overview", "Quantum LDPC codes & constant-rate encoding"]),
    ]),
]


# ============================================================================
# C. ADDITIONAL VERIFIED ROLE CURRICULA (Technical + Government)
# ============================================================================

from backend.secondary_curricula import (
    AIML_CATEGORIES,
    BACKEND_CATEGORIES,
    CLOUD_CATEGORIES,
    CYBER_CATEGORIES,
    DATA_SCIENTIST_CATEGORIES,
    DEVOPS_CATEGORIES,
    FRONTEND_CATEGORIES,
    QUANT_DEV_CATEGORIES,
    SOFTWARE_ENGINEER_CATEGORIES,
    UPSC_IAS_CATEGORIES,
    UPSC_IPS_CATEGORIES,
)


# ============================================================================
# REGISTRY MAP & ROLE RESOLUTION
# ============================================================================

CURRICULUM_REGISTRY: Dict[str, Dict[str, Any]] = {
    "full_stack_developer": {
        "role_key": "full_stack_developer",
        "role_title": "Full Stack Developer",
        "description": "End-to-end web engineering spanning CS foundations, frontend UI/React, backend APIs, databases, cloud deployment, and system design.",
        "curriculum_version": CURRICULUM_VERSION,
        "authority_sources": [
            "ACM/IEEE-CS/AAAI CS2023 Curricula",
            "MDN Web Docs & W3C WCAG 2.1",
            "React, TypeScript, Node.js, FastAPI & PostgreSQL Official Documentation",
            "OWASP Top 10 & CNCF Cloud Native Guides",
        ],
        "categories": FULL_STACK_CATEGORIES,
    },
    "quantum_computing_engineer": {
        "role_key": "quantum_computing_engineer",
        "role_title": "Quantum Computing Engineer",
        "description": "Quantum information science, linear algebra, quantum mechanics, quantum algorithms, error correction, Qiskit simulation, and NISQ/VQA systems.",
        "curriculum_version": CURRICULUM_VERSION,
        "authority_sources": [
            "Nielsen & Chuang — Quantum Computation and Quantum Information",
            "IBM Qiskit Textbook & Official Qiskit Documentation",
            "MIT 8.370x / Preskill Quantum Computation Lecture Notes",
            "NIST Post-Quantum Cryptography Standards",
        ],
        "categories": QUANTUM_CATEGORIES,
    },
    "frontend_developer": {
        "role_key": "frontend_developer",
        "role_title": "Frontend Developer",
        "description": "Modern web UI engineering covering semantic HTML, CSS Grid/Flexbox, TypeScript, React architecture, accessibility, Core Web Vitals, and testing.",
        "curriculum_version": CURRICULUM_VERSION,
        "authority_sources": ["MDN Web Docs", "React Official Docs", "TypeScript Handbook", "web.dev Core Web Vitals"],
        "categories": FRONTEND_CATEGORIES,
    },
    "backend_developer": {
        "role_key": "backend_developer",
        "role_title": "Backend Developer",
        "description": "Server-side engineering across Linux, HTTP/REST/GraphQL, Node.js & FastAPI, PostgreSQL/MongoDB/Redis, security, queues, and distributed systems.",
        "curriculum_version": CURRICULUM_VERSION,
        "authority_sources": ["PostgreSQL Official Docs", "FastAPI & Node.js Official Docs", "OWASP API Security Top 10"],
        "categories": BACKEND_CATEGORIES,
    },
    "software_engineer": {
        "role_key": "software_engineer",
        "role_title": "Software Engineer",
        "description": "Core computer science, algorithms, OS/architecture, OOP & functional design, testing, CI/CD, distributed reliability, and system design.",
        "curriculum_version": CURRICULUM_VERSION,
        "authority_sources": ["ACM/IEEE-CS/AAAI CS2023", "PostgreSQL & Linux Kernel/OS References"],
        "categories": SOFTWARE_ENGINEER_CATEGORIES,
    },
    "ai_ml_engineer": {
        "role_key": "ai_ml_engineer",
        "role_title": "AI/ML Engineer",
        "description": "Mathematics for ML, classical modeling, PyTorch deep learning, Transformers, LLMs/RAG, fine-tuning, MLOps serving, and responsible AI.",
        "curriculum_version": CURRICULUM_VERSION,
        "authority_sources": ["PyTorch Official Tutorials", "scikit-learn User Guide", "Stanford CS229 / CS224N"],
        "categories": AIML_CATEGORIES,
    },
    "data_scientist": {
        "role_key": "data_scientist",
        "role_title": "Data Scientist",
        "description": "Statistical inference, A/B experimentation, causal analysis, SQL/Python wrangling, predictive modeling, time-series forecasting, and storytelling.",
        "curriculum_version": CURRICULUM_VERSION,
        "authority_sources": ["scikit-learn User Guide", "NIST/Duke Statistics & Experimentation Guides"],
        "categories": DATA_SCIENTIST_CATEGORIES,
    },
    "cybersecurity_engineer": {
        "role_key": "cybersecurity_engineer",
        "role_title": "Cybersecurity Engineer",
        "description": "Defensive security engineering across TCP/IP, Linux/Windows internals, cryptography, IAM, OWASP Top 10, SIEM/SOC, forensics, and cloud GRC.",
        "curriculum_version": CURRICULUM_VERSION,
        "authority_sources": ["OWASP Top 10", "NIST Cybersecurity Framework", "MITRE ATT&CK"],
        "categories": CYBER_CATEGORIES,
    },
    "cloud_engineer": {
        "role_key": "cloud_engineer",
        "role_title": "Cloud Engineer",
        "description": "Cloud architecture, VPC networking, compute/storage, IAM/KMS, Kubernetes, Terraform IaC, disaster recovery, and FinOps cost optimization.",
        "curriculum_version": CURRICULUM_VERSION,
        "authority_sources": ["AWS Well-Architected Framework", "CNCF Kubernetes Official Docs", "Terraform Official Docs"],
        "categories": CLOUD_CATEGORIES,
    },
    "devops_engineer": {
        "role_key": "devops_engineer",
        "role_title": "DevOps Engineer",
        "description": "Linux automation, GitOps CI/CD pipelines, Docker/Kubernetes, Terraform/Ansible, Prometheus/Grafana observability, SRE, and DevSecOps.",
        "curriculum_version": CURRICULUM_VERSION,
        "authority_sources": ["CNCF Kubernetes Official Docs", "Google SRE Book", "Terraform & Ansible Official Docs"],
        "categories": DEVOPS_CATEGORIES,
    },
    "quantitative_developer": {
        "role_key": "quantitative_developer",
        "role_title": "Quantitative Developer",
        "description": "Stochastic math, numerical optimization, modern C++, lock-free concurrency, low-latency Linux/networking, market microstructure, and backtesting.",
        "curriculum_version": CURRICULUM_VERSION,
        "authority_sources": ["C++ Core Guidelines", "MIT 18.S096 Mathematical Finance", "Numerical Recipes"],
        "categories": QUANT_DEV_CATEGORIES,
    },
    "ias": {
        "role_key": "ias",
        "role_title": "IAS",
        "description": "Official UPSC Civil Services Examination (CSE) pathway covering Prelims GS I & CSAT, Mains Essay & GS I–IV, Optional, and Personality Test.",
        "curriculum_version": CURRICULUM_VERSION,
        "authority_sources": ["UPSC Civil Services Examination Official Syllabus (2025-2026)", "NCERT Official Textbooks", "DARPG 2nd ARC"],
        "categories": UPSC_IAS_CATEGORIES,
    },
    "ips": {
        "role_key": "ips",
        "role_title": "IPS",
        "description": "Unified UPSC CSE Prelims & Mains preparation paired with IPS policing, internal security, criminal justice, physical standards, and leadership.",
        "curriculum_version": CURRICULUM_VERSION,
        "authority_sources": ["UPSC Civil Services Examination Official Syllabus (2025-2026)", "NCERT Official Textbooks", "MHA Internal Security Frameworks"],
        "categories": UPSC_IPS_CATEGORIES,
    },
}

ROLE_ALIASES: Dict[str, str] = {
    "full stack developer": "full_stack_developer",
    "fullstack developer": "full_stack_developer",
    "quantum computing engineer": "quantum_computing_engineer",
    "quantum engineer": "quantum_computing_engineer",
    "frontend developer": "frontend_developer",
    "backend developer": "backend_developer",
    "software engineer": "software_engineer",
    "ai/ml engineer": "ai_ml_engineer",
    "machine learning engineer": "ai_ml_engineer",
    "ai engineer": "ai_ml_engineer",
    "data scientist": "data_scientist",
    "cybersecurity engineer": "cybersecurity_engineer",
    "cloud engineer": "cloud_engineer",
    "devops engineer": "devops_engineer",
    "quantitative developer": "quantitative_developer",
    "ias": "ias",
    "ias / civil services": "ias",
    "ips": "ips",
    "ips / civil services": "ips",
}


def resolve_role_key(role_name: str) -> Optional[str]:
    clean = " ".join((role_name or "").strip().lower().split())
    if clean in ROLE_ALIASES:
        return ROLE_ALIASES[clean]
    if clean in CURRICULUM_REGISTRY:
        return clean
    return None


def list_verified_career_roles() -> List[str]:
    return [entry["role_title"] for entry in CURRICULUM_REGISTRY.values()]


def audit_curriculum_coverage(entry: Dict[str, Any]) -> Dict[str, Any]:
    categories = entry.get("categories") or []
    all_topic_ids_list = [
        t["topic_id"] for cat in categories for t in (cat.get("topics") or [])
    ]
    all_topic_ids = set(all_topic_ids_list)
    duplicate_ids = [
        tid for tid in all_topic_ids if all_topic_ids_list.count(tid) > 1
    ]
    total_topics = len(all_topic_ids_list)
    subtopic_count = sum(
        len(t.get("subtopics") or [])
        for cat in categories
        for t in (cat.get("topics") or [])
    )
    total_hours = sum(
        int(t.get("estimated_hours") or 0)
        for cat in categories
        for t in (cat.get("topics") or [])
    )
    missing_prereqs: List[str] = []
    missing_objectives: List[str] = []
    prereq_graph: Dict[str, List[str]] = {}
    for cat in categories:
        for t in cat.get("topics") or []:
            tid = t["topic_id"]
            if not str(t.get("learning_objective") or "").strip():
                missing_objectives.append(tid)
            prereqs = list(t.get("prerequisites") or [])
            prereq_graph[tid] = prereqs
            for pid in prereqs:
                if pid not in all_topic_ids:
                    missing_prereqs.append(f"{tid}->{pid}")

    # Detect circular dependencies via DFS coloring (0=unvisited, 1=visiting, 2=visited)
    color: Dict[str, int] = {}
    circular_deps: List[str] = []

    def _dfs(node: str) -> None:
        state = color.get(node, 0)
        if state == 1:
            circular_deps.append(node)
            return
        if state == 2:
            return
        color[node] = 1
        for dep in prereq_graph.get(node, []):
            if dep in prereq_graph:
                _dfs(dep)
        color[node] = 2

    for tid in all_topic_ids:
        if color.get(tid, 0) == 0:
            _dfs(tid)

    return {
        "category_count": len(categories),
        "topic_count": total_topics,
        "subtopic_count": subtopic_count,
        "total_estimated_hours": total_hours,
        "duplicate_topic_ids": duplicate_ids,
        "broken_prerequisite_refs": missing_prereqs,
        "circular_dependencies": circular_deps,
        "missing_objectives": missing_objectives,
        "prerequisites_valid": len(missing_prereqs) == 0 and len(circular_deps) == 0,
        "authority_sources": entry.get("authority_sources") or [],
    }


def get_verified_curriculum(role_name: str) -> Dict[str, Any]:
    role_key = resolve_role_key(role_name)
    if not role_key or role_key not in CURRICULUM_REGISTRY:
        return {
            "verified": False,
            "role_key": None,
            "role_title": role_name,
            "curriculum_version": CURRICULUM_VERSION,
            "unavailable_reason": (
                f"A verified, role-specific curriculum is not yet available for '{role_name}'. "
                f"Select one of the verified career roles to load its full curriculum."
            ),
            "supported_roles": list_verified_career_roles(),
            "categories": [],
        }

    entry = CURRICULUM_REGISTRY[role_key]
    return {
        "verified": True,
        "role_key": entry["role_key"],
        "role_title": entry["role_title"],
        "description": entry.get("description") or f"Complete {entry['role_title']} learning roadmap.",
        "curriculum_version": entry["curriculum_version"],
        "authority_sources": entry["authority_sources"],
        "coverage_audit": audit_curriculum_coverage(entry),
        "categories": entry["categories"],
    }
