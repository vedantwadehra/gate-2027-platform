"""Parse GATE DA PYQ PDFs (2024+ format: "Q. N ... (A)-(D)" + separate answer-key PDF).

Usage: python3 parse_da_pyq.py <qp.pdf> <keys.pdf> [--json out.json]

Extracts only single-correct MCQs (skips NAT and MSQ, including MSQ items
whose official key happens to be a single letter). Body blocks and key rows
are joined on question NUMBER (not document order) so MSQ/NAT never cause
misalignment. Figure/diagram-dependent questions are skipped. Each question
is mapped to a DA syllabus section via keyword scoring; GA-section questions
go to da_aptitude. Unmapped questions are reported, never silently misfiled.
"""
import sys
import re
import json
import PyPDF2

LETTER_IDX = {"A": 0, "B": 1, "C": 2, "D": 3}

LIGATURES = {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl",
             "\ufb03": "ffi", "\ufb04": "ffl", "\ufb05": "st", "\ufb06": "st"}

# Single-codepoint glyph substitutions, each verified in context across the
# DA 2024-2026 PDFs (× in "n×n", θ as Bernoulli parameter, ≤/≥ in CDFs,
# π/σ as relational-algebra operators, * in "A* algorithm").
GLYPH_MAP = {"\x02": "×", "\x03": "*", "\x12": "θ", "\x14": "≤",
             "\x15": "≥", "\x19": "π", "\x1b": "σ"}


def normalize(txt: str) -> str:
    for lig, rep in LIGATURES.items():
        txt = txt.replace(lig, rep)
    for glo, rep in GLYPH_MAP.items():
        txt = txt.replace(glo, rep)
    txt = txt.replace("\xa0", " ")
    # Decimal points extracted as colons ("0:25" -> "0.25").
    txt = re.sub(r"(?<=\d):(?=\d)", ".", txt)
    # Membership/set-power pattern ("A2Rn" -> "A∈R^n").
    txt = re.sub(r"([A-Za-z])2Rn", r"\1∈R^n", txt)
    # Stray backslashes before quotes in relational-algebra expressions.
    txt = txt.replace('\\"', '"')
    # Opening quotes extracted as backslashes ("=\\red" -> '="red"').
    return txt.replace("=\\", '="')

# Page furniture stripped before splitting into question blocks.
FURNITURE_RES = [
    r"Organizing Institute.*",
    r"Page \d+ of \d+",
    r"Data Science.*Artificial Intelligence.*",
    r"General Aptitude\s*\(GA\)",
    r"^GA$",
    r"Q\.?\s*\d+\s*[–\-]\s*Q\.?\s*\d+\s*Carry.*marks?.*",
    r"Carry ONE mark.*",
    r"Carry TWO marks?.*",
    r"END OF.*QUESTION PAPER.*",
    r"SPACE FOR ROUGH WORK.*",
    r"^Rough Work.*",
    r"^GATE \d{4}.*",
]

# Visual-content references: question not answerable from extracted text.
# (Bare "image"/"picture" deliberately excluded: ML questions about image
# data are text-answerable; "graph" is handled via the theory exception.)
FIGURE_RE = re.compile(
    r"fig\.|figure|diagram|histogram|scatter|bar chart|pie chart|box plot"
    r"|as shown|shown below|shown in|shown above|following figure"
    r"|plot\b|plots\b",
    re.I,
)
# "... graph ..." is visual UNLESS it reads as graph theory.
GRAPH_THEORY_RE = re.compile(
    r"vert|edges?|nodes?|adjacency|connected|tree|traversal|bipartite|degree of|cycle",
    re.I,
)

SECTION_KEYWORDS = {
    "da_ai_dl": ["neural", "perceptron", "backprop", "cnn", "convolutional", "rnn",
                 "recurrent", "lstm", "gru", "transformer", "attention", "deep learning",
                 "autoencoder", "gan ", "generative adversarial", "dropout", "batch norm",
                 "embedding", "sigmoid", "relu", "softmax", "activation function",
                 "proposition", "predicate", "tautolog", "satisfiab", "entailment",
                 "knowledge representation", "admissible", "heuristic", "a* search",
                 "alpha-beta", "alpha–beta", "minimax", "game tree", "adversarial search",
                 "informed search", "logic"],
    "da_ml": ["regression", "classification", "clustering", "k-means", "kmeans",
              "svm", "support vector", "decision tree", "random forest", "overfit",
              "underfit", "bias-variance", "bias variance", "cross-validation",
              "cross validation", "precision", "recall", "f1", "roc", "auc",
              "loss function", "regularization", "ridge", "lasso", "elastic net",
              "naive bayes", "ensemble", "boosting", "bagging", "dimensionality",
              "pca", "principal component", "feature selection", "k-nn", "knn",
              "logistic regression", "hyperparameter", "confusion matrix",
              "classifier",
              "discriminant", "scatter matrix", "scatter matrices", "within-class",
              "between-class", "within class", "between class", "fisher", "lda"],
    "da_prob_stats": ["probability", "random variable", "distribution", "variance",
                      "expectation", "covariance", "bayes theorem", "bayes'",
                      "likelihood", "maximum likelihood", "mle", "gaussian", "normal ",
                      "poisson", "bernoulli", "binomial", "exponential", "uniformly",
                      "standard deviation", "correlation", "conditional probability",
                      "central limit", "law of large", "hypothesis", "p-value",
                      "p value", "confidence interval", "sampling", "estimator",
                      "unbiased", "markov", "chebyshev", "joint distribution",
                      "marginal", "posterior", "prior distribution", "entropy",
                      "expected", "pmf", "cdf", "moment"],
    "da_linalg": ["matrix", "matrices", "eigen", "determinant", "vector space",
                  "rank of", "rank ", "svd", "singular value", "orthogonal",
                  "orthonormal", "linear transformation", "linearly independent",
                  "linearly dependent", "span ", "basis", "null space", "column space",
                  "projection", "symmetric matrix", "positive definite",
                  "positive semi", "trace of", "diagonaliz", "linear system",
                  "system of linear", "subspace", "dimension", "stochastic"],
    "da_calc_opt": ["derivative", "gradient", "integral", "convex", "concave",
                    "minima", "maxima", "minimum of", "maximum of", "lagrange",
                    "hessian", "jacobian", "chain rule", "optimiz", "optimum",
                    "optimal ", "learning rate", "limit ", "continuous",
                    "differentiab", "taylor", "stationary point", "saddle point",
                    "descent", "convex function", "second derivative",
                    "local min", "global min", "local max", "global max",
                    "critical point", "necessary", "sufficient"],
    "da_db": ["sql", "database", "relation", "tuple", "normalization", "normal form",
              "bcnf", "3nf", "2nf", "1nf", "transaction", "acid", "indexing",
              "primary key", "foreign key", " join", "joins", "query", "schema",
              "er model", "er diagram", "entity-relationship", "serializab",
              "functional dependenc", "multivalued", "view ", "trigger",
              "data cube", "data warehouse", "warehousing", "olap", "cuboid",
              "roll-up", "roll up", "drill-down", "drill down", "slice and dice",
              "star schema", "snowflake", "etl", "fact table", "dimension table"],
    "da_prog_ds": ["python", "def ", "print(", "code", "program", "algorithm",
                   "complexity", "big-o", "big o", "o(n", "o(log", "binary tree",
                   "bst", "heap", "stack", "queue", "linked list", "hash",
                   "sorting", "sorted", "recurrence", "dynamic programming",
                   "greedy", "divide and conquer", "recursion", "recursive",
                   "array", "linkedlist", "function ", "returns", "loop",
                   "traversal", "stable sort", "quicksort", "mergesort",
                   "dfs", "bfs", "dijkstra", "shortest path", "graph",
                   "topological", "spanning tree", "bellman-ford"],
}

# Hand-reviewed section overrides {(year, qnum): section}.
SECTION_OVERRIDES = {
    (2026, 45): "da_prob_stats",  # Poisson-pmf limit; no scorable keyword
    (2026, 38): "da_ai_dl",       # propositional logic; formula-only stem
    (2025, 13): "da_linalg",      # row-stochastic matrix; symbol-heavy stem
    (2025, 22): "da_ml",          # perceptron update; beats generic code words
    (2025, 44): "da_ai_dl",       # A* state graph; beats graph/queue words
}

# Per-question repairs, each verified against the official paper. Applied to
# stem + options text (TEXT_FIXUPS) or replacing options wholesale
# (OPTIONS_OVERRIDE) when the extractor mangles them.
TEXT_FIXUPS = {
    # 0x15 renders as ≥ in most fonts but as λ here ("E[X] = 1/λ ...
    # what is the value of λ?").
    (2025, 21): [("=1 ≥,", "=1/λ,"), ("value of ≥?", "value of λ?")],
    # Commas in the expected list extracted as semicolons.
    (2025, 23): [("A= [1;2;3;4;5;6]", "A = [1,2,3,4,5,6]")],
}
OPTIONS_OVERRIDE = {
    # "(B)" inside "A.extend(B)" etc. breaks marker segmentation; the
    # official options are A.extend(B) / A.append(B) / A.update(B) /
    # A.insert(B), key (A).
    (2025, 23): ["A.extend(B)", "A.append(B)", "A.update(B)", "A.insert(B)"],
}

# Key-MCQs whose options are destroyed in text extraction (math/figures
# lost); excluded rather than banked as garbage.
EXCLUDE = {
    (2025, 45),  # options C/D garbled beyond recovery
    (2025, 13),  # stem operators ambiguous (lost minus / ∈ / powers)
    (2025, 15),  # propositional operators mangled (!, ::, _)
    (2025, 19),  # piecewise CDF definition destroyed
    (2025, 36),  # standardization expression lost
    (2025, 38),  # set braces / ≠ ambiguous
    (2025, 40),  # summation / Φ definition / minus signs lost
    (2025, 41),  # floor brackets / slashes / powers lost
}


def guess_section(text: str) -> str | None:
    t = text.lower()
    best, best_score = None, 0
    for sec, kws in SECTION_KEYWORDS.items():
        score = sum(t.count(k) for k in kws)
        if score > best_score:
            best, best_score = sec, score
    return best


def extract_text(path: str) -> str:
    r = PyPDF2.PdfReader(path)
    return normalize("\n".join((p.extract_text() or "") for p in r.pages))


def clean_block(block: str) -> str:
    lines = []
    for ln in block.splitlines():
        s = ln.strip()
        if not s:
            continue
        if any(re.search(pat, s, re.I) for pat in FURNITURE_RES):
            continue
        lines.append(s)
    return re.sub(r"\s+", " ", " ".join(lines)).replace("\x00", "").strip()


def get_body_blocks(txt: str) -> dict[int, str]:
    """Map question number -> cleaned block text for Q.1..Q.65."""
    # Strip furniture lines first so section headers ("Q.1 – Q.5 Carry ...")
    # never create phantom question markers.
    kept = []
    for ln in txt.splitlines():
        s = ln.strip()
        if s and any(re.search(pat, s, re.I) for pat in FURNITURE_RES):
            continue
        kept.append(ln)
    txt2 = "\n".join(kept)
    # Mandatory period after Q: table cells like "P1 Q1 R1" must not split.
    parts = re.split(r"Q\.\s*(\d+)\b", txt2)
    # parts: [pre, num, block, num, block, ...]
    # The extractor sometimes duplicates a page; keep the longest block
    # per question number (a truncated duplicate never wins).
    out: dict[int, str] = {}
    for i in range(1, len(parts) - 1, 2):
        try:
            num = int(parts[i])
        except ValueError:
            continue
        if not 1 <= num <= 65:
            continue
        cleaned = clean_block(parts[i + 1])
        if not cleaned:
            continue
        if num in out and len(cleaned) <= len(out[num]):
            continue
        out[num] = cleaned
    return out


def split_options(block: str):
    """Return (stem, [A,B,C,D]) or None. Uses the FIRST (A), then the first
    (B) after it, etc. — option text itself may contain parenthesised
    capitals (e.g. ``A.extend(B)``), so exact marker-set matching is too
    strict. Anything after (D) belongs to option D."""
    marks = [(m.start(), m.end(), m.group(1))
             for m in re.finditer(r"\(\s*([A-D])\s*\)", block)]
    seq, idx = [], 0
    for want in "ABCD":
        nxt = next((j for j in range(idx, len(marks)) if marks[j][2] == want), None)
        if nxt is None:
            return None
        seq.append(marks[nxt])
        idx = nxt + 1
    (a0, a1, _), (b0, b1, _), (c0, c1, _), (d0, d1, _) = seq
    stem = block[:a0].strip()
    opts = [block[a1:b0].strip(), block[b1:c0].strip(),
            block[c1:d0].strip(), block[d1:].strip()]
    if not stem or any(not o for o in opts):
        return None
    if len(stem) > 2000 or any(len(o) > 800 for o in opts):
        return None  # likely a mis-split; stay conservative
    return stem, [re.sub(r"\s+", " ", o).strip() for o in opts]


def get_mcq_keys(txt: str) -> dict[int, tuple[str, str, int]]:
    """Map question number -> (section 'GA'/'DA', answer letter, marks)."""
    out: dict[int, tuple[str, str, int]] = {}
    for m in re.finditer(
        r"(\d+)\s+(?:\d+\s+)?MCQ\s+(GA|DA)\s+([A-D])\s+(\d+)", txt, re.I
    ):
        qnum, sec, letter, marks = int(m.group(1)), m.group(2).upper(), m.group(3).upper(), int(m.group(4))
        if 1 <= qnum <= 65 and qnum not in out:
            out[qnum] = (sec, letter, marks)
    return out


def has_visual(block: str) -> bool:
    if not FIGURE_RE.search(block):
        return False
    # "graph" as graph theory is fine.
    if re.search(r"\bgraph\b", block, re.I) and GRAPH_THEORY_RE.search(block):
        tmp = re.sub(r"\bgraph\b", "", block, flags=re.I)
        return bool(FIGURE_RE.search(tmp))
    return True


def parse_paper(qp_path: str, keys_path: str, year: int):
    body = get_body_blocks(extract_text(qp_path))
    keys = get_mcq_keys(extract_text(keys_path))
    results, skipped_fig, unmapped = [], [], []
    for qnum in sorted(keys):
        sec, letter, marks = keys[qnum]
        if (year, qnum) in EXCLUDE:
            continue
        block = body.get(qnum, "")
        if not block:
            print(f"  [warn] {year} Q.{qnum}: no body block", file=sys.stderr)
            continue
        parsed = split_options(block)
        if parsed is None:
            continue  # NAT/structure without A-D options
        stem, opts = parsed
        for old, new in TEXT_FIXUPS.get((year, qnum), []):
            stem = stem.replace(old, new)
            opts = [o.replace(old, new) for o in opts]
        if (year, qnum) in OPTIONS_OVERRIDE:
            opts = list(OPTIONS_OVERRIDE[(year, qnum)])
        if has_visual(stem + " " + " ".join(opts)):
            skipped_fig.append(qnum)
            continue
        if sec == "GA":
            section = "da_aptitude"
        elif (year, qnum) in SECTION_OVERRIDES:
            section = SECTION_OVERRIDES[(year, qnum)]
        else:
            section = guess_section(stem + " " + " ".join(opts))
            if section is None:
                unmapped.append(qnum)
                continue
        results.append({
            "id": f"da_pyq_{year}_{qnum:02d}",
            "section": section,
            "text": stem,
            "options": opts,
            "answer": LETTER_IDX[letter],
            "explanation": (
                f"GATE DA {year} · Q.{qnum} · {marks} mark{'s' if marks != 1 else ''}. "
                f"Official key: ({letter})."
            ),
            "source": f"GATE DA {year} (official paper)",
            "verified": True,
            "year": year,
            "qnum": qnum,
        })
    return results, skipped_fig, unmapped


if __name__ == "__main__":
    qp, kp = sys.argv[1], sys.argv[2]
    year = int(re.search(r"(19|20)\d{2}", qp).group(0))
    res, skipped_fig, unmapped = parse_paper(qp, kp, year)
    print(f"year={year} mcqs={len(res)} skipped_fig={skipped_fig} unmapped={unmapped}")
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        json.dump(res, open(out, "w"), indent=2)
        print(f"wrote {len(res)} MCQs to {out}")
    else:
        for r in res[:2]:
            print("---", r["id"], r["section"], "ans=", r["answer"])
            print(r["text"][:160])
