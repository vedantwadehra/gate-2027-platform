"""Unit tests for streaming error-gating (stubbed provider, no network)."""

import asyncio

from app.core import llm


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _collect(gen):
    return [t async for t in gen]


def _provider(monkeypatch, tokens, fail=False):
    async def fake(*args, **kwargs):
        for tok in tokens:
            yield tok
        if fail:
            raise RuntimeError("boom")

    monkeypatch.setattr(llm, "_stream_openai", fake)
    monkeypatch.setattr(llm.settings, "llm_provider", "groq")
    monkeypatch.setattr(llm.settings, "llm_api_key", "x")


def test_text_stream_passes_through(monkeypatch):
    _provider(monkeypatch, ["hel", "lo ", "world"])
    out = run(_collect(llm.generate_stream("s", "u")))
    assert "".join(out) == "hello world"


def test_image_error_head_falls_back_without_image(monkeypatch):
    seen = {}

    async def fake(system, user, base_url=None, model=None, image=None,
                   image_media_type=None):
        seen["image"] = image
        if image is not None:
            yield "Cannot read image.png (this model does not support image input)"
        else:
            yield "clean answer"

    monkeypatch.setattr(llm, "_stream_openai", fake)
    monkeypatch.setattr(llm.settings, "llm_provider", "groq")
    monkeypatch.setattr(llm.settings, "llm_api_key", "x")
    out = run(_collect(llm.generate_stream("s", "u", image=b"img")))
    assert "".join(out) == "clean answer"
    assert seen["image"] is None  # retry went out imageless


def test_image_clean_head_streams_fully(monkeypatch):
    _provider(monkeypatch, ["The answer is 4", " because 2+2.", " Done."])
    out = run(_collect(llm.generate_stream("s", "u", image=b"img")))
    assert "".join(out) == "The answer is 4 because 2+2. Done."


def test_provider_exception_falls_back_to_mock(monkeypatch):
    _provider(monkeypatch, ["partial"], fail=True)
    out = run(_collect(llm.generate_stream("s", "u")))
    text = "".join(out)
    assert "mock AI tutor response" in text
