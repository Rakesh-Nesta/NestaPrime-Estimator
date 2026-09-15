"""Amendment 13 (Section 12): app/services/ai_content.py unit tests.
Every Anthropic call is monkeypatched -- no network access in tests, same
discipline as test_wa_gateway_integration.py."""

import httpx
import pytest

from app.config import settings
from app.services import ai_content


def test_not_configured_fails_fast_without_network(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with pytest.raises(ai_content.AiContentError, match="not configured"):
        ai_content.generate_text("Draft something")


def test_success_returns_the_concatenated_text_blocks(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    def _fake_post(url, json, headers, timeout):
        assert url == ai_content.ANTHROPIC_API_URL
        assert headers["x-api-key"] == "test-key"
        assert json["model"] == settings.anthropic_model
        assert json["messages"] == [{"role": "user", "content": "Draft something"}]
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "Hello "}, {"type": "text", "text": "world"}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(ai_content.httpx, "post", _fake_post)
    assert ai_content.generate_text("Draft something") == "Hello world"


def test_non_200_response_raises(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    def _fake_post(url, json, headers, timeout):
        return httpx.Response(401, text="invalid api key", request=httpx.Request("POST", url))

    monkeypatch.setattr(ai_content.httpx, "post", _fake_post)
    with pytest.raises(ai_content.AiContentError, match="401"):
        ai_content.generate_text("Draft something")


def test_network_failure_raises(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    def _fake_post(url, json, headers, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(ai_content.httpx, "post", _fake_post)
    with pytest.raises(ai_content.AiContentError, match="request failed"):
        ai_content.generate_text("Draft something")


def test_unexpected_response_shape_raises(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    def _fake_post(url, json, headers, timeout):
        return httpx.Response(200, json={"unexpected": "shape"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(ai_content.httpx, "post", _fake_post)
    with pytest.raises(ai_content.AiContentError, match="unexpected response shape"):
        ai_content.generate_text("Draft something")
