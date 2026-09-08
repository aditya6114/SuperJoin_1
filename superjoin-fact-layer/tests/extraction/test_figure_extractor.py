import json
from superjoin.extraction.extractors.figure_extractor import extract_figure_facts

def test_ocr_noise_in_figure_is_rejected():
    # Case 9: OCR noise fragments ("Conaas", "peraca Tralos, fs") are rejected
    context = json.dumps({
        "element_id": "fig-noise-1",
        "evidence_ids": ["fig-noise-1"],
        "figure_caption": None,
        "figure_text_fragments": [
            {"text": "Conaas"},
            {"text": "peraca Tralos, fs"},
            {"text": "----"}
        ]
    })
    facts = extract_figure_facts(context)
    assert len(facts) == 0

def test_clean_figure_caption_fact_extracted():
    context = json.dumps({
        "element_id": "fig-clean-1",
        "evidence_ids": ["fig-clean-1"],
        "document_title": "Delhivery Prospectus",
        "figure_caption": "Figure 2: Distribution Network with 93 fulfilment centres across India in FY2022",
        "figure_text_fragments": []
    })
    facts = extract_figure_facts(context)
    assert len(facts) >= 1
    assert facts[0].object.value == 93
    assert facts[0].evidence_ids == ["fig-clean-1"]
