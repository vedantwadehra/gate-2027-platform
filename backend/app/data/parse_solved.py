"""Parse 'Solved' GATE CS PYQ PDFs.

Format: each MCQ shows options (A)/(a)...(D)/(d) then an answer marker like
'Ans. (C)' / 'Ans: (C)' immediately before the explanation ('Exp:').

Usage: python3 parse_solved.py <pdf_path> [--json out.json]
Skips NAT (no 4 options) and questions without a detected answer letter.
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


def build_mcq(body: str):
    """Return (answer_letter, options, stem) for a question block, or None."""
    am = re.search(r"Ans\.?\s*[:\-]?\s*\(?\s*([A-Da-d])", body, re.I)
    if am:
        letter = am.group(1).upper()
        # options come BEFORE the answer marker; cut there to drop the explanation
        body = body[:am.start()]
        body = re.sub(r"Ans\.?\s*[:\-]?\s*\(?\s*[A-Da-d]\s*\)?", " ", body, flags=re.I)
    else:
        am2 = re.search(r"correct\s+option\s+is\s*\(?\s*([A-Da-d])", body, re.I)
        if not am2:
            am2 = re.search(r"option\s*\(?\s*([A-Da-d])\s*\)?\s*is\s+(?:the\s+)?correct", body, re.I)
        if not am2:
            return None
        letter = am2.group(1).upper()
        body = re.split(r"Exp\.?|Explanation|Solution|Soln?\.?", body)[0]
    letters = re.findall(r"\(\s*([A-Da-d])\s*\)", body, re.I)
    splits = re.split(r"\(\s*[A-Da-d]\s*\)", body, flags=re.I)[1:]
    opts = {}
    for L, o in zip([x.upper() for x in letters], [s.strip() for s in splits]):
        opts.setdefault(L, o)
    if set(opts.keys()) != {"A", "B", "C", "D"}:
        return None
    options = [re.sub(r"\s+", " ", opts[L]).strip() for L in "ABCD"]
    stem = re.split(r"\(\s*A\s*\)", body, flags=re.I)[0].strip()
    stem = re.sub(r"^\s*\d+\.\s*", "", stem).strip()
    if not stem or any(not o for o in options):
        return None
    return letter, options, stem


SPLIT_RE = re.compile(r"(?:^|\n)\s*(?:Q\.?\s*)?(\d{1,3})\s*[\.\)]?\s")


def degarble(t: str) -> str:
    """Collapse the exact repeated-token overlap artifacts in MadeEasy PDFs
    (e.g. 'Q.1Q.1Q.1' -> 'Q.1', 'Ans.Ans. (b)(b)(b)' -> 'Ans. (b)')."""
    t = re.sub(r"(Q\.\s*\d+)(?:\s*\1)+", r"\1", t)
    t = re.sub(r"(Ans\.?)(?:\s*\1)+", r"\1", t)
    t = re.sub(r"(\(\s*[A-Da-d]\s*\))(?:\s*\1)+", r"\1", t)
    return t


def parse_paper(text: str, year: int):
    text = degarble(text)
    parts = SPLIT_RE.split("\n" + text)
    out = []
    for i in range(1, len(parts) - 1, 2):
        num, body = parts[i], parts[i + 1]
        if int(num) > 90:
            continue
        m = build_mcq(body)
        if not m:
            continue
        letter, options, stem = m
        sec = "cs_aptitude" if is_aptitude(stem + " " + " ".join(options)) else guess_section(stem)
        out.append({
            "year": year, "section": sec,
            "source": f"GATE CS {year} (solved PYQ)", "verified": True,
            "text": re.sub(r"\s+", " ", stem).strip(),
            "options": options, "answer": LETTER_IDX[letter], "answer_letter": letter,
        })
    return out


def parse_combined(path: str, years):
    """Parse a multi-paper PDF; split papers on question-number reset; assign `years` in order."""
    txt = extract_text(path)
    txt = degarble(txt)
    parts = SPLIT_RE.split("\n" + txt)
    blocks = []
    for i in range(1, len(parts) - 1, 2):
        num, body = int(parts[i]), parts[i + 1]
        if num > 90:
            continue
        m = build_mcq(body)
        if m:
            blocks.append((num, m))
    # split into papers where the question number resets
    papers, cur, prev_max = [], [], 0
    for num, m in blocks:
        if num <= prev_max and cur:
            papers.append(cur); cur = []
            prev_max = 0
        cur.append(m); prev_max = max(prev_max, num)
    if cur:
        papers.append(cur)
    out = []
    for y, paper in zip(years, papers):
        for letter, options, stem in paper:
            sec = "cs_aptitude" if is_aptitude(stem + " " + " ".join(options)) else guess_section(stem)
            out.append({
                "year": y, "section": sec,
                "source": f"GATE CS {y} (solved PYQ)", "verified": True,
                "text": re.sub(r"\s+", " ", stem).strip(),
                "options": options, "answer": LETTER_IDX[letter], "answer_letter": letter,
            })
    return out


def is_aptitude(text: str) -> bool:
    t = text.lower()
    kw = ["the word that best fills", "synonym", "antonym", "fill the blank", "grammar",
          "sentence", "passage", "choose the correct", "missing number", "average speed",
          "smallest natural number", "area of a square", "logical", "verbal"]
    return sum(t.count(k) for k in kw) >= 1


def split_by_year(text: str):
    """Return list of (year, segment) using 'CS-GATE-YYYY PAPER' headers, else whole text."""
    segs = re.split(r"CS-GATE-(\d{4})\s+PAPER", text)
    if len(segs) > 1:
        res = []
        for i in range(1, len(segs) - 1, 2):
            res.append((int(segs[i]), segs[i + 1]))
        return res
    return [(None, text)]


def parse_pdf_solved(path: str):
    r = PyPDF2.PdfReader(path)
    ym = re.search(r"(19|20)\d{2}", path)
    file_year = int(ym.group(0)) if ym else None
    pages = [(p.extract_text() or "") for p in r.pages]
    # group consecutive pages by the footer year (CS-GATE-YYYY PAPER)
    groups = []
    cur_year, cur_txt = None, []
    for pg in pages:
        m = re.search(r"CS-GATE-(\d{4})\s+PAPER", pg)
        y = int(m.group(1)) if m else cur_year
        if y != cur_year and cur_txt:
            groups.append((cur_year, "\n".join(cur_txt)))
            cur_txt = []
        cur_year = y
        cur_txt.append(pg)
    if cur_txt:
        groups.append((cur_year, "\n".join(cur_txt)))
    allq = []
    for y, seg in groups:
        yy = y or file_year
        if yy is None:
            continue
        allq += parse_paper(seg, yy)
    return allq


if __name__ == "__main__":
    path = sys.argv[1]
    allq = parse_pdf_solved(path)
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        json.dump(allq, open(out, "w"), indent=2)
        print(f"wrote {len(allq)} MCQs to {out}")
    else:
        print(f"pdf={path.split('/')[-1]} mcqs={len(allq)}")
        for r in allq[:3]:
            print("---", r["section"], r["answer_letter"])
            print(r["text"][:110]); print(r["options"])

