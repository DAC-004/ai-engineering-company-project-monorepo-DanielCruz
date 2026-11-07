"""Pure generated-prose boundary. No app, broker, or transport calls."""

from __future__ import annotations

import json
from datetime import date

from agents.financial_close.generation import build_write_messages, parse_write_payload, text_is_grounded
from agents.financial_close.privacy import is_safe_prose
from agents.financial_close.seed import write_fixtures
from agents.financial_close.serialize import (
    allowed_number_catalog,
    evidence_sentences,
    known_reference_catalog,
    number_catalogs_by_line,
)
from agents.financial_close.tools import build_facts

_UNCERTAINTY_FRAME = "Hypothesis (not proved causality):"


def test_unsupported_model_amount_is_rejected() -> None:
    payload = json.dumps(
        {"hypotheses": {"us_laboratory": "Hypothesis: costs changed by 987654321 USD."}, "summary": []}
    )
    hypotheses, summary = parse_write_payload(payload, {"us_laboratory"})
    assert hypotheses == {}
    assert summary == []


def test_unlabelled_fictional_name_is_rejected_from_comments_or_prose() -> None:
    assert is_safe_prose("Jordan Hale requires individual follow up.") is False


def test_ordinary_financial_prose_is_not_blocked_by_two_word_english() -> None:
    summary = (
        "Close for 2026-10 is incomplete. Consolidated USD uses verified amounts only "
        "and does not treat missing software as zero. Uncertain ledger records are listed by entry_id only."
    )
    assert is_safe_prose(summary) is True


def test_grounded_allowlisted_staff_name_is_accepted() -> None:
    assert is_safe_prose("Tom Callahan approved the October close.") is True


def test_complete_numeric_tokens_reject_concatenation_sign_and_decimal_changes() -> None:
    allowed = {"1", "19.26", "48150", "18.00"}
    assert text_is_grounded("Laboratory verified actual is 48150.", allowed) is True
    assert text_is_grounded("Laboratory cost increased by 987654321.", allowed) is False
    assert text_is_grounded("Invented concatenation 111111.", allowed) is False
    assert text_is_grounded("Sign-changed actual -48150.", allowed) is False
    assert text_is_grounded("Truncated unit price 19.2.", allowed) is False
    assert text_is_grounded("Budget-implied unit price 18.00.", allowed) is True


def test_identifier_digits_are_not_figure_claims() -> None:
    allowed = {"48150"}
    assert text_is_grounded("Trace LED-202610-001 only.", allowed) is True
    assert text_is_grounded("Trace LED-202610-001 for 99999.", allowed) is False


def test_invented_typed_ids_are_rejected_unless_supplied(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    facts = build_facts(raw_dir=raw, load_date=date(2026, 11, 6), catch_up=True)
    known = known_reference_catalog(facts)
    real_id = facts.quarantined_entry_ids[0]
    assert text_is_grounded(f"Quarantined {real_id} only.", {"48150"}, known) is True
    assert text_is_grounded("Quarantined LED-202610-999 only.", {"48150"}, known) is False
    assert text_is_grounded("Hash " + ("a" * 64) + ".", {"48150"}, known) is False


def test_allowed_fact_number_is_rejected_on_the_wrong_claim(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    facts = build_facts(raw_dir=raw, load_date=date(2026, 11, 6), catch_up=True)
    by_line = number_catalogs_by_line(facts)
    union = allowed_number_catalog(facts)
    assert "22.6" in union
    assert "22.6" not in by_line["us_laboratory"]
    wrong = json.dumps(
        {"hypotheses": {"us_laboratory": "Hypothesis: ClearPath Labs unit price is 22.6."}, "summary": []}
    )
    hypotheses, _ = parse_write_payload(wrong, {"us_laboratory"}, union, by_line)
    assert hypotheses == {}
    right = json.dumps(
        {"hypotheses": {"us_laboratory": "Hypothesis: ClearPath Labs unit price is 19.26."}, "summary": []}
    )
    hypotheses, _ = parse_write_payload(right, {"us_laboratory"}, union, by_line)
    assert hypotheses["us_laboratory"].endswith("19.26.")


def test_medicare_unsigned_loss_is_rejected_and_signed_copy_is_accepted(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    facts = build_facts(raw_dir=raw, load_date=date(2026, 11, 6), catch_up=True)
    by_line = number_catalogs_by_line(facts)
    union = allowed_number_catalog(facts)
    line = "us_medicare_medicaid_revenue"
    assert "2026-10" in union
    assert "10" not in by_line[line]
    assert "10.0" not in by_line[line]
    unsigned_amount = json.dumps(
        {
            "hypotheses": {
                line: "Hypothesis: denial rate is 22.6 and revenue declined by 52000."
            },
            "summary": [],
        }
    )
    hypotheses, _ = parse_write_payload(unsigned_amount, {line}, union, by_line)
    assert hypotheses == {}
    positive_percent = json.dumps(
        {
            "hypotheses": {
                line: "Hypothesis: denial rate is 22.6 after a 10.0% decline."
            },
            "summary": [],
        }
    )
    hypotheses, _ = parse_write_payload(positive_percent, {line}, union, by_line)
    assert hypotheses == {}
    signed = json.dumps(
        {
            "hypotheses": {
                line: (
                    "Hypothesis: amount_variance is -52000 and percent_display is -10.0%; "
                    "denial rate is 22.6."
                )
            },
            "summary": [],
        }
    )
    hypotheses, _ = parse_write_payload(signed, {line}, union, by_line)
    assert hypotheses[line].startswith("Hypothesis: amount_variance is -52000")
    assert "-10.0%" in hypotheses[line]


def test_numeric_legal_wrong_labels_are_rejected_without_evidence_copy(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    facts = build_facts(raw_dir=raw, load_date=date(2026, 11, 6), catch_up=True)
    by_line = number_catalogs_by_line(facts)
    union = allowed_number_catalog(facts)
    evidence = evidence_sentences(facts)
    medicare = "us_medicare_medicaid_revenue"
    lab = "us_laboratory"
    allowed = {medicare, lab}
    wrong_medicare = json.dumps(
        {
            "hypotheses": {
                medicare: "Hypothesis: claims stayed 4000 and denials are consistent, revenue unchanged."
            },
            "summary": [],
        }
    )
    hypotheses, _ = parse_write_payload(wrong_medicare, allowed, union, by_line, None, evidence)
    assert medicare not in hypotheses
    wrong_lab = json.dumps(
        {
            "hypotheses": {
                lab: "Hypothesis: budget-implied unit price is 19.26 from budget 45000 and quantity 2500."
            },
            "summary": [],
        }
    )
    hypotheses, _ = parse_write_payload(wrong_lab, allowed, union, by_line, None, evidence)
    assert lab not in hypotheses
    copied_only = json.dumps(
        {
            "hypotheses": {medicare: evidence[medicare], lab: evidence[lab]},
            "summary": ["Close for 2026-10 remains incomplete."],
        }
    )
    hypotheses, _ = parse_write_payload(copied_only, allowed, union, by_line, None, evidence)
    assert hypotheses == {}
    medicare_raw = "Higher denials reduced collections this closing period."
    lab_raw = "Higher supplier unit price increased expense."
    accepted = json.dumps(
        {
            "hypotheses": {
                medicare: evidence[medicare] + " " + medicare_raw,
                lab: evidence[lab] + " " + lab_raw,
            },
            "summary": ["Close for 2026-10 remains incomplete."],
        }
    )
    hypotheses, summary = parse_write_payload(accepted, allowed, union, by_line, None, evidence)
    assert hypotheses[medicare] == f"{evidence[medicare]} {_UNCERTAINTY_FRAME} {medicare_raw}"
    assert medicare_raw in hypotheses[medicare]
    assert "22.6" in hypotheses[medicare]
    assert "Revenue below budget." in evidence[medicare]
    assert hypotheses[lab] == f"{evidence[lab]} {_UNCERTAINTY_FRAME} {lab_raw}"
    assert lab_raw in hypotheses[lab]
    assert "budget-implied" in hypotheses[lab]
    assert "19.26" in hypotheses[lab]
    assert summary == ["Close for 2026-10 remains incomplete."]


def test_nested_writer_shape_requires_exact_evidence_and_rejects_bad_fields(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    facts = build_facts(raw_dir=raw, load_date=date(2026, 11, 6), catch_up=True)
    by_line = number_catalogs_by_line(facts)
    union = allowed_number_catalog(facts)
    evidence = evidence_sentences(facts)
    medicare = "us_medicare_medicaid_revenue"
    lab = "us_laboratory"
    allowed = {medicare, lab}
    medicare_raw = "Higher denials reduced collections this closing period."
    lab_raw = "Higher supplier unit price increased expense."
    nested_ok = json.dumps(
        {
            "hypotheses": {
                medicare: {
                    "evidence": evidence[medicare],
                    "hypothesis": medicare_raw,
                },
                lab: {
                    "evidence": evidence[lab],
                    "hypothesis": lab_raw,
                },
            },
            "summary": "Close for 2026-10 remains incomplete.",
        }
    )
    hypotheses, summary = parse_write_payload(nested_ok, allowed, union, by_line, None, evidence)
    assert hypotheses[medicare] == f"{evidence[medicare]} {_UNCERTAINTY_FRAME} {medicare_raw}"
    assert medicare_raw in hypotheses[medicare]
    assert "Revenue below budget." in evidence[medicare]
    assert hypotheses[lab] == f"{evidence[lab]} {_UNCERTAINTY_FRAME} {lab_raw}"
    assert lab_raw in hypotheses[lab]
    assert summary == ["Close for 2026-10 remains incomplete."]
    evidence_only = json.dumps(
        {
            "hypotheses": {
                medicare: {"evidence": evidence[medicare], "hypothesis": evidence[medicare]},
            },
            "summary": [],
        }
    )
    hypotheses, _ = parse_write_payload(evidence_only, allowed, union, by_line, None, evidence)
    assert hypotheses == {}
    empty_hypothesis = json.dumps(
        {"hypotheses": {medicare: {"evidence": evidence[medicare], "hypothesis": ""}}, "summary": []}
    )
    hypotheses, _ = parse_write_payload(empty_hypothesis, allowed, union, by_line, None, evidence)
    assert hypotheses == {}
    too_short = json.dumps(
        {
            "hypotheses": {
                medicare: {"evidence": evidence[medicare], "hypothesis": "Denials rose."},
            },
            "summary": [],
        }
    )
    hypotheses, _ = parse_write_payload(too_short, allowed, union, by_line, None, evidence)
    assert hypotheses == {}
    missing = json.dumps(
        {"hypotheses": {medicare: {"evidence": evidence[medicare]}}, "summary": []}
    )
    hypotheses, _ = parse_write_payload(missing, allowed, union, by_line, None, evidence)
    assert hypotheses == {}
    extra = json.dumps(
        {
            "hypotheses": {
                medicare: {
                    "evidence": evidence[medicare],
                    "hypothesis": medicare_raw,
                    "note": "extra",
                }
            },
            "summary": [],
        }
    )
    hypotheses, _ = parse_write_payload(extra, allowed, union, by_line, None, evidence)
    assert hypotheses == {}
    mismatched = json.dumps(
        {
            "hypotheses": {
                medicare: {
                    "evidence": "Claims 4000 unchanged; denials 14.0 to 14.0.",
                    "hypothesis": medicare_raw,
                }
            },
            "summary": [],
        }
    )
    hypotheses, _ = parse_write_payload(mismatched, allowed, union, by_line, None, evidence)
    assert hypotheses == {}
    non_string = json.dumps(
        {
            "hypotheses": {
                medicare: {
                    "evidence": evidence[medicare],
                    "hypothesis": [medicare_raw],
                }
            },
            "summary": [],
        }
    )
    hypotheses, _ = parse_write_payload(non_string, allowed, union, by_line, None, evidence)
    assert hypotheses == {}


def test_unsupported_line_drivers_are_rejected_and_source_drivers_accepted(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    facts = build_facts(raw_dir=raw, load_date=date(2026, 11, 6), catch_up=True)
    by_line = number_catalogs_by_line(facts)
    union = allowed_number_catalog(facts)
    evidence = evidence_sentences(facts)
    medicare = "us_medicare_medicaid_revenue"
    lab = "us_laboratory"
    allowed = {medicare, lab}
    medicare_raw = "Higher denials reduced collections this closing period."
    lab_raw = "Higher supplier unit price increased expense."
    tautology = json.dumps(
        {
            "hypotheses": {
                medicare: {
                    "evidence": evidence[medicare],
                    "hypothesis": "Revenue fluctuation causing shortfall",
                },
                lab: {"evidence": evidence[lab], "hypothesis": lab_raw},
            },
            "summary": [],
        }
    )
    hypotheses, _ = parse_write_payload(tautology, allowed, union, by_line, None, evidence)
    assert medicare not in hypotheses
    assert hypotheses[lab] == f"{evidence[lab]} {_UNCERTAINTY_FRAME} {lab_raw}"
    efficiency = json.dumps(
        {
            "hypotheses": {
                medicare: {"evidence": evidence[medicare], "hypothesis": medicare_raw},
                lab: {
                    "evidence": evidence[lab],
                    "hypothesis": "Laboratory efficiency gains leading to excess",
                },
            },
            "summary": [],
        }
    )
    hypotheses, _ = parse_write_payload(efficiency, allowed, union, by_line, None, evidence)
    assert hypotheses[medicare] == f"{evidence[medicare]} {_UNCERTAINTY_FRAME} {medicare_raw}"
    assert lab not in hypotheses
    volume = json.dumps(
        {
            "hypotheses": {
                lab: {
                    "evidence": evidence[lab],
                    "hypothesis": "Higher test volume increased laboratory expense.",
                }
            },
            "summary": [],
        }
    )
    hypotheses, _ = parse_write_payload(volume, allowed, union, by_line, None, evidence)
    assert hypotheses == {}
    accepted = json.dumps(
        {
            "hypotheses": {
                medicare: {"evidence": evidence[medicare], "hypothesis": medicare_raw},
                lab: {"evidence": evidence[lab], "hypothesis": lab_raw},
            },
            "summary": ["Close for 2026-10 remains incomplete."],
        }
    )
    hypotheses, summary = parse_write_payload(accepted, allowed, union, by_line, None, evidence)
    assert hypotheses[medicare] == f"{evidence[medicare]} {_UNCERTAINTY_FRAME} {medicare_raw}"
    assert hypotheses[lab] == f"{evidence[lab]} {_UNCERTAINTY_FRAME} {lab_raw}"
    assert summary == ["Close for 2026-10 remains incomplete."]


def test_trailing_punctuation_exponent_and_grouping_are_lexed_safely() -> None:
    allowed = {"48150", "19.26"}
    assert text_is_grounded("Verified actual is 48150.", allowed) is True
    assert text_is_grounded("Verified actual is 48150,", allowed) is True
    assert text_is_grounded("Verified actual is 48150;", allowed) is True
    assert text_is_grounded("Verified actual is 48150e0.", allowed) is False
    assert text_is_grounded("Verified actual is 4.8e3.", allowed) is False
    assert text_is_grounded("Verified actual is 48,150.", allowed) is True
    assert text_is_grounded("Verified actual is 48,15.", allowed) is False
    assert text_is_grounded("Invented grouping 111,111.", {"1"}) is False
    assert text_is_grounded("Sign-changed grouped actual -48,150.", allowed) is False


def test_summary_string_normalizes_to_one_grounded_line() -> None:
    payload = json.dumps(
        {
            "hypotheses": {"us_laboratory": "Hypothesis: unit price is 19.26."},
            "summary": "Close for 2026-10 remains\nincomplete.",
        }
    )
    hypotheses, summary = parse_write_payload(
        payload, {"us_laboratory"}, {"19.26", "2026-10"}
    )
    assert hypotheses["us_laboratory"] == "Hypothesis: unit price is 19.26."
    assert summary == ["Close for 2026-10 remains incomplete."]


def test_trusted_writer_policy_is_not_validated_as_sensitive_data() -> None:
    messages = build_write_messages(
        {
            "period": "2026-10",
            "incomplete": True,
            "relevant": ["us_laboratory"],
            "fx_rate": "1.27",
        }
    )
    assert "patient names" in messages[0]["content"]
    assert messages[0]["role"] == "system"


def test_fenced_writer_json_is_parsed_without_inventing_fields() -> None:
    payload = (
        "```json\n"
        '{"hypotheses":{"us_laboratory":"Hypothesis: unit price is 19.26."},'
        '"summary":["Close for 2026-10 remains incomplete."]}\n'
        "```"
    )
    hypotheses, summary = parse_write_payload(payload, {"us_laboratory"}, {"19.26", "2026-10"})
    assert hypotheses["us_laboratory"] == "Hypothesis: unit price is 19.26."
    assert summary == ["Close for 2026-10 remains incomplete."]
    truncated, empty = parse_write_payload('{"hypotheses":{"us_laboratory":"Hypothesis: unit price is 19.26."', {"us_laboratory"}, {"19.26"})
    assert truncated == {}
    assert empty == []


def test_grounded_nine_word_cause_fits_bounded_output_but_thirteen_does_not(tmp_path) -> None:
    raw = tmp_path / "raw"
    write_fixtures(raw, date(2026, 11, 6))
    facts = build_facts(raw_dir=raw, load_date=date(2026, 11, 6), catch_up=True)
    evidence = evidence_sentences(facts)
    key = "us_laboratory"
    cause = "Higher supplier unit price increased total laboratory expense costs."
    assert len(cause.split()) == 9
    payload = {"hypotheses": {key: {"evidence": evidence[key], "hypothesis": cause}}, "summary": []}
    accepted, _ = parse_write_payload(json.dumps(payload), {key}, allowed_number_catalog(facts), number_catalogs_by_line(facts), None, evidence)
    assert cause in accepted[key]
    payload["hypotheses"][key]["hypothesis"] += " for this closing period"
    rejected, _ = parse_write_payload(json.dumps(payload), {key}, allowed_number_catalog(facts), number_catalogs_by_line(facts), None, evidence)
    assert rejected == {}
