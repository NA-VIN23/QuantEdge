import pytest
import os
from quant.api.llm_provider import BaseLLMProvider, GroqProvider

def test_groq_provider_missing_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY environment variable is not set"):
        GroqProvider()

def test_groq_provider_init(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODEL", "test-model")

    provider = GroqProvider()
    assert provider.api_key == "test-key"
    assert provider.model == "test-model"
