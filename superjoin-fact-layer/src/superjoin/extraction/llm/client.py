import os
import json
from abc import ABC, abstractmethod
from typing import Type, TypeVar, Optional, Dict, Any
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

class LLMClient(ABC):
    """Minimal interface for structured LLM extraction."""
    
    @abstractmethod
    def extract_structured(self, prompt: str, context: str, schema: Type[T]) -> T:
        """Extract structured data conforming to schema from prompt and context."""
        pass

    def generate_structured(self, context: str, schema: Type[T], prompt: str) -> T:
        """Alias matching alternative caller conventions."""
        return self.extract_structured(prompt, context, schema)


class MockLLMClient(LLMClient):
    """Deterministic mock client for offline testing without network access."""
    
    def __init__(self, responses: Optional[Dict[str, Any]] = None):
        self.responses: Dict[str, Any] = responses or {}
        self.call_history = []

    def set_response(self, match_key: str, response: Any):
        """Register a canned response triggered when match_key is in prompt or context."""
        self.responses[match_key] = response

    def extract_structured(self, prompt: str, context: str, schema: Type[T]) -> T:
        self.call_history.append({"prompt": prompt, "context": context, "schema": schema})
        
        for k, v in self.responses.items():
            if k in context or k in prompt:
                if isinstance(v, schema):
                    return v
                elif isinstance(v, dict):
                    return schema.model_validate(v)
                elif isinstance(v, str):
                    return schema.model_validate_json(v)

        # Fallback: empty model
        try:
            return schema.model_validate({})
        except Exception:
            return schema.model_validate_json("{}")


# Backward compatibility alias
MockLLMProvider = MockLLMClient


class OpenAILLMClient(LLMClient):
    """Production OpenAI / Gemini-compatible structured output client."""

    def __init__(
        self,
        model_name: str = "gemini-1.5-flash",
        api_key: Optional[str] = None
    ):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")

    def extract_structured(self, prompt: str, context: str, schema: Type[T]) -> T:
        if not self.api_key:
            raise RuntimeError("No API key provided for LLM client.")

        import openai
        client = openai.OpenAI(api_key=self.api_key)
        system_msg = (
            f"{prompt}\n\n"
            f"You MUST return ONLY valid JSON matching this schema:\n"
            f"{json.dumps(schema.model_json_schema())}"
        )
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Context:\n{context}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        content = response.choices[0].message.content or "{}"
        return schema.model_validate_json(content)
