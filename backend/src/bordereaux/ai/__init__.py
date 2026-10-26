"""Optional LLM integration for semantic interpretation and review hints.

The deterministic pipeline never depends on this package. If the user has not
configured an LLM provider, the service is disabled and the rest of the platform
continues to operate normally.
"""

from bordereaux.ai.service import LLMService, NoOpLLMProvider, OpenAICompatibleProvider, build_llm_provider, build_llm_service

__all__ = [
    "LLMService",
    "NoOpLLMProvider",
    "OpenAICompatibleProvider",
    "build_llm_provider",
    "build_llm_service",
]
