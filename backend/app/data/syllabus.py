"""GATE 2027 syllabus (DA and CS) as structured content used for guides + RAG."""

SYLLABUS = {
    "DA": {
        "title": "GATE 2027 - Data Analytics / Data Science (DA)",
        "sections": [
            {
                "id": "da_prob_stats",
                "name": "Probability & Statistics",
                "topics": [
                    "Random variables, CDF/PDF/PMF",
                    "Expectation, variance, covariance, correlation",
                    "Common distributions (Bernoulli, Binomial, Poisson, Normal, Exponential)",
                    "Bayes theorem, conditional probability",
                    "Law of large numbers, central limit theorem",
                    "Hypothesis testing, confidence intervals",
                ],
                "guide": (
                    "Core quantitative foundation. Focus on distribution properties, "
                    "expectation identities, and hypothesis testing since these recur "
                    "across ML and EDA questions."
                ),
            },
            {
                "id": "da_linalg",
                "name": "Linear Algebra",
                "topics": [
                    "Vectors, matrices, transpose, rank",
                    "Eigenvalues and eigenvectors",
                    "Determinants, inverses",
                    "Singular Value Decomposition (SVD)",
                    "Systems of linear equations",
                ],
                "guide": (
                    "Linear algebra underpins PCA, regression and neural networks. "
                    "Be comfortable with eigen-decomposition and SVD intuitions."
                ),
            },
            {
                "id": "da_calc_opt",
                "name": "Calculus & Optimization",
                "topics": [
                    "Limits, continuity, differentiability",
                    "Partial derivatives, gradients",
                    "Convex/non-convex functions",
                    "Gradient descent, Lagrange multipliers",
                ],
                "guide": (
                    "Optimization is central to training models. Understand gradient "
                    "descent convergence and constrained optimization."
                ),
            },
            {
                "id": "da_prog_ds",
                "name": "Programming & Data Structures",
                "topics": [
                    "Python / C fundamentals",
                    "Arrays, lists, stacks, queues, trees, graphs",
                    "Recursion, complexity analysis",
                    "Pandas / NumPy basics",
                ],
                "guide": (
                    "Expect coding-snippet based questions and complexity estimation. "
                    "Practice with real Pandas operations."
                ),
            },
            {
                "id": "da_ml",
                "name": "Machine Learning",
                "topics": [
                    "Supervised learning: regression, classification",
                    "Bias-variance tradeoff, overfitting, regularization",
                    "Unsupervised: clustering (k-means), dimensionality reduction (PCA)",
                    "Model evaluation: confusion matrix, precision/recall, ROC-AUC",
                    "Cross-validation",
                ],
                "guide": (
                    "Highest weight section. Master evaluation metrics and the intuition "
                    "behind common algorithms rather than just APIs."
                ),
            },
            {
                "id": "da_ai_dl",
                "name": "AI & Deep Learning Basics",
                "topics": [
                    "Perceptron, activation functions",
                    "Feedforward networks, backpropagation",
                    "CNNs, RNNs (high level)",
                    "Loss functions, optimizers (SGD, Adam)",
                ],
                "guide": "Conceptual depth is usually tested; math-heavy derivations are rare.",
            },
            {
                "id": "da_db",
                "name": "Databases",
                "topics": [
                    "Relational model, SQL",
                    "Joins, aggregation, indexing",
                    "Normalization basics",
                ],
                "guide": "SQL query writing and join reasoning are common in DA paper.",
            },
            {
                "id": "da_aptitude",
                "name": "General Aptitude",
                "topics": [
                    "Verbal analogy, grammar, vocabulary",
                    "Logical reasoning, sets, Venn diagrams",
                    "Numerical ability, percentages, ratios",
                ],
                "guide": "GA carries 15 marks in GATE DA. Quick, scoring questions — practice verbal and numerical ability.",
            },
        ],
    },
    "CS": {
        "title": "GATE 2027 - Computer Science & Information Technology (CS)",
        "sections": [
            {
                "id": "cs_discrete",
                "name": "Discrete Mathematics",
                "topics": [
                    "Propositional & first-order logic",
                    "Sets, relations, functions",
                    "Graph theory, combinatorics",
                    "Generating functions, recurrence relations",
                ],
                "guide": "Foundational and frequently mixed into other sections. Practice proof-free application.",
            },
            {
                "id": "cs_linalg",
                "name": "Linear Algebra & Calculus",
                "topics": [
                    "Matrices, determinants, eigenvalues",
                    "Limits, continuity, differentiation",
                    "Maxima/minima",
                ],
                "guide": "Small but predictable marks. Memorize standard results.",
            },
            {
                "id": "cs_prob",
                "name": "Probability & Statistics",
                "topics": [
                    "Random variables, distributions",
                    "Mean, median, mode, standard deviation",
                    "Conditional probability, Bayes theorem",
                ],
                "guide": "Straightforward if you practice distribution manipulation.",
            },
            {
                "id": "cs_ds_algo",
                "name": "Data Structures & Algorithms",
                "topics": [
                    "Arrays, linked lists, trees, graphs, heaps",
                    "Sorting, searching, hashing",
                    "Asymptotic notation, recursion",
                    "Greedy, divide & conquer, DP",
                ],
                "guide": "High weight. Be fluent in time/space complexity and DP patterns.",
            },
            {
                "id": "cs_toc",
                "name": "Theory of Computation",
                "topics": [
                    "Finite automata, regular languages",
                    "Context-free grammars, pushdown automata",
                    "Turing machines, decidability",
                ],
                "guide": "Learn closure properties and reduction-based decidability proofs.",
            },
            {
                "id": "cs_os",
                "name": "Operating Systems",
                "topics": [
                    "Processes, threads, concurrency",
                    "Scheduling, synchronization, deadlocks",
                    "Memory management, paging, virtual memory",
                    "File systems",
                ],
                "guide": "Very scoring. Numerical on paging/disk scheduling are common.",
            },
            {
                "id": "cs_db",
                "name": "Databases",
                "topics": [
                    "ER model, relational algebra",
                    "SQL, normalization (1NF-BCNF)",
                    "Transactions, concurrency control",
                ],
                "guide": "Normalization and transaction isolation levels are favorites.",
            },
            {
                "id": "cs_networks",
                "name": "Computer Networks",
                "topics": [
                    "OSI/TCP-IP layering",
                    "IP, routing, DNS, HTTP",
                    "Congestion control, sliding window",
                ],
                "guide": "Memorize protocol details and numeric examples (subnetting).",
            },
            {
                "id": "cs_compiler",
                "name": "Compiler Design",
                "topics": [
                    "Lexical analysis, parsing",
                    "LL/LR parsers, syntax-directed translation",
                    "Run-time environments",
                ],
                "guide": "Focus on parsing table construction and First/Follow sets.",
            },
            {
                "id": "cs_coa",
                "name": "Computer Organization & Architecture",
                "topics": [
                    "Number systems, cache memory, pipelining",
                    "Addressing modes, control unit, I/O",
                    "Instruction formats, hazards, performance",
                ],
                "guide": "Cache/pipeline numericals are high-yield. Memorize AMAT and speedup formulas.",
            },
            {
                "id": "cs_digital_logic",
                "name": "Digital Logic",
                "topics": [
                    "Boolean algebra, K-maps, minimization",
                    "Combinational circuits: mux, decoder, adders",
                    "Sequential circuits: latches, flip-flops, counters",
                ],
                "guide": "K-map grouping and flip-flop excitation tables cover most questions.",
            },
            {
                "id": "cs_aptitude",
                "name": "General Aptitude (GA)",
                "topics": [
                    "Verbal ability: grammar, vocabulary, sentence completion",
                    "Numerical ability: speed, time, work, averages, sequences",
                    "Logical reasoning and data interpretation",
                ],
                "guide": "15 marks in GATE. Quick, scoring questions — practice previous-year GA sets.",
            },
        ],
    },
}


def get_sections(paper: str) -> list[dict]:
    return SYLLABUS.get(paper, {}).get("sections", [])


# Concise study notes per section (shown in the guide + used for RAG context).
SECTION_NOTES = {
    "da_prob_stats": "Master distributions, expectation identities, and CLT. Most DA ML questions reduce to a probability or stats computation — practice converting word problems into P(X) statements.",
    "da_linalg": "Eigen-decomposition and SVD are the backbone of PCA and word embeddings. Know properties: det(A^T)=det(A), eigenvalues of A^k are lambda^k, symmetric => orthogonal diagonalization.",
    "da_calc_opt": "Gradient descent = move opposite the gradient. Recognize convex vs non-convex; Lagrange multipliers appear in constrained ML problems.",
    "da_prog_ds": "Be fluent in Big-O and recursion. Pandas/NumPy operations (groupby, merge, vectorization) are frequently tested — avoid hidden O(n^2) loops.",
    "da_ml": "Memorize metric formulas (precision/recall/F1, ROC-AUC). Bias-variance and regularization (L1/L2) explain most 'why' questions. Cross-validation estimates generalization.",
    "da_ai_dl": "Understand backprop (chain rule) and activation roles. CNNs for grids, RNNs for sequences; optimizers (SGD/Adam) differ in adaptive learning rates.",
    "da_db": "SQL joins and aggregations are the most common DA coding questions. Know LEFT vs INNER, GROUP BY, and COUNT(*) vs COUNT(col).",
    "cs_discrete": "Propositional logic, counting, and graph basics appear everywhere. Practice contrapositives, pigeonhole, and tree/graph edge counts (tree: n-1, K_n: n(n-1)/2).",
    "cs_linalg": "Small but free marks: eigenvalues of triangular matrices are diagonal entries; derivative/power rules. Don't skip.",
    "cs_prob": "Expectation and variance of simple RVs; Bayes theorem. Var(constant)=0, Var(X+Y)=Var(X)+Var(Y) when independent.",
    "cs_ds_algo": "Highest weight. Know complexities cold: merge sort O(n log n)/space O(n), binary search O(log n), balanced BST O(log n). DP = overlapping subproblems.",
    "cs_toc": "Closure properties and reductions. Regular < CFL < recursive. Halting problem undecidable; {a^n b^n} is CFL not regular.",
    "cs_os": "Practise paging numeric (page table size, TLB), scheduling (starvation in priority), and sync (race conditions, locks). Demand paging loads on fault.",
    "cs_db": "Normalization (1NF->BCNF removes transitive deps), transaction isolation/serializability via locking. ER -> relational mapping.",
    "cs_networks": "Layer 3 routing, TCP reliable over IP, HTTP over TCP. Drill subnetting and sliding-window numbers.",
    "cs_compiler": "Lexer->tokens, parser (LL/LR tables, FIRST/FOLLOW), semantic analysis. LR uses ACTION/GOTO tables + stack.",
    "cs_coa": "Cache (AMAT = hit + miss-rate x penalty), 5-stage pipeline, addressing modes. Number-system conversions are free marks.",
    "cs_digital_logic": "Boolean minimization via K-maps, mux/decoder/adders for combinational; SR/JK/D/T flip-flops, excitation tables, counters for sequential.",
    "cs_aptitude": "Verbal + numerical ability. Grammar rules (subject-verb agreement), vocab, and fast arithmetic (speed/distance, averages, sequences). These are the easiest 15 marks in GATE.",
}


for _paper in SYLLABUS.values():
    for _sec in _paper["sections"]:
        _sec["notes"] = SECTION_NOTES.get(_sec["id"], "")
