import re
from typing import List, Dict, Any, Optional, Tuple
from ..models import FactSubject, FactObject, TemporalContext
from ..rules.predicates import (
    map_verb_to_predicate,
    PREDICATE_OPERATES,
    PREDICATE_OWNS,
    PREDICATE_ACQUIRED,
    PREDICATE_LAUNCHED,
    PREDICATE_PROVIDES,
    PREDICATE_SERVES,
    PREDICATE_APPOINTED_AS,
    PREDICATE_RESIGNED_AS,
    PREDICATE_LOCATED_AT,
    PREDICATE_FLOOR_AREA,
    PREDICATE_REVENUE,
    PREDICATE_PROFIT,
    PREDICATE_LOSS,
    PREDICATE_EBITDA,
)
from ..rules.qualifiers import extract_qualifiers
from .numerical_extractor import extract_quantities
from .temporal_extractor import extract_temporal_context

PRONOUNS = {"it", "its", "they", "their", "he", "his", "she", "her"}

def _resolve_subject(
    candidate_subject: str, 
    context_dict: Dict[str, Any]
) -> Tuple[Optional[FactSubject], Optional[str]]:
    """
    Resolves the subject entity from candidate text or surrounding context.
    Returns (FactSubject, uncertainty_reason).
    Strictly avoids hallucinating a subject when unresolvable.
    """
    clean_subj = candidate_subject.strip()
    clean_lower = clean_subj.lower()

    # If it's a pronoun like "it", "they", "he", "she"
    if clean_lower in PRONOUNS:
        # Check if preceding section header or document title establishes the company
        header = context_dict.get("preceding_section_header")
        doc_title = context_dict.get("document_title")

        # If preceding section header has a proper noun
        if header and len(header.split()) <= 5 and not any(p in header.lower() for p in ("introduction", "overview", "financials", "table")):
            return FactSubject(name=header.strip(), type="company"), None
        elif doc_title and ("prospectus" in doc_title.lower() or "report" in doc_title.lower()):
            # Extract main entity name from title if clear (e.g. "Delhivery Prospectus" -> "Delhivery")
            first_word = doc_title.split()[0]
            if first_word.isalnum() and len(first_word) > 2:
                return FactSubject(name=first_word, type="company"), None
        
        return None, f"Subject could not be established for pronoun '{clean_subj}'."

    # If subject is generic like "The company" or "The group"
    if clean_lower in ("the company", "the firm", "the group", "company"):
        doc_title = context_dict.get("document_title") or ""
        header = context_dict.get("preceding_section_header") or ""
        # Look for explicit entity name in context
        if doc_title and not doc_title.lower().startswith("document"):
            name = doc_title.split()[0]
            if len(name) > 2 and name.isalpha():
                return FactSubject(name=name, type="company"), None
        return FactSubject(name="Company", type="company"), None

    # Specific named entity
    is_person = any(honorific in clean_subj for honorific in ("Mr.", "Ms.", "Mrs.", "Dr."))
    subj_type = "person" if is_person else "company"
    return FactSubject(name=clean_subj, type=subj_type), None


def extract_semantic_relations(
    text: str, 
    context_dict: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Extracts controlled semantic relation tuples:
    (subject, predicate, object, time, qualifiers, confidence)
    and any extraction uncertainties encountered.
    """
    if not text:
        return [], []

    relations: List[Dict[str, Any]] = []
    uncertainties: List[str] = []
    quals = extract_qualifiers(text)

    # 1. Appointments & Resignations
    # "Person X was appointed director in 2021."
    # "Person X resigned as director in 2024."
    appt_pattern = re.compile(
        r'([A-Z][A-Za-z\s\.\-]+?)\s+(?:was\s+)?(appointed(?:\s+as)?|resigned(?:\s+as)?|stepped\s+down\s+as)\s+([A-Za-z\s]+?)(?:\s+(?:in|on|effective)\s+([A-Za-z0-9\s,\-]+))?[\.\,]',
        re.IGNORECASE
    )
    for match in appt_pattern.finditer(text):
        person_name = match.group(1).strip()
        verb = match.group(2).strip()
        role = match.group(3).strip()
        raw_time = match.group(4)

        time_ctx = extract_temporal_context(raw_time if raw_time else text)
        predicate = PREDICATE_APPOINTED_AS if "appointed" in verb.lower() else PREDICATE_RESIGNED_AS

        relations.append({
            "subject": FactSubject(name=person_name, type="person"),
            "predicate": predicate,
            "object": FactObject(value_type="text", value=role),
            "time": time_ctx,
            "qualifiers": quals,
            "confidence": 0.95,
            "fact_type": "event"
        })

    # 2. Location / Address (Preserves verbatim address as required by Case 3)
    # "Subject is located at Air Cargo Logistics Center, IGI Airport, New Delhi."
    loc_pattern = re.compile(
        r'([A-Z][A-Za-z0-9\s\.\-]+?)\s+(?:is\s+)?(located\s+at|headquartered\s+at|situated\s+at)\s+([A-Za-z0-9\s\,\.\-]+)[\.\,]?',
        re.IGNORECASE
    )
    for match in loc_pattern.finditer(text):
        raw_subj = match.group(1).strip()
        address = match.group(3).strip().rstrip('.').rstrip(',')
        subj, err = _resolve_subject(raw_subj, context_dict)
        if not subj:
            uncertainties.append(err or "Unresolvable subject in location statement.")
            continue
        relations.append({
            "subject": subj,
            "predicate": PREDICATE_LOCATED_AT,
            "object": FactObject(value_type="text", value=address),
            "time": extract_temporal_context(text),
            "qualifiers": quals,
            "confidence": 0.92,
            "fact_type": "relationship"
        })

    # 3. Compound operational sentences (Case 6: Multiple facts in one sentence)
    # "Company operates 93 fulfilment centres covering 6.25 million square feet."
    compound_op = re.compile(
        r'([A-Z][A-Za-z0-9\s\.\-]+?|\bIt\b|\bThe\s+company\b)\s+operates\s+(\d[\d,]*)\s+([A-Za-z\s]+?)\s+covering\s+(\d+(?:\.\d+)?)\s*(million|lakh|crore)?\s*(square\s*feet|sq\s*ft)',
        re.IGNORECASE
    )
    compound_match = compound_op.search(text)
    if compound_match:
        raw_subj = compound_match.group(1)
        count_val = int(compound_match.group(2).replace(',', ''))
        unit_centres = compound_match.group(3).strip()
        area_raw = compound_match.group(4)
        area_val = float(area_raw) if '.' in area_raw else int(area_raw)
        area_scale = compound_match.group(5)
        area_unit = compound_match.group(6)

        subj, err = _resolve_subject(raw_subj, context_dict)
        if not subj:
            uncertainties.append(err or "Subject unresolvable in compound operational statement.")
        else:
            time_ctx = extract_temporal_context(text)
            # Fact 1: operates count centres
            relations.append({
                "subject": subj,
                "predicate": PREDICATE_OPERATES,
                "object": FactObject(value_type="quantity", value=count_val, unit=unit_centres),
                "time": time_ctx,
                "qualifiers": quals,
                "confidence": 0.95,
                "fact_type": "numerical"
            })
            # Fact 2: floor area
            relations.append({
                "subject": subj,
                "predicate": PREDICATE_FLOOR_AREA,
                "object": FactObject(value_type="number", value=area_val, scale=area_scale, unit=area_unit or "square feet"),
                "time": time_ctx,
                "qualifiers": quals,
                "confidence": 0.94,
                "fact_type": "numerical"
            })

    # 4. Standard Operational / Corporate Verbs (operates, owns, acquired, launched, provides, serves)
    if not compound_match:
        verb_pattern = re.compile(
            r'([A-Z][A-Za-z0-9\s\.\-]+?|\bIt\b|\bThe\s+company\b)\s+(operates|owns|acquired|launched|provides|serves)\s+([^\.\;]+)',
            re.IGNORECASE
        )
        for match in verb_pattern.finditer(text):
            raw_subj = match.group(1)
            verb = match.group(2)
            predicate = map_verb_to_predicate(verb) or verb.lower()
            remainder = match.group(3).strip()

            subj, err = _resolve_subject(raw_subj, context_dict)
            if not subj:
                uncertainties.append(err or f"Subject unresolvable for predicate '{predicate}'.")
                continue

            time_ctx = extract_temporal_context(text)
            # Check if remainder contains quantities
            extracted_objs = extract_quantities(remainder)
            if extracted_objs:
                for obj in extracted_objs:
                    relations.append({
                        "subject": subj,
                        "predicate": predicate,
                        "object": obj,
                        "time": time_ctx,
                        "qualifiers": quals,
                        "confidence": 0.90,
                        "fact_type": "numerical"
                    })
            else:
                relations.append({
                    "subject": subj,
                    "predicate": predicate,
                    "object": FactObject(value_type="text", value=remainder),
                    "time": time_ctx,
                    "qualifiers": quals,
                    "confidence": 0.88,
                    "fact_type": "relationship"
                })

    # 5. Financial reporting statements in prose
    # Pattern A: "The company reported revenue of ₹3,057.5 million for FY2021."
    fin_pattern = re.compile(
        r'([A-Z][A-Za-z0-9\s\.\-]+?|\bThe\s+company\b|\bIt\b)\s+(?:reported|generated|had|achieved)\s+(?:a\s+)?(revenue|profit|net\s+profit|loss|net\s+loss|ebitda)\s+of\s+([^\.\;]+)',
        re.IGNORECASE
    )
    for match in fin_pattern.finditer(text):
        raw_subj = match.group(1)
        metric = match.group(2).lower()
        remainder = match.group(3).strip()

        subj, err = _resolve_subject(raw_subj, context_dict)
        if not subj:
            uncertainties.append(err or f"Subject unresolvable for metric '{metric}'.")
            continue

        time_ctx = extract_temporal_context(remainder)
        extracted_objs = extract_quantities(remainder)
        if extracted_objs:
            for obj in extracted_objs:
                pred = PREDICATE_REVENUE if "revenue" in metric else (
                    PREDICATE_PROFIT if "profit" in metric else (
                        PREDICATE_LOSS if "loss" in metric else PREDICATE_EBITDA
                    )
                )
                relations.append({
                    "subject": subj,
                    "predicate": pred,
                    "object": obj,
                    "time": time_ctx,
                    "qualifiers": quals,
                    "confidence": 0.95,
                    "fact_type": "numerical"
                })

    # Pattern B: "Revenue was / stood at / reached ₹50 crore in 2022."
    fin_was_pattern = re.compile(
        r'\b(revenue|profit|net\s+profit|loss|net\s+loss|ebitda)\s+(?:was|reached|stood\s+at|is)\s+([^\.\;]+)',
        re.IGNORECASE
    )
    for match in fin_was_pattern.finditer(text):
        metric = match.group(1).lower()
        remainder = match.group(2).strip()

        # Subject defaults to context entity or Company
        subj, _ = _resolve_subject("The company", context_dict)
        if not subj:
            subj = FactSubject(name="Company", type="company")

        time_ctx = extract_temporal_context(remainder)
        extracted_objs = extract_quantities(remainder)
        if extracted_objs:
            for obj in extracted_objs:
                pred = PREDICATE_REVENUE if "revenue" in metric else (
                    PREDICATE_PROFIT if "profit" in metric else (
                        PREDICATE_LOSS if "loss" in metric else PREDICATE_EBITDA
                    )
                )
                relations.append({
                    "subject": subj,
                    "predicate": pred,
                    "object": obj,
                    "time": time_ctx,
                    "qualifiers": quals,
                    "confidence": 0.92,
                    "fact_type": "numerical"
                })

    return relations, uncertainties
