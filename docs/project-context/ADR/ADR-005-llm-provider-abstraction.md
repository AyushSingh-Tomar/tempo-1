# ADR-005: LLM Provider Abstraction

## Status
**Accepted**

## Date
2026-10-09

## Context

The platform uses LLM capabilities for mapping suggestions, exception classification, and pattern explanation. We need to support multiple providers while maintaining consistent behavior.

### Requirements

- Initially support Claude (Anthropic)
- Allow future provider swaps without code changes
- Handle rate limits, retries, and failures gracefully
- Maintain no-LLM mode for deterministic operation
- Protect sensitive data from LLM exposure

## Decision

Implement an **LLM Provider Abstraction Layer** with pluggable backends.

### Architecture

```
┌─────────────────────────────────────────────────┐
│                Application Layer                │
│   (Mapping Service, Reconciliation Service)     │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              LLM Service Interface              │
│   suggest_confidence(), classify_variance()      │
└──────────────────────┬──────────────────────────┘
                       │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │  Claude  │ │  OpenAI  │ │   Mock   │
    │ Provider │ │ Provider │ │ Provider │
    └──────────┘ └──────────┘ └──────────┘
```

### Interface Definition

```python
from abc import ABC, abstractmethod
from typing import Optional

class LLMProvider(ABC):
    """Abstract base for LLM providers."""
    
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.0
    ) -> LLMResponse:
        """Generate completion."""
        ...
    
    @abstractmethod
    async def complete_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        system: Optional[str] = None
    ) -> BaseModel:
        """Generate structured output matching schema."""
        ...
    
    @abstractmethod
    def get_model_info(self) -> ModelInfo:
        """Return model name, context window, etc."""
        ...

class LLMResponse:
    content: str
    usage: TokenUsage
    latency_ms: int
    model: str
```

### Provider Implementations

#### Claude Provider (MVP Default)

```python
class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = Anthropic(api_key=api_key)
        self.model = model
    
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=kwargs.get("max_tokens", 1000),
            messages=[{"role": "user", "content": prompt}],
            system=kwargs.get("system")
        )
        return LLMResponse(
            content=response.content[0].text,
            usage=TokenUsage(
                input=response.usage.input_tokens,
                output=response.usage.output_tokens
            ),
            model=self.model
        )
```

#### Mock Provider (Testing/No-LLM Mode)

```python
class MockLLMProvider(LLMProvider):
    """Returns neutral responses for no-LLM operation."""
    
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        return LLMResponse(
            content="",
            usage=TokenUsage(input=0, output=0),
            model="mock"
        )
    
    async def complete_structured(
        self, 
        prompt: str, 
        schema: type[BaseModel],
        **kwargs
    ) -> BaseModel:
        # Return neutral/default instance
        return schema.model_construct()
```

### LLM Service Layer

```python
class LLMService:
    """Application-level LLM operations."""
    
    def __init__(self, provider: LLMProvider, config: LLMConfig):
        self.provider = provider
        self.config = config
    
    async def suggest_mapping_confidence(
        self,
        candidate: MappingCandidate,
        context: MappingContext
    ) -> Suggestion[ConfidenceAdjustment]:
        """Suggest confidence adjustment for mapping candidate."""
        
        # Sanitize sensitive data
        sanitized = self._sanitize_for_llm(candidate, context)
        
        prompt = self._build_mapping_prompt(sanitized)
        
        response = await self.provider.complete_structured(
            prompt=prompt,
            schema=ConfidenceAdjustmentResponse,
            system=MAPPING_SYSTEM_PROMPT
        )
        
        return Suggestion(
            value=response.adjustment,
            explanation=response.reasoning,
            confidence=response.confidence
        )
```

### Configuration

```yaml
llm:
  enabled: true
  provider: "claude"
  model: "claude-sonnet-4-20250514"
  api_key: "${ANTHROPIC_API_KEY}"
  
  # Guardrails
  max_tokens_per_request: 4000
  max_requests_per_minute: 60
  timeout_seconds: 30
  
  # Retry policy
  retry:
    max_attempts: 3
    backoff_base: 1.0
    backoff_max: 30.0
  
  # Data protection
  sanitization:
    mask_pii: true
    mask_amounts: false
    max_sample_rows: 10
```

### Data Protection

```python
class DataSanitizer:
    """Sanitize data before sending to LLM."""
    
    def sanitize_column_sample(
        self, 
        values: list[Any],
        column_type: DataType,
        config: SanitizationConfig
    ) -> list[Any]:
        if config.mask_pii and self._looks_like_pii(values):
            return ["[REDACTED]"] * len(values)
        
        # Limit sample size
        return values[:config.max_sample_rows]
    
    def _looks_like_pii(self, values: list[Any]) -> bool:
        # Check for email, SSN, phone patterns
        ...
```

## Consequences

### Positive

- **Provider flexibility** — Swap Claude for OpenAI/other easily
- **Testable** — Mock provider for unit tests
- **Graceful degradation** — No-LLM mode works fully
- **Rate limit handling** — Centralized retry logic
- **Data protection** — Sanitization before LLM exposure

### Negative

- **Abstraction cost** — Extra layer to maintain
- **Provider differences** — Not all features portable
- **Latency** — Abstraction adds minimal overhead

### Mitigation

- Keep abstraction minimal (only shared features)
- Document provider-specific limitations
- Cache LLM responses where appropriate

## References

- ANSWERING_OPEN_QUESTION.md (OQ-05: Claude initial provider)
- ADR-002: Deterministic First principle
- MODULE_CONTRACTS.md (LLMService interface)
