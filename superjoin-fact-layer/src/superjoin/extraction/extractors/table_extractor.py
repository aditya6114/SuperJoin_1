import re
import json
from typing import List, Dict, Any, Optional, Tuple

from ..models import Fact, FactSubject, FactObject, TemporalContext
from ..rules.predicates import map_metric_to_predicate
from ..rules.qualifiers import extract_qualifiers
from ..rules.patterns import (
    CURRENCY_PATTERN,
    CURRENCY_MAP,
    SCALE_PATTERN,
    SCALE_MAP,
    PERCENTAGE_PATTERN,
    FISCAL_YEAR_PATTERN,
    CALENDAR_YEAR_PATTERN,
    NUMBER_REGEX,
)
from ..fact_builder import build_fact
from .temporal_extractor import extract_temporal_context

def _extract_table_level_units(caption: str) -> Dict[str, Optional[str]]:
    """Extracts currency, scale, and qualifiers defined in table caption."""
    units: Dict[str, Optional[str]] = {
        "currency": None,
        "scale": None,
        "unit": None
    }
    if not caption:
        return units

    curr_match = CURRENCY_PATTERN.search(caption)
    if curr_match:
        raw_c = curr_match.group(0).lower()
        units["currency"] = CURRENCY_MAP.get(raw_c, curr_match.group(0))

    scale_match = SCALE_PATTERN.search(caption)
    if scale_match:
        raw_s = scale_match.group(0).lower()
        units["scale"] = SCALE_MAP.get(raw_s, raw_s)

    if "%" in caption or "percent" in caption.lower():
        units["unit"] = "%"

    return units

def extract_table_facts_deterministic(
    context_dict: Dict[str, Any]
) -> Tuple[List[Fact], bool]:
    """
    Deterministically extracts structured facts from table headers and rows.
    Returns (facts, is_ambiguous).
    If headers/rows are ambiguous or corrupted, returns ([], True).
    """
    headers = context_dict.get("table_headers") or []
    rows = context_dict.get("table_rows") or []
    caption = context_dict.get("table_caption") or ""
    evidence_ids = context_dict.get("evidence_ids") or []
    element_id = context_dict.get("element_id")
    if element_id and element_id not in evidence_ids:
        evidence_ids.append(element_id)

    if not rows or not isinstance(rows, list):
        return [], True

    # Check for ambiguous or blank headers
    clean_headers = [str(h).strip() for h in headers] if headers else []
    if not clean_headers or all(h == "" or h.startswith("Unnamed") for h in clean_headers):
        # Header is missing or corrupt
        return [], True

    # Count blank headers: if more than 50% blank, mark ambiguous
    blank_headers = sum(1 for h in clean_headers if not h or h == "-")
    if blank_headers > len(clean_headers) / 2:
        return [], True

    # Extract table-level units from caption
    caption_units = _extract_table_level_units(caption)
    caption_quals = extract_qualifiers(caption)
    caption_time = extract_temporal_context(caption)

    # Determine default subject
    doc_title = context_dict.get("document_title") or ""
    subj_name = "Company"
    if doc_title and not doc_title.lower().startswith("document"):
        first_w = doc_title.split()[0]
        if len(first_w) > 2 and first_w.isalnum():
            subj_name = first_w
    subject = FactSubject(name=subj_name, type="company")

    facts: List[Fact] = []

    # Check Table Orientation:
    # Orientation A: Standard table (Col 0 is Year/Time, remaining cols are metrics)
    # e.g. Year | Revenue | Growth
    col0_header_lower = clean_headers[0].lower()
    is_col0_time_header = any(t in col0_header_lower for t in ("year", "period", "date", "fy"))
    
    # Also inspect row[0] cell to see if values in col 0 are dates
    col0_sample_values = [str(r[0]).strip() for r in rows if len(r) > 0]
    col0_looks_like_time = any(
        FISCAL_YEAR_PATTERN.search(v) or CALENDAR_YEAR_PATTERN.search(v)
        for v in col0_sample_values[:3]
    )

    if is_col0_time_header or col0_looks_like_time:
        # Standard: row-level temporal context, column-level predicates
        for row in rows:
            if not isinstance(row, list) or len(row) < 2:
                continue
            row_str = [str(c).strip() for c in row]
            time_val = row_str[0]
            row_time = extract_temporal_context(time_val)
            if row_time.time_type == "unknown" and caption_time.time_type != "unknown":
                row_time = caption_time

            for col_idx in range(1, min(len(clean_headers), len(row_str))):
                col_name = clean_headers[col_idx]
                cell_val = row_str[col_idx].replace(',', '').strip()
                if not cell_val or cell_val in ("-", "—", "N/A", "NA", "null"):
                    continue

                predicate = map_metric_to_predicate(col_name)
                
                # Parse numeric cell
                is_pct = "%" in cell_val or "%" in col_name or caption_units["unit"] == "%"
                num_clean = cell_val.replace('%', '').strip()

                num_match = re.match(r'^[-+]?\d+(\.\d+)?$', num_clean)
                if num_match:
                    val = float(num_clean) if '.' in num_clean else int(num_clean)
                    val_type = "percentage" if is_pct else ("currency" if caption_units["currency"] else "number")
                    
                    fact_obj = FactObject(
                        value_type=val_type,
                        value=val,
                        unit="%" if is_pct else None,
                        currency=caption_units["currency"] if not is_pct else None,
                        scale=caption_units["scale"] if not is_pct else None
                    )

                    facts.append(build_fact(
                        subject=subject,
                        predicate=predicate,
                        object_val=fact_obj,
                        time=row_time,
                        qualifiers=caption_quals,
                        evidence_ids=evidence_ids,
                        confidence=0.95
                    ))

        return facts, False

    # Orientation B: Transposed table (Row labels in Col 0, Columns are Years)
    # e.g. Metric | 2021 | 2022
    headers_look_like_time = any(
        FISCAL_YEAR_PATTERN.search(h) or CALENDAR_YEAR_PATTERN.search(h)
        for h in clean_headers[1:]
    )
    if headers_look_like_time:
        for row in rows:
            if not isinstance(row, list) or len(row) < 2:
                continue
            metric_label = str(row[0]).strip()
            if not metric_label or metric_label in ("-", "—"):
                continue
            predicate = map_metric_to_predicate(metric_label)

            for col_idx in range(1, min(len(clean_headers), len(row))):
                col_time_str = clean_headers[col_idx]
                col_time = extract_temporal_context(col_time_str)
                cell_val = str(row[col_idx]).replace(',', '').strip()
                if not cell_val or cell_val in ("-", "—", "N/A", "null"):
                    continue

                is_pct = "%" in cell_val or "%" in metric_label or caption_units["unit"] == "%"
                num_clean = cell_val.replace('%', '').strip()
                num_match = re.match(r'^[-+]?\d+(\.\d+)?$', num_clean)
                if num_match:
                    val = float(num_clean) if '.' in num_clean else int(num_clean)
                    val_type = "percentage" if is_pct else ("currency" if caption_units["currency"] else "number")
                    
                    fact_obj = FactObject(
                        value_type=val_type,
                        value=val,
                        unit="%" if is_pct else None,
                        currency=caption_units["currency"] if not is_pct else None,
                        scale=caption_units["scale"] if not is_pct else None
                    )

                    facts.append(build_fact(
                        subject=subject,
                        predicate=predicate,
                        object_val=fact_obj,
                        time=col_time,
                        qualifiers=caption_quals,
                        evidence_ids=evidence_ids,
                        confidence=0.95
                    ))

        return facts, False

    # If neither orientation matches cleanly, mark ambiguous
    return [], True

def extract_table_facts(context: str, llm_client: Any = None) -> List[Fact]:
    """
    Extracts facts from table context using hybrid extraction:
    1. Deterministic table parser (primary, high confidence)
    2. Fallback to LLM if ambiguous and LLM is enabled
    """
    try:
        ctx_dict = json.loads(context)
    except Exception:
        ctx_dict = {}

    # 1. Deterministic Extraction
    facts, is_ambiguous = extract_table_facts_deterministic(ctx_dict)
    if facts and not is_ambiguous:
        return facts

    # 2. If ambiguous and LLM is available, delegate to LLM
    if is_ambiguous and llm_client is not None:
        try:
            from ..llm.extractor import extract_with_llm
            return extract_with_llm(context, mode="table", client=llm_client)
        except Exception:
            return []

    return facts
