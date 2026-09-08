import pytest
from unittest.mock import MagicMock, patch
from superjoin.extraction.models import Fact, FactSubject, FactObject, TemporalContext
from superjoin.matching.models import MatchResult, MatchSignals, MatchClassification
from superjoin.reasoning.models import RelationshipType
from superjoin.reasoning.compatibility import ComparisonContext
from superjoin.reasoning.semantic_reasoner import SemanticReasoner, SemanticReasoningResult


@pytest.fixture
def sample_context():
    fact_a = Fact(
        fact_id="f1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e1"]
    )
    fact_b = Fact(
        fact_id="f2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=600, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e2"]
    )
    signals = MatchSignals(
        subject="exact",
        predicate="exact",
        fact_type="compatible",
        value="different",
        unit="same",
        time="same",
        scope="same",
        qualifiers="exact"
    )
    match = MatchResult(
        fact_a_id="f1",
        fact_b_id="f2",
        classification=MatchClassification.SAME_CLAIM,
        confidence=0.90,
        signals=signals,
        reasons=["Different values"],
        fact_a=fact_a,
        fact_b=fact_b
    )
    return ComparisonContext(match), fact_a, fact_b


def test_semantic_reasoner_disabled_by_default(sample_context):
    ctx, fact_a, fact_b = sample_context
    reasoner = SemanticReasoner(enabled=False)
    result = reasoner.reason(fact_a, fact_b, ctx)
    assert result is None


def test_semantic_reasoner_mocked_openai_response(sample_context):
    ctx, fact_a, fact_b = sample_context
    reasoner = SemanticReasoner(api_key="mock-key", enabled=True)

    mock_chat_completion = MagicMock()
    mock_chat_completion.choices = [
        MagicMock(message=MagicMock(content='''{
            "relationship": "CONTRADICTS",
            "confidence": 0.94,
            "reason": "Different revenue figures reported for identical period.",
            "explanation": "Fact A reports 500 crore while Fact B reports 600 crore for FY2024."
        }'''))
    ]

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_chat_completion

        res = reasoner.reason(fact_a, fact_b, ctx)
        assert res is not None
        assert res.relationship == RelationshipType.CONTRADICTS
        assert res.confidence == 0.94
        assert "Different revenue figures" in res.reason


def test_semantic_reasoner_handles_exception_gracefully(sample_context):
    ctx, fact_a, fact_b = sample_context
    reasoner = SemanticReasoner(api_key="mock-key", enabled=True)

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("OpenAI API rate limit")

        res = reasoner.reason(fact_a, fact_b, ctx)
        assert res is None  # Graceful fallback
