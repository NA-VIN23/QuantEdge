"""
quant/api/routes/assistant.py
-----------------------------
Sprint 7 AI Research Assistant API.
Provides read-only explanation grounded in QuantEdge metrics.
"""

from __future__ import annotations

import logging
from typing import List, Dict
from fastapi import APIRouter, HTTPException

from quant.api.schemas import ChatRequest, ChatResponse
from quant.api.context_builder import build_research_context
from quant.api.llm_provider import GroqProvider
from quant.data.registry import VALID_SYMBOLS

router = APIRouter(tags=["assistant"])
logger = logging.getLogger(__name__)

# Initialize provider on load. Will raise ValueError if API key is missing.
try:
    llm_provider = GroqProvider()
except Exception as e:
    logger.warning(f"Failed to initialize GroqProvider: {e}")
    llm_provider = None


SYSTEM_PROMPT_TEMPLATE = """You are the QuantEdge AI Research Assistant.
Your sole purpose is to answer questions about quantitative research using ONLY the exact data provided below.
The data comes directly from the QuantEdge read-only verified research engine.

CRITICAL RULES:
1. PRESERVE NUMBERS EXACTLY: If a metric is provided (e.g. ₹91,464.71), output it exactly as provided. Do not round or alter it unless explicitly asked.
2. DO NOT INVENT DATA: If the user asks for a metric or fact not present in the provided context, you must explicitly state that the metric is unavailable.
3. READ-ONLY GUARANTEE: You cannot modify strategy, run code, change parameters, place trades, or optimize anything. If asked to do so, decline.
4. BE CONCISE: Provide clear, concise answers appropriate for a quantitative researcher.
5. CONVERSATION CONTEXT: If the user says "it" or "the stock", they are referring to the symbol provided in the context.

Here is the context data:
{context_string}
"""


@router.post("/assistant/chat", response_model=ChatResponse)
def chat_with_assistant(request: ChatRequest) -> ChatResponse:
    """
    Interact with the QuantEdge Research Assistant.
    Provides answers grounded strictly in the available JSON artifacts for the symbol.
    """
    if llm_provider is None:
        raise HTTPException(
            status_code=503,
            detail="LLM Provider is not configured (missing GROQ_API_KEY environment variable)."
        )

    symbol = request.symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' is not recognised."
        )

    # 1. Build the exact context for this symbol
    try:
        context_string, sources = build_research_context(symbol)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build research context for {symbol}: {str(e)}"
        )

    # 2. Format System Prompt
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context_string=context_string)

    # 3. Prepare messages
    messages_dict: List[Dict[str, str]] = []
    for msg in request.messages:
        if msg.role not in ["user", "assistant"]:
            raise HTTPException(status_code=400, detail="Message role must be 'user' or 'assistant'.")
        messages_dict.append({"role": msg.role, "content": msg.content})

    # 4. Generate Response
    try:
        reply = llm_provider.generate_response(
            system_prompt=system_prompt,
            messages=messages_dict
        )
    except Exception as e:
        # e.g. Provider error (quota, network)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to generate response from LLM provider: {str(e)}"
        )

    return ChatResponse(
        reply=reply.strip(),
        sources=sources
    )
