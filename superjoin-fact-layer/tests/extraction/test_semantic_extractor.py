from superjoin.extraction.extractors.semantic_extractor import extract_semantic_relations

def test_extract_appointments_and_resignations():
    # Case 2: Status change over time
    text_appt = "Dr. Rajesh Sharma was appointed director in 2021."
    rel_appt, _ = extract_semantic_relations(text_appt, {})
    assert len(rel_appt) == 1
    assert rel_appt[0]["subject"].name == "Dr. Rajesh Sharma"
    assert rel_appt[0]["subject"].type == "person"
    assert rel_appt[0]["predicate"] == "appointed_as"
    assert rel_appt[0]["object"].value == "director"
    assert rel_appt[0]["time"].time_type == "calendar_year"
    assert rel_appt[0]["time"].value == "2021"

    text_res = "Dr. Rajesh Sharma resigned as director in 2024."
    rel_res, _ = extract_semantic_relations(text_res, {})
    assert len(rel_res) == 1
    assert rel_res[0]["predicate"] == "resigned_as"
    assert rel_res[0]["time"].value == "2024"

def test_extract_differently_written_addresses():
    # Case 3: Addresses preserved verbatim
    t1 = "Delhivery is located at Air Cargo Logistics Center, IGI Airport, New Delhi."
    r1, _ = extract_semantic_relations(t1, {})
    assert len(r1) == 1
    assert r1[0]["object"].value == "Air Cargo Logistics Center, IGI Airport, New Delhi"

    t2 = "Delhivery is located at Air Cargo Logistics Centre, Indira Gandhi International Airport."
    r2, _ = extract_semantic_relations(t2, {})
    assert len(r2) == 1
    assert r2[0]["object"].value == "Air Cargo Logistics Centre, Indira Gandhi International Airport"

def test_unresolvable_subject_returns_uncertainty():
    # Case 14: Missing subject - "It operates 50 facilities." without context
    text = "It operates 50 facilities."
    rels, uncertainties = extract_semantic_relations(text, {})
    assert len(rels) == 0
    assert len(uncertainties) > 0
    assert "could not be established" in uncertainties[0] or "unresolvable" in uncertainties[0].lower()
