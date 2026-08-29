"""Parse GATE CS PYQ PDFs (question + options + official answer key).

Usage: python3 parse_pyq.py <pdf_path> [--json out.json]
Extracts only single-correct MCQs (skips NAT and multiple-correct MSQ).
Matches body MCQs to answer-key letters by document order (robust to
per-section numbering resets). Maps each question to a CS syllabus section.
"""
import sys
import re
import json
import PyPDF2

LETTER_IDX = {"A": 0, "B": 1, "C": 2, "D": 3}

SECTION_KEYWORDS = {
    "cs_toc": ["grammar", "language", "automata", "dfa", "nfa", "turing", "regular",
               "context-free", "context free", "pda", "recursively enumerable", "decidable",
               "pushdown", "finite automaton"],
    "cs_os": ["semaphore", "process", "thread", "scheduling", "paging", "page fault",
              "deadlock", "interrupt", "cpu", "virtual memory", "fork", "mutex", "demand paging"],
    "cs_db": ["sql", "table", "query", "relation", "schema", "normaliz", "er model",
              "transaction", "join", "bcnf", "3nf", "2nf", "foreign key", "primary key"],
    "cs_networks": ["tcp", "udp", "ip ", "network", "mac address", "ethernet", "routing",
                    "http", "protocol", "packets", "osi", "switch", "subnet", "congestion"],
    "cs_compiler": ["compiler", "lexical", "parser", "parse ", "syntax directed", "semantic",
                    "code generation", "intermediate", "token", "grammar", "lr parser", "ll "],
    "cs_ds_algo": ["algorithm", "sort", "tree", "graph", "linked list", "array", "queue",
                   "stack", "hash", "complexity", "recurrence", "dynamic programming",
                   "binary search", "heap", "bst", "avl", "traversal", "asymptotic"],
    "cs_linalg": ["matrix", "eigen", "determinant", "vector", "linear", "rank", "singular"],
    "cs_prob": ["probability", "random", "distribution", "variance", "expectation", "poisson",
                "bernoulli", "gaussian", "normal distribution", "exponential", "mean of"],
    "cs_discrete": ["group", "subset", "permutation", "combination", "proposition", "lattice",
                    "chromatic", "recurrence relation", "boolean", "poset", "function ", "relation "],
}


def guess_section(text: str) -> str:
    t = text.lower()
    best, best_score = "cs_ds_algo", 0
    for sec, kws in SECTION_KEYWORDS.items():
        score = sum(t.count(k) for k in kws)
        if score > best_score:
            best, best_score = sec, score
    return best


def extract_text(path: str) -> str:
    r = PyPDF2.PdfReader(path)
    return "\n".join((p.extract_text() or "") for p in r.pages)


def get_body_mcqs(txt: str):
    """Ordered list of MCQ blocks (those with A-D options) across the whole paper."""
    marker = re.compile(r"Q\.?\s*(\d+)|Question\s+(\d+)")
    matches = list(marker.finditer(txt))
    out = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(txt)
        block = txt[start:end]
        letters = re.findall(r"\(\s*([A-D])\s*\)", block)
        parts = re.split(r"\(\s*[A-D]\s*\)", block)[1:]
        opts = dict(zip(letters, [p.strip() for p in parts]))
        if set(opts.keys()) == {"A", "B", "C", "D"}:
            stem = re.split(r"\(\s*A\s*\)", block)[0].strip()
            out.append({"stem": stem, "options": [re.sub(r"\s+", " ", opts[l]).strip() for l in "ABCD"]})
    return out


def get_key_rows(txt: str):
    """Ordered list of answer-key rows: ('MCQ', letter, sec) / ('NAT',None,sec) / ('MSQ',None,sec)."""
    rows = []
    for m in re.finditer(r"(\d+)\s+(MCQ|NAT|MSQ)\s+(\S+)\s+(\S+)", txt, re.I):
        qnum, typ, sec, key = m.groups()
        sec = "GA" if sec.upper().startswith("GA") else "CS"
        if typ == "MCQ":
            letter = key.strip().split()[0].upper()
            if letter in LETTER_IDX and ";" not in key:
                rows.append(("MCQ", letter, sec))
            else:
                rows.append(("MSQ", None, sec))
        else:
            rows.append(("NAT", None, sec))
    if rows:
        return rows
    # Method 2: GATE 2015 style "Question Number : N  Question Type : MCQ ... Correct Answer :\n<letter>"
    blocks = re.split(r"Question Number\s*:\s*(\d+)\s*Question Type\s*:\s*(MCQ|NAT|MSQ)", txt)
    # blocks: [pre, num, type, text, num, type, text, ...]
    for i in range(1, len(blocks) - 1, 3):
        num, typ, body = blocks[i], blocks[i + 1], blocks[i + 2]
        if typ == "MCQ":
            mm = re.search(r"Correct Answer\s*:?\s*\n?\s*([A-D])", body)
            if mm:
                rows.append(("MCQ", mm.group(1).upper(), "CS"))
    return rows


def parse_pdf(path: str, year: int):
    txt = extract_text(path)
    body = get_body_mcqs(txt)
    key = get_key_rows(txt)
    mcq_keys = [r for r in key if r[0] == "MCQ"]
    if len(body) != len(mcq_keys):
        print(f"  [warn] {year}: body MCQs={len(body)} key MCQs={len(mcq_keys)} (misalignment)", file=sys.stderr)
    results = []
    for q, krow in zip(body, mcq_keys):
        letter = krow[1]
        sec = "cs_aptitude" if krow[2] == "GA" else guess_section(q["stem"] + " " + " ".join(q["options"]))
        results.append({
            "year": year,
            "section": sec,
            "source": f"GATE CS {year} (official paper)",
            "verified": True,
            "text": re.sub(r"\s+", " ", q["stem"]).strip(),
            "options": q["options"],
            "answer": LETTER_IDX[letter],
            "answer_letter": letter,
        })
    return results


if __name__ == "__main__":
    path = sys.argv[1]
    year = int(re.search(r"(19|20)\d{2}", path).group(0))
    res = parse_pdf(path, year)
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        json.dump(res, open(out, "w"), indent=2)
        print(f"wrote {len(res)} MCQs to {out}")
    else:
        print(f"year={year} mcqs={len(res)}")
        for r in res[:3]:
            print("---", r["section"], r["answer_letter"])
            print(r["text"][:120])
            print(r["options"])
