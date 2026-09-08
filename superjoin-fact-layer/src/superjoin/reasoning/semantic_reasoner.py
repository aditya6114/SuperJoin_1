import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from superjoin.extraction.models import Fact
from .models import RelationshipType
from .compatibility import ComparisonContext

# Ensure environment variables from .env are loaded
load_dotenv()


class SemanticReasoningResult(BaseModel):
    """Structured result returned by the semantic LLM reasoning layer."""
    relationship: RelationshipType = Field(..., description="Determined semantic relationship")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the determination")
    reason: str = Field(..., description="Concise summary reason")
    explanation: str = Field(..., description="Detailed explanation grounded in the facts")


class SemanticReasoner:
    """Optional semantic LLM reasoning extension for resolving complex or ambiguous cases."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gpt-4o-mini",
        enabled: bool = False,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.enabled = enabled and bool(self.api_key)

    def is_available(self) -> bool:
        """Check if LLM reasoning is configured and available."""
        return bool(self.api_key)

    def reason(
        self,
        fact_a: Fact,
        fact_b: Fact,
        context: ComparisonContext,
    ) -> Optional[SemanticReasoningResult]:
        """Perform semantic reasoning using OpenAI API with strict structured output.
        
        Returns SemanticReasoningResult if successful, or None on failure / disabled.
        """
        if not self.enabled or not self.api_key:
            return None

        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)

            system_prompt = (
                "You are an expert financial and factual reasoning engine for the Superjoin Fact Knowledge Layer.\n"
                "Your task is to analyze two extracted facts and determine their relationship.\n"
                "You MUST choose exactly one relationship from:\n"
                "- CORROBORATES: The facts make the same claim in compatible contexts and their values/assertions agree.\n"
                "- CONTRADICTS: The facts make the same claim in the same context, but assertions materially disagree.\n"
                "- CONTEXTUALLY_RECONCILED: The facts appear different, but the difference is explained by reporting period, scope, status transition, or qualifier.\n"
                "- UNRELATED: The facts refer to different entities or unrelated metrics.\n"
                "- UNRESOLVED: Insufficient evidence to safely determine the relationship.\n\n"
                "CRITICAL CONSTRAINTS:\n"
                "1. NEVER invent missing values or fabricate facts.\n"
                "2. If context is missing or uncertain, output UNRESOLVED.\n"
                "3. You must output strictly valid JSON matching this schema:\n"
                "{\n"
                '  "relationship": "CORROBORATES | CONTRADICTS | CONTEXTUALLY_RECONCILED | UNRELATED | UNRESOLVED",\n'
                '  "confidence": <float between 0.0 and 1.0>,\n'
                '  "reason": "<concise one-sentence summary>",\n'
                '  "explanation": "<detailed factual explanation>"\n'
                "}"
            )

            user_content = json.dumps({
                "fact_a": fact_a.model_dump(mode="json"),
                "fact_b": fact_b.model_dump(mode="json"),
                "signals": context.to_comparison_signals().model_dump(mode="json"),
            }, indent=2)

            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyze these two facts:\n{user_content}"},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            raw_text = response.choices[0].message.content or "{}"
            data = json.loads(raw_text)

            return SemanticReasoningResult(
                relationship=RelationshipType(data["relationship"]),
                confidence=float(data.get("confidence", 0.8)),
                reason=data.get("reason", "LLM-assisted semantic resolution"),
                explanation=data.get("explanation", "Reasoning determined via OpenAI structured semantic evaluation."),
            )

        except Exception as e:
            # Fall back gracefully to deterministic behavior
            return None
