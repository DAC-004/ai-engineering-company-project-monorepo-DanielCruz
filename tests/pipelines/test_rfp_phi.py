"""PHI screening tests. These do not prove a PostgreSQL read-back."""

from __future__ import annotations

from data.pipelines.rfp_intake.phi import screen_structure, screen_text


def test_labeled_patient_fields_are_redacted() -> None:
    source = "Clinical case summary\nPatient name: Alex Example\nDiagnosis: example condition\n"
    screened = screen_text(source)

    assert screened.detected is True
    assert "Alex Example" not in screened.text
    assert "example condition" not in screened.text
    assert "[redacted]" in screened.text


def test_workforce_condition_list_without_a_patient_label_is_not_phi() -> None:
    source = "Chronic condition management support (diabetes, hypertension) for all 800 employees."
    screened = screen_text(source)

    assert screened.detected is False
    assert screened.text == source


def test_output_screen_removes_patient_text_before_a_payload_is_saved() -> None:
    generated = {
        "summary": "Ask Claire Whitfield about the BAA. Patient name: Alex Example. Diagnosis: example condition.",
        "aspects": ["Ask Claire Whitfield about the BAA."],
    }
    screened, detected, _blocked = screen_structure(generated)

    assert detected is True
    assert isinstance(screened, dict)
    assert "Alex Example" not in screened["summary"]
    assert "example condition" not in screened["summary"]
    assert screened["aspects"] == ["Ask Claire Whitfield about the BAA."]
