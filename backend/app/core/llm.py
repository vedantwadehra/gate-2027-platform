"""Provider-agnostic LLM client with a built-in mock for offline dev."""

import base64
import json
from typing import AsyncGenerator

import httpx

from app.core.config import settings


# Heuristic: which provider/model combinations accept image input.
VISION_HINTS = (
    "vision",
    "gpt-4o",
    "gpt-4-vision",
    "gpt-4-turbo",
    "claude-3",
    "llama-3.2-90b-vision",
    "gemini",
    "qwen-vl",
    "pixtral",
)


def model_supports_vision(provider: str, model: str | None) -> bool:
    """Best-effort check of whether the configured model can ingest images."""
    if (provider or "").lower() == "google":
        return True
    if (provider or "").lower() == "groq":
        # Groq only serves image input on models whose id contains "vision".
        return "vision" in (model or "").lower()
    name = (model or "").lower()
    return any(hint in name for hint in VISION_HINTS)


# Some providers (e.g. Groq) return a rejection as a *normal* 200 completion
# whose content is the error message, rather than as an HTTP error. Detect it.
_ERROR_SIGNS = (
    "does not support image input",
    "invalid_request_error",
    "this model does not support",
    "model does not support",
    "is not a supported model",
    '"error"',
    "cannot read",
)


def _looks_like_provider_error(text: str) -> bool:
    t = (text or "").lower()
    return any(sign in t for sign in _ERROR_SIGNS)


def _openai_user_content(user: str, image: bytes | None, image_media_type: str | None):
    if image is None:
        return user
    b64 = base64.b64encode(image).decode()
    return [
        {"type": "text", "text": user},
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:{image_media_type or 'image/png'};base64,{b64}"
            },
        },
    ]


def _build_context_prompt(system: str, user: str) -> str:
    return f"{system}\n\nUser: {user}\nAssistant:"


async def _call_openai(
    system: str,
    user: str,
    base_url: str | None = None,
    model: str | None = None,
    image: bytes | None = None,
    image_media_type: str | None = None,
) -> str:
    url = (base_url or "https://api.openai.com/v1") + "/chat/completions"
    payload = {
        "model": model or settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _openai_user_content(user, image, image_media_type)},
        ],
        "temperature": 0.3,
        "max_tokens": 1500,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def _call_google(
    system: str,
    user: str,
    image: bytes | None = None,
    image_media_type: str | None = None,
) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.google_model}:generateContent?key={settings.llm_api_key}"
    )
    parts = []
    if image is not None:
        parts.append(
            {
                "inline_data": {
                    "mime_type": image_media_type or "image/png",
                    "data": base64.b64encode(image).decode(),
                }
            }
        )
    parts.append({"text": user})
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"maxOutputTokens": 1500},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]


async def _stream_openai(
    system: str,
    user: str,
    base_url: str | None = None,
    model: str | None = None,
    image: bytes | None = None,
    image_media_type: str | None = None,
) -> AsyncGenerator[str, None]:
    url = (base_url or "https://api.openai.com/v1") + "/chat/completions"
    payload = {
        "model": model or settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _openai_user_content(user, image, image_media_type)},
        ],
        "temperature": 0.3,
        "max_tokens": 1500,
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = chunk["choices"][0]["delta"].get("content")
                if delta:
                    yield delta


async def _call_mock(system: str, user: str) -> str:
    # Offline fallback so the platform works without API keys.
    return (
        "This is a mock AI tutor response (no LLM key configured). "
        "Set LLM_PROVIDER and LLM_API_KEY in backend/.env to enable live answers.\n\n"
        f"Context used:\n{system[-600:]}\n\nBased on your question, review the relevant "
        "syllabus section and practice similar PYQs. Ask me to generate a question on any topic!"
    )


async def _stream_mock(system: str, user: str) -> AsyncGenerator[str, None]:
    text = await _call_mock(system, user)
    for piece in text.split(" "):
        yield piece + " "


async def generate(
    system: str,
    user: str,
    model: str | None = None,
    image: bytes | None = None,
    image_media_type: str | None = None,
) -> str:
    """Generate a reply, falling back to the mock tutor on any provider error."""
    provider = settings.llm_provider.lower()
    try:
        reply = None
        if provider == "openai" and settings.llm_api_key:
            reply = await _call_openai(
                system, user, model=model, image=image, image_media_type=image_media_type
            )
        elif provider == "google" and settings.llm_api_key:
            reply = await _call_google(
                system, user, image=image, image_media_type=image_media_type
            )
        elif provider == "groq" and settings.llm_api_key:
            reply = await _call_openai(
                system,
                user,
                base_url="https://api.groq.com/openai/v1",
                model=model or settings.groq_model,
                image=image,
                image_media_type=image_media_type,
            )
        if reply is None:
            return await _call_mock(system, user)
        # A provider may return the rejection as ordinary content (HTTP 200).
        if _looks_like_provider_error(reply):
            raise RuntimeError("provider returned an error response")
        return reply
    except Exception:
        # If the image was rejected (e.g. a mis-detected text-only model),
        # retry once with the OCR text already embedded in `user`, never raw-error.
        if image is not None:
            try:
                return await generate(system, user, model=model)
            except Exception:
                pass
        # Never break the chat UX on a provider/network failure.
        return await _call_mock(system, user)


async def generate_stream(
    system: str,
    user: str,
    model: str | None = None,
    image: bytes | None = None,
    image_media_type: str | None = None,
) -> AsyncGenerator[str, None]:
    """Yield response tokens incrementally for a streaming chat UX.

    On any provider/network failure it transparently falls back to the mock
    tutor so the chat UI never shows a hard error.

    Some providers return an image rejection as ordinary streamed content
    instead of an HTTP error. That rejection always arrives as a short,
    front-loaded message, so when an image is attached we gate on the first
    ~300 chars before streaming live; text-only calls stream straight
    through with zero buffering.
    """
    provider = settings.llm_provider.lower()
    if provider in ("openai", "groq") and settings.llm_api_key:
        base = "https://api.groq.com/openai/v1" if provider == "groq" else None
        mdl = model or (settings.groq_model if provider == "groq" else None)
        try:
            stream = _stream_openai(
                system,
                user,
                base_url=base,
                model=mdl,
                image=image,
                image_media_type=image_media_type,
            )
            if image is None:
                async for tok in stream:
                    yield tok
                return
            head: list[str] = []
            head_len = 0
            async for tok in stream:
                head.append(tok)
                head_len += len(tok)
                if head_len >= 300:
                    break
            text = "".join(head)
            if _looks_like_provider_error(text):
                raise RuntimeError("provider returned an error response")
            for tok in head:
                yield tok
            # Remainder streams live; keep watching in case a rejection
            # appears past the head window, and abort to the fallback then.
            tail = [text]
            async for tok in stream:
                tail.append(tok)
                if _looks_like_provider_error("".join(tail)[-600:]):
                    raise RuntimeError("provider returned an error response")
                yield tok
            return
        except Exception:
            if image is not None:
                # Retry without the image (OCR text is already in `user`).
                try:
                    async for tok in generate_stream(system, user, model=model):
                        yield tok
                    return
                except Exception:
                    pass
            async for tok in _stream_mock(system, user):
                yield tok
            return
    # Google / mock: fetch once, then emit in word chunks.
    full = await generate(
        system, user, model=model, image=image, image_media_type=image_media_type
    )
    for piece in full.split(" "):
        yield piece + " "
