"""Extract + classify test-series questions (GO Classes, MadeEasy) for bank import.

Usage:
  python3 parse_test_series.py go [--json out.json]
  python3 parse_test_series.py madeeasy [--json out.json] [--limit N]

Classification: every question gets (paper, subject). Shared-foundation
subjects (ds_algo, prog, linalg, prob, db, aptitude, calc) dual-bank to both
papers; specialised subjects go to one paper only. MSQ/NAT are classified
(mapping output) but never emitted for import — the bank schema is MCQ-only.
Only fully-text MCQs with a verifiable single correct answer are importable;
cards/questions containing images are mapping-only.
"""
import sys
import os
import re
import json
import html as htmlmod

GO_DIR = "/Users/vedantwadehra/Desktop/GATE PREP/GO_Classes_Test_Series (1)"
ME_DIR = "/Users/vedantwadehra/Desktop/GATE PREP/GATE CS TEST SERIES"

LETTER_IDX = {"A": 0, "B": 1, "C": 2, "D": 3}

# subject -> ({papers}, {paper: section})
SUBJECTS = {
    "toc": (("CS",), {"CS": "cs_toc"}),
    "os": (("CS",), {"CS": "cs_os"}),
    "networks": (("CS",), {"CS": "cs_networks"}),
    "compiler": (("CS",), {"CS": "cs_compiler"}),
    "coa": (("CS",), {"CS": "cs_coa"}),
    "digital": (("CS",), {"CS": "cs_digital_logic"}),
    "discrete": (("CS",), {"CS": "cs_discrete"}),
    "ml": (("DA",), {"DA": "da_ml"}),
    "ai_dl": (("DA",), {"DA": "da_ai_dl"}),
    "db": (("DA", "CS"), {"DA": "da_db", "CS": "cs_db"}),
    "ds_algo": (("DA", "CS"), {"DA": "da_prog_ds", "CS": "cs_ds_algo"}),
    "prog": (("DA", "CS"), {"DA": "da_prog_ds", "CS": "cs_ds_algo"}),
    "linalg": (("DA", "CS"), {"DA": "da_linalg", "CS": "cs_linalg"}),
    "calc": (("DA", "CS"), {"DA": "da_calc_opt", "CS": "cs_linalg"}),
    "prob": (("DA", "CS"), {"DA": "da_prob_stats", "CS": "cs_prob"}),
    "aptitude": (("DA", "CS"), {"DA": "da_aptitude", "CS": "cs_aptitude"}),
}

# filename fragment -> subject prior (MadeEasy subjectwise/topicwise)
ME_FILE_SUBJECT = [
    ("theory_of_computation", "toc"),
    ("algorithms", "ds_algo"),
    ("computer_organization", "coa"),
    ("operating_system", "os"),
    ("engineering_mathematics", None),  # split by keywords
    ("general_aptitude", "aptitude"),
    ("database", "db"),
    ("programming_and", "prog"),
    ("computer_networks", "networks"),
    ("digital_logic", "digital"),
    ("compiler_design", "compiler"),
    ("discrete_mathematics", "discrete"),
]

# keyword -> subject (checked in order; first hit wins for priors, scored otherwise)
SUBJECT_KEYWORDS = {
    "toc": ["finite automata", "dfa", "nfa", "regular language", "regular expression",
            "context-free", "context free", "pushdown", "pda", "turing", "decidab",
            "recursively enumerable", "grammar", "pumping lemma", "chomsky",
            "quotient", "homomorphism", "transducer", "recursive ", "undecidable",
            "semi-decidable", "multi-tape", "two-way", "finite control"],
    "os": ["semaphore", "mutex", "deadlock", "paging", "page fault", "scheduling",
           "process ", "thread", "virtual memory", "fork(", "demand paging",
           "belady", "thrashing", "inode", "system call", "concurrency", "race condition"],
    "networks": ["tcp", "udp", "ip address", "subnet", "routing", "ethernet", "mac address",
                 "http", "dns", "osi model", "congestion", "flow control", "csma", "aloha",
                 "packet switching", "circuit switching", "cidr", "address resolution", "icmp",
                 "computer network", "protocol", "packets"],
    "compiler": ["lexical", "parser", "parsing", "syntax directed", "three address",
                 "intermediate code", "code generation", "code optimization", "token",
                 "lr(", "ll(", "slr", "lalr", "yacc", "dfa",
                 "activation record", "symbol table"],
    "coa": ["cache", "pipeline", "speedup", "addressing mode", "microprogram",
            "control unit", "datapath", "hazard", "branch predictor",
            "tomasulo", "cache coherence", "memory hierarchy", "tlb", " hit ", "miss rate",
            "cpi ", "mips", "endianness", "overflow flag", " booth", "restoring division",
            "register", "isa ", "floating point", "ieee", "mantissa", "exponent",
            "normalized", "denormal", "single precision", "double precision",
            "half precision", "bias", "complement", "signed integer", "unsigned",
            "overflow", "underflow", "fixed point", "binary representation",
            "hexadecimal", "octal", "gray code", "excess-3", "bcd"],
    "digital": ["flip-flop", "flip flop", "latch", "multiplexer", "mux", "decoder",
                "encoder", "k-map", "karnaugh", "boolean function", "logic gate",
                "nand", "nor gate", "xor", "half adder", "full adder", "counter",
                "shift register", "state diagram", "moore ", "mealy", "minterm", "maxterm",
                "circuit", "quine", "prime implicant", "essential prime", "don't care",
                "master-slave", "ripple", "synchronous", "asynchronous"],
    "discrete": ["proposition", "propositional", "predicate", "tautology", "contradiction",
                 "truth value", "truth table", "logical equivalence",
                 "→", "↔", "∼", "∧", "∨", "¬", "⊕",
                 "graph ", "vertex", "vertices", "edge", "euler", "hamiltonian", "chromatic",
                 "permutation", "combination", "pigeonhole", "recurrence relation",
                 "generating function", "poset", "lattice", "group ", "subgroup",
                 "coset", "boolean algebra", "sets", "relation", "equivalence class",
                 "partial order", "trees", "spanning tree", "cartesian",
                 "composite function", "one-to-one", "onto", "bijective", "injective",
                 "surjective", "inverse function", "mapping", "indistinguishable",
                 "distinguishable", "stars and bars", "ways are there", "distribute",
                 "power set", "subset", "vowels", "consonants", "in how many ways",
                 "number of ways", "can be formed", "boolean", "converse",
                 "contrapositive", "mod ", "modulo", "congruence"],
    "ml": ["regression", "classification", "clustering", "k-means", "svm",
           "decision tree", "random forest", "overfit", "bias-variance", "cross-validation",
           "precision", "recall", "f1", "roc curve", "loss function", "regularization",
           "ridge", "lasso", "naive bayes", "ensemble", "pca", "classifier",
           "hyperparameter", "confusion matrix", "discriminant", "likelihood",
           "gradient descent", "stochastic"],
    "ai_dl": ["neural", "perceptron", "backprop", "cnn", "rnn", "lstm", "transformer",
              "self-attention", "attention mechanism", "attention weights",
              "multi-head", "query-key", "deep learning", "autoencoder", "dropout", "activation function",
              "admissible", "heuristic", "minimax", "alpha-beta", "game tree",
              "a* search", "informed search", "knowledge representation"],
    "db": ["sql", "database", "relation", "tuple", "normalization", "normal form",
           "bcnf", "transaction", "acid", "indexing", "primary key", "foreign key",
           " join", "query", "schema", "er model", "serializab", "functional dependenc",
           "data cube", "olap", "warehouse", "select ", "columns", "where clause",
           "order by", "group by", "having clause", "distinct", "like operator"],
    "ds_algo": ["algorithm", "complexity", "big-o", "big o", "o(n", "binary search",
                "linear search", "sequential search", "search algorithm",
                "sorting", "sort", "sorted", "heap", "bst", "avl", "linked list", "stack",
                "queue", "hash", "binary tree", "search tree", "tree traversal",
                "travers", "dynamic programming", "greedy", "recurrence", "master theorem",
                "asymptotic", "divide and conquer", "bfs", "dfs", "dijkstra",
                "shortest path", "minimum spanning", "prim", "kruskal",
                "bellman", "topological", "graph traversal", "pattern matching", "kmp",
                "comparisons"],
    "prog": ["python", "def ", "print(", "program", "code", "c program", "#include",
             "pointer", "malloc", "recursion", "recursive", "function ", "returns",
             "array", "string", "struct", "typedef", "scanf", "printf", "loop",
             "variable", "scope", "parameter passing", "call by"],
    "linalg": ["matrix", "matrices", "eigen", "determinant", "vector", "rank",
               "svd", "singular value", "orthogonal", "linear ", "span", "basis",
               "null space", "projection", "symmetric", "positive definite", "trace",
               "diagonaliz", "system of linear", "subspace", "dimension"],
    "calc": ["derivative", "integral", "convex", "concave", "minima", "maxima",
             "lagrange", "hessian", "chain rule", "optimiz", "limit", "continuity",
             "differentiab", "taylor", "critical point", "saddle", "descent",
             "local min", "global min", "local max", "global max",
             "greatest value", "least value", "necessary", "sufficient"],
    "prob": ["probability", "random variable", "distribution", "variance",
             "expectation", "expected", "covariance", "bayes", "gaussian", "normal ",
             "poisson", "bernoulli", "binomial", "exponential", "standard deviation",
             "correlation", "conditional probability", "hypothesis", "sampling",
             "estimator", "markov", "pmf", "cdf", "moment", "die ", "dice", "coin",
             "toss", "deck", "urn", "balls", "drawn", "with replacement",
             "without replacement", "maximum value", "at least", "at most"],
    "aptitude": ["analogy", "synonym", "antonym", "grammar", "sentence", "paragraph",
                 "percentage", "ratio", "average", "speed", "distance", "profit",
                 "loss", "interest", "mixture", "alligation", "venn", "syllogism",
                 "blood relation", "direction sense", "series completion", "odd one out",
                 "availability", "salience", "cognitive bias", "meaning", "opposite",
                 "mirror", "water image", "population", "growth", "annual",
                 "compound interest", "calendar", "clock", "train", "boat", "stream",
                 "partnership", "ages", "fraction", "conclusion", "divisible",
                 "divisibility", "remainder", "divisor", "circle", "triangle",
                 "tangent", "chord", "radius", "diameter", "circumference",
                 "polygon", "angle", "parallel", "perpendicular", "congruent",
                 "arithmetic progression", "geometric progression", "harmonic progression",
                 "in AP", "in GP", "logarithm", "grammatically", "grammatical",
                 "one word", "vocabulary", "most nearly", "nearest in meaning",
                 "closest in meaning", "two-digit", "three-digit", "digits",
                 "unit’s place", "ten’s place", "premise", "assumption",
                 "inference", "course of action"],
}


def guess_subject(text: str, prior: str | None = None) -> str:
    t = text.lower()
    if prior == "aptitude":
        return "aptitude"
    if not t.strip() and not prior:
        return "unknown"  # image-only card from a mixed file: do not guess
    scores = {}
    for subj, kws in SUBJECT_KEYWORDS.items():
        scores[subj] = sum(t.count(k) for k in kws)
    if prior and scores.get(prior, 0) > 0:
        return prior
    best, best_score = None, 0
    for subj in SUBJECT_KEYWORDS:
        if scores[subj] > best_score:
            best, best_score = subj, scores[subj]
    if best:
        return best
    # Nothing scorable: trust a subjectwise-file prior over the ds_algo default.
    return prior or "ds_algo"


def strip_html(h: str) -> str:
    h = re.sub(r"<script.*?</script>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<style.*?</style>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<br\s*/?>", "\n", h, flags=re.I)
    h = re.sub(r"</p\s*>", "\n", h, flags=re.I)
    h = re.sub(r"<[^>]+>", " ", h)
    h = htmlmod.unescape(h)
    h = re.sub(r"[ \t\xa0]+", " ", h)
    h = re.sub(r"\n\s*\n+", "\n", h)
    return h.strip()


# ---------------- GO Classes ----------------

def go_brace_json(raw: str):
    i = raw.find("const TEST_DATA")
    if i < 0:
        return None
    j = raw.find("{", i)
    depth, k, instr, esc = 0, j, False, False
    for k in range(j, len(raw)):
        c = raw[k]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(raw[j:k + 1])
    return None


GO_TAG_SUBJECT = {
    "DS": "ds_algo", "Algorithms": "ds_algo", "Graph Theory": "discrete",
    "Linear Algebra": "linalg", "Quantitative Aptitude": "aptitude",
    "AI/ML": "ml", "Machine Learning": "ml",
    "Programming in Python": "prog", "Programming in C": "prog",
    "Programming and DS": "prog",
}

GO_FILE_SUBJECT = {
    "dsa1": "ds_algo", "dsa2": "ds_algo", "dsa3": "ds_algo", "dsa4": "ds_algo",
    "dsa6": "ds_algo", "fund_linear_algebra": None, "fund_seq_series": "aptitude",
    "ml1": "ml", "ml2": "ml", "ml3": "ml", "ml4": "ml",
    "python1": "prog", "python2": "prog",
}


def parse_go():
    out = []
    for f in sorted(os.listdir(GO_DIR)):
        if not f.endswith(".html") or f == "index.html":
            continue
        slug = f[:-5]
        raw = open(os.path.join(GO_DIR, f), encoding="utf-8", errors="replace").read()
        data = go_brace_json(raw)
        if not data:
            print(f"  [warn] no TEST_DATA in {f}", file=sys.stderr)
            continue
        title = data.get("title", slug)
        prior = GO_FILE_SUBJECT.get(slug)
        for q in data["questions"]:
            qtype = q.get("type", "MCQ")
            opts = q.get("options", {}) or {}
            images = q.get("images", []) or []
            crop_images = q.get("crop_images", []) or []
            text = strip_html(q.get("stem", ""))
            opt_list = [strip_html(opts.get(l, "")) for l in "ABCD"] if qtype in ("MCQ", "MSQ") else []
            correct = q.get("correct", []) or []
            tag = q.get("tag")
            # Institute's own tag is authoritative; keywords only fill gaps.
            subj = GO_TAG_SUBJECT.get(tag) or guess_subject(
                text + " " + " ".join(opt_list), prior)
            # fund_linear_algebra mixes aptitude(Quant) + linalg: keyword decides
            out.append({
                "institute": "GO", "test": title, "file": f,
                "qnum": q.get("qnum"), "qtype": qtype,
                "marks": q.get("award"), "tag": q.get("tag"),
                "subject": subj, "text": text, "options": opt_list,
                "correct": correct, "has_images": bool(images or crop_images),
            })
    return out


# ---------------- MadeEasy ----------------

def me_file_prior(fname: str) -> str | None:
    low = fname.lower()
    for frag, subj in ME_FILE_SUBJECT:
        if frag in low:
            return subj
    return None


def parse_madeeasy(limit: int = 0):
    out = []
    files = sorted(f for f in os.listdir(ME_DIR) if f.endswith(".html"))
    if limit:
        files = files[:limit]
    for f in files:
        raw = open(os.path.join(ME_DIR, f), encoding="utf-8", errors="replace").read()
        body = re.sub(r"<script.*?</script>", "", raw, flags=re.S | re.I)
        title_m = re.search(r"<title>(.*?)</title>", raw, flags=re.S | re.I)
        title = htmlmod.unescape(title_m.group(1).strip()) if title_m else f
        prior = me_file_prior(f)
        cards = re.findall(r'<section class="card qcard"(.*?)</section>', body, flags=re.S)
        for card in cards:
            m = re.search(r'data-qnum="(\d+)"\s+data-qtype="([A-Z]+)".*?data-correct="([^"]*)"', card)
            if not m:
                continue
            qnum, qtype, correct = int(m.group(1)), m.group(2), m.group(3).strip()
            tm = re.search(r'<div class="qtext">(.*?)</div>\s*<div class="opts">', card, flags=re.S)
            if not tm:
                # NAT cards have no options block; match the qtext close only.
                tm = re.search(r'<div class="qtext">(.*?)</div>', card, flags=re.S)
            stem_html = tm.group(1) if tm else ""
            opts = []
            # ANY <img> (data:, CDN, relative) means figure-dependent: mapping only.
            has_img = "<img" in stem_html.lower()
            if qtype == "MCQ":
                for letter in "ABCD":
                    om = re.search(r'data-opt="%s".*?<div><b>%s\.</b>(.*?)</div>\s*</label>' % (letter, letter), card, flags=re.S)
                    ohtml = om.group(1) if om else ""
                    if "<img" in ohtml.lower():
                        has_img = True
                    opts.append(strip_html(ohtml))
            else:
                # NAT/MSQ: options may exist for MSQ
                for letter in "ABCD":
                    om = re.search(r'data-opt="%s".*?<div><b>%s\.</b>(.*?)</div>\s*</label>' % (letter, letter), card, flags=re.S)
                    if om:
                        ohtml = om.group(1)
                        if "<img" in ohtml.lower():
                            has_img = True
                        opts.append(strip_html(ohtml))
            am = re.search(r'Correct answer:\s*<b>([^<]*)</b>', card)
            answerline = am.group(1).strip() if am else ""
            text = strip_html(stem_html)
            subj = guess_subject(text + " " + " ".join(opts), prior)
            out.append({
                "institute": "ME", "test": title, "file": f,
                "qnum": qnum, "qtype": qtype,
                "marks": None, "tag": None,
                "subject": subj, "text": text, "options": opts,
                "correct": correct, "answerline": answerline,
                "has_images": has_img,
            })
    return out


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "go"
    limit = 0
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    data = parse_go() if which == "go" else parse_madeeasy(limit)
    print(f"{which}: {len(data)} questions")
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        json.dump(data, open(out, "w"), indent=1)
        print(f"wrote {out}")
