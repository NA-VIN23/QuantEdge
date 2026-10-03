"""
quant/api/llm_provider.py
-------------------------
Provider abstraction for the QuantEdge AI Research Assistant.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any

try:
    from groq import Groq
    from groq.types.chat import ChatCompletionMessageParam
except ImportError:  # pragma: no cover
    Groq = None  # type: ignore
    ChatCompletionMessageParam = Any  # type: ignore


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers to ensure
    the Research Assistant remains vendor-agnostic.
    """

    @abstractmethod
    def generate_response(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]]
    ) -> str:
        """
        Generate a response given a system prompt and a list of message dicts
        e.g., [{"role": "user", "content": "What is the final equity?"}]
        """
        pass


class GroqProvider(BaseLLMProvider):
    """
    Groq API implementation.
    Reads GROQ_API_KEY and GROQ_MODEL from environment.
    """

    def __init__(self):
        if Groq is None:
            raise ValueError("The 'groq' package is not installed. Please run 'pip install -r requirements.txt'.")

        # We rely on the groq package picking up GROQ_API_KEY from os.environ
        # But we also assert it's present to fail fast.
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set.")

        self.model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        self.client = Groq(api_key=self.api_key)

    def generate_response(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]]
    ) -> str:

        # Prepare messages in the exact format required by Groq
        formatted_messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt}
        ]

        for msg in messages:
            if msg["role"] in ["user", "assistant"]:
                formatted_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                }) # type: ignore

        try:
            response = self.client.chat.completions.create(
                messages=formatted_messages,
                model=self.model,
                temperature=0.0, # Strict deterministic/grounded mode
                max_tokens=1024,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            # Wrap any provider-specific errors
            raise RuntimeError(f"Groq provider error: {str(e)}")
