import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from quant.api.main import app

client = TestClient(app)

@patch("quant.api.routes.assistant.llm_provider")
def test_chat_invalid_symbol(mock_provider):
    mock_provider.generate_response.return_value = "Hello"
    response = client.post("/api/assistant/chat", json={
        "symbol": "INVALID",
        "messages": [{"role": "user", "content": "hello"}]
    })
    assert response.status_code == 404

@patch("quant.api.routes.assistant.llm_provider")
def test_chat_success(mock_provider):
    mock_provider.generate_response.return_value = "The equity is 91,464.71"
    response = client.post("/api/assistant/chat", json={
        "symbol": "ITC",
        "messages": [{"role": "user", "content": "What is the equity?"}]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "The equity is 91,464.71"
    assert "ITC backtest summary" in data["sources"]

@patch("quant.api.routes.assistant.llm_provider")
def test_chat_provider_failure(mock_provider):
    mock_provider.generate_response.side_effect = RuntimeError("Groq down")
    response = client.post("/api/assistant/chat", json={
        "symbol": "ITC",
        "messages": [{"role": "user", "content": "Hello"}]
    })
    assert response.status_code == 502
