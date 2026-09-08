# Superjoin Fact Knowledge Layer

A multi-module enterprise document intelligence system designed to ingest complex multi-format business documents (PDFs, prospectuses, annual reports) and extract atomic, evidence-grounded facts with complete provenance.

---

## Architecture Overview

```text
[ Document PDFs ]
       ↓
Module 1: Ingestion & Canonicalization (src/superjoin/ingestion/)
  - Docling Parsing & Layout Analysis
  - Geometry-based Reading Order Resolution
  - Header, Footer, and Table Normalization
       ↓
[ CanonicalDocument JSON ] (data/parsed/)
       ↓
Module 2: Hybrid Fact Extraction Layer (src/superjoin/extraction/)
  - Candidate Selection (Deterministic heuristic filtering)
  - Targeted Context Construction (Headers, hierarchy, surroundings)
  - Three Complementary Extraction Layers:
      1. Deterministic Extraction (Tables, Quantities, Physical Units, Currencies)
      2. Conventional Semantic NLP (Controlled predicates, relation templates)
      3. LLM Enhancement (Complex prose & ambiguous language)
  - Strict Schema & Evidence Validation (All evidence IDs grounded in CanonicalDocument)
  - Conservative Document-Level Deduplication
       ↓
[ FactExtractionResult JSON ] (data/facts/)
```

---

## Module 1: Document Ingestion & Canonicalization

Module 1 is responsible for parsing arbitrary PDF documents and transforming raw parser representations into a normalized, deterministic, provenance-preserving `CanonicalDocument`.

- **Package**: `src/superjoin/ingestion/`
- **Output Models**: `CanonicalDocument`, `CanonicalPage`, `CanonicalElement`, `CanonicalTable`, `CanonicalFigure`
- **Provenance**: Every element preserves bounding boxes (`bbox`) and `evidence_ids`.

---

## Module 2: Hybrid Fact Extraction Layer

### 1. Purpose & Core Objective
Module 2 converts a `CanonicalDocument` into meaningful, atomic, structured, evidence-grounded facts.

**The Central Invariant:**
> **EVERY VALID FACT MUST BE TRACEABLE TO ACTUAL SOURCE EVIDENCE.**
> If the system cannot confidently establish a fact from the provided document evidence, it must return uncertainty or skip the extraction. Never hallucinate a fact merely because the statement appears plausible.

### 2. Why the Architecture is Hybrid
Module 2 does **not** rely solely on an LLM. Instead, it implements three complementary layers:
1. **Deterministic Extraction**: High-confidence parsing of structured tables, numerical quantities, physical units, and currencies.
2. **Conventional Semantic NLP**: Controlled predicate mappings and relation templates for operational and corporate statements.
3. **LLM Assistance**: Reserved as an enhancement layer for complex prose or structural ambiguity.

#### Architectural Tradeoff:
- **Deterministic extraction** provides total reproducibility, zero hallucinations, fast execution, zero API costs, and robust debugging.
- **Conventional semantic NLP** extracts well-defined entity relations and compound claims deterministically.
- **LLM assistance** provides high semantic recall for difficult, nuanced, or irregular natural language statements.
- **Strict Evidence Validation** ensures that *no component*—neither heuristics nor the LLM—is permitted to bypass source grounding.

### 3. What Deterministic Extraction Handles
- **Numerical Quantities**: Integers, decimals, percentages, scaled numbers (million, billion, crore, lakh), currencies (₹, INR, $, USD, €, EUR), and physical units (guards, fulfilment centres, sq ft).
- **Semantics Preservation**: Preserves comparisons (`greater_than` for "over 1,607") and approximations (`approximate` for "approximately 5 million") without lossy conversions.
- **Temporal Expressions**: Calendar years (`2023`), fiscal years (`FY2022`, `FY 2021-22`), quarters (`Q3 FY2025`), specific dates (`March 31, 2024`), and as-of dates.
- **Structured Tables**: Direct extraction of table row-column intersections, associating row/column temporal headers with cell values.

### 4. What Conventional Semantic NLP Handles
- Controlled relation extraction using a curated predicate vocabulary in `src/superjoin/extraction/rules/predicates.py`:
  - `operates`, `owns`, `acquired`, `launched`, `provides`, `serves`, `located_at`, `floor_area`
  - Governance & roles: `appointed_as`, `resigned_as`
  - Financial metrics: `revenue`, `profit`, `loss`, `ebitda`, `growth`, `margin`
- Compound sentence decomposition: splits multi-fact sentences into atomic claims (e.g., "Company operates 93 fulfilment centres covering 6.25 million square feet" → two atomic facts).
- Conservative subject resolution: identifies proper nouns from local context; flags unresolvable pronouns ("It operates 50 facilities") as uncertain rather than guessing.

### 5. When the LLM is Used
The LLM is an enhancement layer, not the entire pipeline. It is invoked **only** when:
- Deterministic extraction returns no high-confidence facts for a fact-bearing candidate.
- Prose contains complex, multi-clause semantic statements that exceed rule templates.
- A table structure is irregular or non-standard.
- A figure has ambiguous layout requiring semantic interpretation.

If deterministic extraction produces a high-confidence fact, **zero LLM calls are made**.

### 6. Fact Schema
Every fact conforms to the strongly-typed `Fact` model:

```python
class Fact(BaseModel):
    fact_id: str                      # Unique UUID
    fact_type: str                    # "numerical" | "semantic" | "event" | "attribute" | "relationship"
    subject: FactSubject              # Entity (name: str, type: str)
    predicate: str                    # Controlled predicate (e.g. 'operates', 'revenue', 'appointed_as')
    object: FactObject                # Typed value (number, currency, percentage, quantity, text)
    time: TemporalContext             # Time context (fiscal_year, calendar_year, quarter, as_of_date, unknown)
    scope: Optional[str]              # Geographic or organizational scope (e.g. 'India', 'consolidated')
    qualifiers: List[str]             # Semantic qualifiers ('approximately', 'over', 'unaudited', etc.)
    confidence: float                 # Extraction confidence (0.0 to 1.0)
    evidence_ids: List[str]           # Canonical element IDs strictly grounded in the document
```

### 7. Evidence & Provenance
Every valid fact retains a non-empty list of `evidence_ids`.
- `validators.py` verifies every `evidence_id` against the set of all element and evidence IDs present in the `CanonicalDocument`.
- Fabricated, inferred, or hallucinated evidence IDs are strictly rejected.
- When an identical claim appears in multiple locations (e.g., summary, body, table), the deduplicator consolidates the claim into a single representative fact and merges all supporting `evidence_ids`.

### 8. Table Extraction & Unit Inheritance
- **Caption-level unit inheritance**: If a table specifies `(₹ in million)` in its caption, all numerical cell facts automatically inherit `currency="₹"` and `scale="million"`.
- **Temporal row/column binding**: Identifies whether rows or columns represent time intervals and anchors the cell value to that temporal context.
- **Ambiguous tables**: If column headers are blank, corrupt, or missing, the extractor marks the candidate as **uncertain** rather than inventing column meanings.

### 9. Temporal Extraction Rules
- Detects explicit calendar years, fiscal years, quarters, dates, and ranges.
- **Never infer missing dates**: If the source text states `"Revenue was ₹500 million"` with no time period established, `time_type="unknown"` and `value=None`. The publication year is never assumed.

### 10. Failure & Uncertainty Handling
Extraction failures and uncertainties are first-class, observable outputs in `FactExtractionResult`:
- `facts`: Validated, deduplicated, evidence-grounded facts.
- `uncertain_candidates`: Records of statements with unresolvable subjects, ambiguous table layouts, or unclear figure text.
- `failed_candidates`: Candidates that failed extraction or schema validation, detailing the exact reason.
- `statistics`: Metrics tracking candidate counts, extracted facts, rejected facts, and uncertainties.

### 11. LLM-Off Mode
Module 2 fully supports running with the LLM disabled (`--no-llm` flag or `FactExtractionService(llm_enabled=False)`).
- When the LLM is turned off, deterministic parsing and semantic rules extract all structured table data, quantities, and relation templates.
- Ambiguous candidates are cleanly recorded in `uncertain_candidates` with explanatory reasons rather than failing the pipeline.
- Ensures 100% offline reproducibility and eliminates test flakiness.

### 12. Strict Boundaries & Limitations
Module 2 strictly avoids:
- Cross-document entity resolution (e.g., deciding whether two slightly different company addresses are the same location).
- Contradiction reconciliation (if a document has conflicting revenue values across sections, both are extracted).
- Final unit normalization (converting crore to millions belongs to Module 3).
- Knowledge graph synthesis.

---

## Supported Critical Edge Cases

| Edge Case | Description | Handled By |
|---|---|---|
| **1. Same Metric, Different Time** | Revenue in FY2022 vs FY2023 extracted as separate distinct facts | `temporal_extractor` & `deduplicator` |
| **2. Status Change Over Time** | Person appointed in 2021, resigned in 2024 preserved as distinct event facts | `semantic_extractor` (`appointed_as`, `resigned_as`) |
| **3. Differently Written Addresses** | Preserves verbatim addresses without premature equivalence | `semantic_extractor` (`located_at`) |
| **4. Different Units** | ₹5 crore, ₹50 million, ₹50,000,000 preserved in original source scale | `numerical_extractor` |
| **5. Approximate Values** | "over 1,607", "approximately 5 million" preserve comparison qualifiers | `numerical_extractor` (`qualifier="greater_than"`, etc.) |
| **6. Multiple Facts in One Sentence** | "Operates 93 centres covering 6.25 million sq ft" splits into 2 atomic facts | `semantic_extractor` |
| **7. Table Unit in Caption** | `Revenue (₹ in million)` propagates currency and scale to cells | `table_extractor` |
| **8. Ambiguous Tables** | Missing or corrupted headers marked uncertain without guessing | `table_extractor` (`is_ambiguous=True`) |
| **9. OCR / Figure Noise** | Non-alphanumeric noise ("Conaas", "peraca Tralos, fs") filtered out | `figure_extractor` (`_is_noisy_fragment`) |
| **10. Repeated Headers/Footers** | Page numbers, headers, and footers excluded from candidate selection | `candidate_selector` |
| **11. PDF vs Printed Page** | Tracks `pdf_page_number` and `printed_page_number` alongside evidence IDs | `context_builder` & `service` |
| **12. Qualified Claims** | "unaudited", "pro forma", "estimated" preserved in fact qualifiers | `rules/qualifiers.py` |
| **13. Missing Time** | Missing time yields `unknown` time context without date inference | `temporal_extractor` |
| **14. Missing Subject** | "It operates 50 facilities" marked uncertain if pronoun is unresolvable | `semantic_extractor` |
| **15. Internal Disagreement** | Differing values in same document are both extracted if evidence-grounded | `service` & `validators` |

---

## Directory Structure

```text
src/superjoin/extraction/
    __init__.py
    models.py                   # Fact, FactSubject, FactObject, TemporalContext, FactExtractionResult
    service.py                  # FactExtractionService (hybrid orchestration)
    candidate_selector.py       # Heuristic candidate filtering
    context_builder.py          # Local targeted context construction
    fact_builder.py             # Fact assembly and validation helper
    deduplicator.py             # Conservative local document deduplication
    validators.py               # Strict schema and evidence grounding validation
    cli.py                      # CLI entrypoint with --inspect and --no-llm options

    extractors/
        __init__.py
        numerical_extractor.py  # Quantities, scales, units, currencies, comparisons
        temporal_extractor.py   # Fiscal years, calendar years, dates, quarters
        semantic_extractor.py   # Relation extraction, subject resolution, atomic splitting
        table_extractor.py      # Deterministic table parsing and unit inheritance
        figure_extractor.py     # Conservative figure and chart extraction
        text_extractor.py       # Hybrid text extraction

    rules/
        __init__.py
        predicates.py           # Controlled canonical predicate vocabulary
        qualifiers.py           # Qualifier detection (approximations, accounting, comparisons)
        patterns.py             # Compiled regex patterns for numbers, currencies, dates

    llm/
        __init__.py
        client.py               # Minimal LLMClient interface, MockLLMClient, OpenAILLMClient
        extractor.py            # Structured LLM extractor with evidence grounding
        prompts.py              # Strict system prompts for text, table, and figure extraction
        provider.py             # Backward-compatibility bridge
```

---

## How to Run

### 1. Ingestion (Module 1)
Parse raw PDFs into canonical JSON:
```bash
python scripts/parse_documents.py --input data/input --output data/parsed
```

### 2. Fact Extraction (Module 2)

#### Run in Deterministic / LLM-Off Mode (Recommended for testing & offline reproducibility):
```bash
python scripts/extract_facts.py --input data/parsed --output data/facts --no-llm
```

#### Inspect Extracted Facts:
To inspect candidate statistics, extraction metrics, and a sample of validated facts in the terminal:
```bash
python scripts/extract_facts.py --input data/parsed/01-delhivery-prospectus-2022-excerpt-0d7e71.json --no-llm --inspect
```

#### Run with LLM Enabled:
```bash
python scripts/extract_facts.py --input data/parsed --output data/facts --model gemini-1.5-flash
```

---

## Running Tests

Execute the comprehensive test suite (66 tests covering ingestion, extraction, extractors, rules, edge cases, deduplication, and service orchestration):

```bash
pytest -v
# Or via virtual environment
.venv\Scripts\pytest -v
```
