import json
import re
from typing import List, Dict, Any, Tuple
from ..models import Fact, FactSubject, FactObject
from ..candidate_selector import is_noise_or_boilerplate
from ..rules.qualifiers import extract_qualifiers
from .numerical_extractor import extract_quantities
from .temporal_extractor import extract_temporal_context
from ..fact_builder import build_fact

def _is_noisy_fragment(text: str) -> bool:
    """Detects OCR gibberish fragments (e.g. 'Conaas', 'peraca Tralos, fs')."""
    if not text or len(text.strip()) < 3:
        return True
    clean = text.strip()
    # Check alphanumeric ratio
    alnum = sum(1 for c in clean if c.isalnum())
    if alnum / len(clean) < 0.4:
        return True
    # Check for random character sequences without standard vowel/consonant distribution
    words = clean.split()
    for w in words:
        if len(w) > 4 and not re.search(r'[aeiouyAEIOUY]', w):
            return True
    return False

def extract_figure_facts_deterministic(
    context_dict: Dict[str, Any]
) -> Tuple[List[Fact], bool]:
    """
    Conservatively extracts facts from figure captions and text fragments.
    Strictly avoids guessing or connecting noisy OCR fragments.
    """
    caption = context_dict.get("figure_caption") or ""
    fragments = context_dict.get("figure_text_fragments") or []
    evidence_ids = context_dict.get("evidence_ids") or []
    element_id = context_dict.get("element_id")
    if element_id and element_id not in evidence_ids:
        evidence_ids.append(element_id)

    # 1. Inspect caption if clean
    if caption and not is_noise_or_boilerplate(caption):
        # Strip "Figure 1:", "Fig. 2 —", etc. prefix
        clean_cap = re.sub(r'^(?:Figure|Fig\.?)\s*\d+\s*[:\-—]\s*', '', caption, flags=re.IGNORECASE)
        # Look for explicit numerical or operational statement in caption
        quantities = extract_quantities(clean_cap)
        time_ctx = extract_temporal_context(clean_cap)
        doc_title = context_dict.get("document_title") or "Company"
        first_w = doc_title.split()[0] if doc_title else "Company"

        if quantities:
            facts: List[Fact] = []
            for q in quantities:
                facts.append(build_fact(
                    subject=FactSubject(name=first_w, type="company"),
                    predicate="metric_in_figure",
                    object_val=q,
                    time=time_ctx,
                    evidence_ids=evidence_ids,
                    confidence=0.85
                ))
            return facts, False

    # 2. Inspect text fragments
    valid_texts: List[str] = []
    for f in fragments:
        t = f.get("text", "") if isinstance(f, dict) else str(f)
        if t and not _is_noisy_fragment(t) and not is_noise_or_boilerplate(t):
            valid_texts.append(t.strip())

    # If all fragments are noisy or empty, conservatively return no facts
    if not valid_texts:
        return [], True

    # Only extract if there is an explicit unambiguous label + value pair
    # (e.g. "Revenue FY2022: ₹5,000 Cr")
    facts = []
    for txt in valid_texts:
        if ":" in txt or "—" in txt or "-" in txt:
            parts = re.split(r'[:—\-]', txt, maxsplit=1)
            label, val_part = parts[0].strip(), parts[1].strip()
            quantities = extract_quantities(val_part)
            if quantities:
                time_ctx = extract_temporal_context(label)
                for q in quantities:
                    facts.append(build_fact(
                        subject=FactSubject(name="Company", type="company"),
                        predicate=label.lower().replace(' ', '_')[:30],
                        object_val=q,
                        time=time_ctx,
                        evidence_ids=evidence_ids,
                        confidence=0.80
                    ))

    return facts, len(facts) == 0

def extract_figure_facts(context: str, llm_client: Any = None) -> List[Fact]:
    """
    Conservatively extracts facts from figure/chart contexts.
    Rejects noisy or disconnected OCR fragments without verified semantic links.
    """
    try:
        ctx_dict = json.loads(context)
    except Exception:
        ctx_dict = {}

    # 1. Deterministic figure extraction
    facts, is_ambiguous = extract_figure_facts_deterministic(ctx_dict)
    if facts and not is_ambiguous:
        return facts

    # 2. LLM enhancement if enabled and candidate has clean fragments
    if llm_client is not None:
        try:
            from ..llm.extractor import extract_with_llm
            llm_facts = extract_with_llm(context, mode="figure", client=llm_client)
            # Filter low confidence LLM figure hallucinations
            return [f for f in llm_facts if f.confidence >= 0.70]
        except Exception:
            return []

    return facts
