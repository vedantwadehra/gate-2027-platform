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
    name = (model or "").lower()
    return any(hint in name for hint in VISION_HINTS)


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
        if provider == "openai" and settings.llm_api_key:
            return await _call_openai(
                system, user, model=model, image=image, image_media_type=image_media_type
            )
        if provider == "google" and settings.llm_api_key:
            return await _call_google(
                system, user, image=image, image_media_type=image_media_type
            )
        if provider == "groq" and settings.llm_api_key:
            return await _call_openai(
                system,
                user,
                base_url="https://api.groq.com/openai/v1",
                model=model or settings.groq_model,
                image=image,
                image_media_type=image_media_type,
            )
    except Exception:
        # Never break the chat UX on a provider/network failure.
        return await _call_mock(system, user)
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
    """
    provider = settings.llm_provider.lower()
    if provider in ("openai", "groq") and settings.llm_api_key:
        base = "https://api.groq.com/openai/v1" if provider == "groq" else None
        mdl = model or (settings.groq_model if provider == "groq" else None)
        try:
            async for tok in _stream_openai(
                system,
                user,
                base_url=base,
                model=mdl,
                image=image,
                image_media_type=image_media_type,
            ):
                yield tok
            return
        except Exception:
            async for tok in _stream_mock(system, user):
                yield tok
            return
    # Google / mock: fetch once, then emit in word chunks.
    full = await generate(
        system, user, model=model, image=image, image_media_type=image_media_type
    )
    for piece in full.split(" "):
        yield piece + " "
