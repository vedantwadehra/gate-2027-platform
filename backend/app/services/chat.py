"""AI tutor chat service using retrieval-augmented generation."""

from app.services import retrieval


SYSTEM_TEMPLATE = (
    "You are GATEMentor, an expert AI tutor for GATE 2027 (Data Analytics and "
    "Computer Science papers). Help the student by explaining concepts, solving "
    "doubts, and generating practice questions. Use the retrieved context when "
    "relevant, but keep answers clear and exam-focused. If asked to generate a "
    "question, provide one with options and an explanation. "
    "Format every answer with clean Markdown: short headings, bullet or numbered "
    "lists, tables where they help, and fenced code blocks for code. Write ALL "
    "mathematics with $...$ inline and $$...$$ display delimiters. Never use "
    "\\( \\), \\[ \\], or raw unicode math — dollar delimiters only, or the "
    "math will not render. Inside math, never write a bare # character (it "
    "breaks rendering); write the word 'number of' instead, e.g. "
    "$\\frac{\\text{number of favorable outcomes}}{\\text{number of total outcomes}}$. "
    "Avoid \\displaystyle (it adds nothing inline). "
    "For numerical problems, reason step by step, simplify carefully, and "
    "double-check the final value against your derivation before stating it. "
    "When the user asks for 'just the value/answer', reply with only that."
)

GEN_TEMPLATE = (
    "You are GATEMentor, an expert GATE 2027 question generator. Create ONE "
    "original multiple-choice practice question (MCQ) for the given paper and "
    "topic, in the style of actual GATE exam questions. Return STRICT JSON only "
    "(no markdown, no extra text) with this shape:\n"
    '{"question": "<stem>", "options": ["A","B","C","D"], '
    '"answer_index": <0-3>, "explanation": "<why the answer is correct>"}\n'
    "Make the question non-trivial and the distractors plausible. Base it on the "
    "retrieved context when available."
)


def build_system(paper: str, context_chunks: list[str], history: list[dict] | None = None) -> str:
    context = "\n\n".join(context_chunks) if context_chunks else "(no context retrieved)"
    hist = ""
    if history:
        hist = "\n\nConversation so far:\n" + "\n".join(
            f"{m['role']}: {m['content']}" for m in history
        )
    return f"{SYSTEM_TEMPLATE}\n\nPaper: {paper}\n\nRetrieved context:\n{context}{hist}"


def build_gen_system(paper: str, context_chunks: list[str]) -> str:
    context = "\n\n".join(context_chunks) if context_chunks else "(no context retrieved)"
    return f"{GEN_TEMPLATE}\n\nPaper: {paper}\n\nRetrieved context:\n{context}"


def _needs_context(message: str) -> bool:
    """Skip retrieval for chit-chat (greetings/thanks/ok): TF-IDF matches
    random lookalikes on content-free text, and the noise hurts more than the
    (absent) signal helps. Everything else — including short conceptual
    queries like 'what is PCA' — still retrieves."""
    import re

    m = (message or "").strip().lower()
    if not m:
        return False
    return not re.fullmatch(
        r"(hi+|hii+|hello+|hey+|yo|thanks?|thank\s+you|thx|ok+|okay|bye+|good\s*(morning|afternoon|evening|day))[!.,\s]*",
        m,
    )


async def answer_question(
    paper: str,
    message: str,
    model: str | None = None,
    image: bytes | None = None,
    image_media_type: str | None = None,
) -> str:
    chunks = retrieval.retrieve(paper, message, k=4) if _needs_context(message) else []
    system = build_system(paper, chunks)
    from app.core.llm import generate

    return await generate(
        system, message, model=model, image=image, image_media_type=image_media_type
    )


async def answer_question_stream(
    paper: str,
    message: str,
    history: list[dict] | None = None,
    model: str | None = None,
    image: bytes | None = None,
    image_media_type: str | None = None,
):
    chunks = retrieval.retrieve(paper, message, k=4) if _needs_context(message) else []
    system = build_system(paper, chunks, history)
    from app.core.llm import generate_stream

    async for token in generate_stream(
        system,
        message,
        model=model,
        image=image,
        image_media_type=image_media_type,
    ):
        yield token


async def generate_question(paper: str, topic: str) -> dict:
    """Generate a new MCQ for a topic using the LLM (returns parsed JSON)."""
    from app.core.llm import generate

    chunks = retrieval.retrieve(paper, topic, k=4)
    system = build_gen_system(paper, chunks)
    try:
        raw = await generate(system, f"Generate a GATE {paper} MCQ on: {topic}")
    except Exception:
        raw = ""
    return _extract_json(raw or "{}")


FLASHCARD_TEMPLATE = (
    "You are GATEMentor. From the study notes below, create concise revision "
    "flashcards for GATE 2027 ({paper}). Return STRICT JSON only (no markdown) "
    "as a list of objects, up to 12 items:\n"
    '[{"front": "<term or question>", "back": "<definition or answer>"}, ...]\n'
    "Keep each front/back short and exam-relevant."
)


async def generate_flashcards(paper: str, notes: str) -> list[dict]:
    """Generate flashcards from pasted/imported notes using the LLM."""
    from app.core.llm import generate

    notes_excerpt = (notes or "")[:6000]
    system = FLASHCARD_TEMPLATE.replace("{paper}", paper)
    try:
        raw = await generate(system, f"Notes:\n{notes_excerpt}")
    except Exception:
        raw = ""
    return _extract_json_list(raw or "[]")


def _extract_json_list(raw: str) -> list[dict]:
    import json as _json
    import re

    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = _json.loads(cleaned)
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict) and d.get("front")]
    except _json.JSONDecodeError:
        pass
    match = re.search(r"\[.*\]", cleaned, flags=re.DOTALL)
    if match:
        try:
            data = _json.loads(match.group(0))
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict) and d.get("front")]
        except _json.JSONDecodeError:
            pass
    return []


def _extract_json(raw: str) -> dict:
    import json as _json
    import re

    # Strip code fences if the model wrapped the JSON.
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        return _json.loads(cleaned)
    except _json.JSONDecodeError:
        pass
    # Fallback: grab the first {...} block.
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        try:
            return _json.loads(match.group(0))
        except _json.JSONDecodeError:
            pass
    return {
        "question": raw,
        "options": [],
        "answer_index": -1,
        "explanation": "",
    }
