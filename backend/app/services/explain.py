"""Generate (and the caller caches) a concise explanation for a question.

Uses the provider LLM; falls back to a short static note if the LLM is unavailable
so the review screen always has something to show.
"""
from app.core import llm


async def explain_question(paper: str, q: dict) -> str:
    opts = q.get("options", [])
    qt = (q.get("qtype") or "MCQ").upper()
    if qt == "MSQ":
        idxs = [i for i in (q.get("answer_list") or [q.get("answer", 0)])
                if isinstance(i, int) and 0 <= i < len(opts)]
        correct_label = "(" + ",".join(chr(65 + i) for i in idxs) + ")"
        correct_text = "; ".join(opts[i] for i in idxs) or "?"
    elif qt == "NAT":
        correct_label = str(q.get("answer_num"))
        correct_text = correct_label
    else:
        correct = q.get("answer", 0)
        correct_text = opts[correct] if 0 <= correct < len(opts) else "?"
        correct_label = chr(65 + correct) if 0 <= correct < len(opts) else "?"
    opt_lines = "\n".join(
        f"{chr(65 + i)}. {o}" for i, o in enumerate(opts)
    )
    prompt = (
        "You are a GATE (Graduate Aptitude Test in Engineering) tutor. "
        "Explain, concisely and accurately, why the given correct answer is right "
        "for the question below. Use a short step-by-step rationale (max ~120 words). "
        "Do not repeat the question verbatim; focus on the reasoning.\n\n"
        f"Question: {q.get('text', '')}\n\nOptions:\n{opt_lines}\n\n"
        f"Correct answer: {correct_label}. {correct_text}"
    )
    try:
        text = await llm.generate(
            "You are a precise GATE exam tutor. Give only the explanation.", prompt
        )
    except Exception:
        text = (
            f"The correct answer is {correct_label}. {correct_text}. "
            "(Auto-generated explanation unavailable — review the related syllabus section.)"
        )
    return text.strip()
