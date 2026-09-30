"""CONTEXT conflict triggers. Detection reads stored text. It does not invent counts.

An established capacity conflict stays unresolved until a later stored sentence
shows comparable coverage on the same unit that is not lower than the population.
Dropping the coverage sentence does not clear that record.
"""

from __future__ import annotations

import re
from typing import Any

from data.pipelines.rfp_intake.evaluators import asserts_uk_gdpr_instrument

_COUNT_UNIT = re.compile(
    r"(?i)\b(?P<count>\d{1,3}(?:,\d{3})+|\d+)\s+(?P<unit>employees|students|people|lives)\b"
)
_COVERAGE_SENTENCE = re.compile(
    r"(?i)[^.]*\b(?:cover|covers|covered|coverage|capacity|serve|serves|serving)\b[^.]*"
)

POPULATION_OPEN_QUESTION = "Covered population was not stated."
COVERAGE_OPEN_QUESTION = "Clinical Operations did not state a committed coverage figure."
RESOLUTIONS = ("reduce_covered_population", "add_sites")


def _parse_count(text: str) -> dict[str, Any] | None:
    match = _COUNT_UNIT.search(text)
    if match is None:
        return None
    return {
        "count": int(match.group("count").replace(",", "")),
        "unit": match.group("unit").lower(),
        "source_text": match.group(0),
    }


def parse_population(covered_population: object) -> dict[str, Any] | None:
    """Read a headcount only from the stored covered-population string."""
    if not isinstance(covered_population, str) or not covered_population.strip():
        return None
    parsed = _parse_count(covered_population)
    if parsed is None:
        return None
    parsed["source_field"] = "covered_population"
    parsed["source_text"] = covered_population.strip()
    return parsed


def parse_coverage(clinical_text: str) -> dict[str, Any] | None:
    """Read coverage only from a sentence that already states cover, capacity, or serve.

    A days-per-week schedule has no population unit, so it does not match.
    """
    if not clinical_text.strip():
        return None
    for sentence in _COVERAGE_SENTENCE.findall(clinical_text):
        parsed = _parse_count(sentence)
        if parsed is None:
            continue
        parsed["source_field"] = "clinical_coverage"
        parsed["source_text"] = sentence.strip()
        return parsed
    return None


def clinical_text(section: dict[str, Any]) -> str:
    """Join the clinical aspects and the current draft. Both are stored fields."""
    key_aspects = section.get("key_aspects") if isinstance(section.get("key_aspects"), dict) else {}
    aspects = key_aspects.get("aspects") if isinstance(key_aspects.get("aspects"), list) else []
    aspect_text = " ".join(aspect for aspect in aspects if isinstance(aspect, str))
    draft = section.get("draft_content") if isinstance(section.get("draft_content"), str) else ""
    return f"{aspect_text}\n{draft}"


def _capacity_record(population: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    return {
        "trigger_id": "capacity-vs-population",
        "arbiter": "Tom Callahan",
        "population": {
            "count": population["count"],
            "unit": population["unit"],
            "source_field": population["source_field"],
            "source_text": population["source_text"],
        },
        "coverage": {
            "count": coverage["count"],
            "unit": coverage["unit"],
            "source_field": coverage["source_field"],
            "source_text": coverage["source_text"],
        },
        "comparison": "coverage_count < population_count",
        "resolution": None,
        "resolved": False,
    }


def assess_capacity(
    covered_population: object,
    clinical_corpus: str,
    established: dict[str, Any] | None,
) -> tuple[list[str], dict[str, Any] | None]:
    """Return open questions and the capacity record.

    Missing evidence does not create a conflict. Once a conflict exists, missing
    evidence does not delete it and does not mark it resolved.
    """
    population = parse_population(covered_population)
    coverage = parse_coverage(clinical_corpus)
    questions: list[str] = []
    if population is None:
        questions.append(POPULATION_OPEN_QUESTION)
    if coverage is None:
        questions.append(COVERAGE_OPEN_QUESTION)
    comparable = (
        population is not None
        and coverage is not None
        and population["unit"] == coverage["unit"]
    )
    if established is None:
        if comparable and coverage["count"] < population["count"]:
            return questions, _capacity_record(population, coverage)
        return questions, None

    # Keep the counts that established the conflict. A later sentence can resolve
    # it, but it cannot replace those counts with a blank.
    kept = {
        "trigger_id": established.get("trigger_id", "capacity-vs-population"),
        "arbiter": "Tom Callahan",
        "population": established.get("population"),
        "coverage": established.get("coverage"),
        "comparison": "coverage_count < population_count",
        "resolution": established.get("resolution"),
        "resolved": False,
    }
    if comparable and coverage["count"] >= population["count"]:
        kept["resolved"] = True
        kept["resolution_evidence"] = {
            "population": {
                "count": population["count"],
                "unit": population["unit"],
                "source_text": population["source_text"],
            },
            "coverage": {
                "count": coverage["count"],
                "unit": coverage["unit"],
                "source_text": coverage["source_text"],
            },
        }
    return questions, kept


def population_after_reduce(coverage: dict[str, Any]) -> str:
    """Copy the already extracted coverage figure. This writes no new integer."""
    return (
        f"{coverage['count']} {coverage['unit']} "
        "(from the clinical coverage sentence already on the ticket)"
    )


def section_has_phi(section: dict[str, Any]) -> bool:
    evaluation = section.get("evaluation_results") if isinstance(section.get("evaluation_results"), dict) else {}
    return bool(evaluation.get("contains_phi"))


def wrong_instrument(country: object, text: str) -> bool:
    """True when this section states the other country's agreement."""
    folded = text.casefold()
    if country == "US":
        return asserts_uk_gdpr_instrument(text)
    if country == "UK":
        has_dpa = "data processing agreement" in folded and "uk gdpr" in folded
        return "business associate agreement" in folded and not has_dpa
    return False


def compliance_gap(country: object, text: str) -> bool:
    """True when the compliance section is missing the country-correct clause."""
    folded = text.casefold()
    if country == "US":
        return "business associate agreement" not in folded or asserts_uk_gdpr_instrument(text)
    if country == "UK":
        return "data processing agreement" not in folded or "uk gdpr" not in folded
    return False


def baa_dpa_targets(country: object, sections: list[dict[str, Any]]) -> list[str]:
    """Compliance is a target when its clause is wrong, plus any section with the wrong instrument."""
    targets: list[str] = []
    for section in sections:
        department_id = section.get("department_id")
        if not isinstance(department_id, str):
            continue
        text = section.get("draft_content") if isinstance(section.get("draft_content"), str) else ""
        if department_id == "compliance" and compliance_gap(country, text):
            targets.append(department_id)
        elif wrong_instrument(country, text):
            targets.append(department_id)
    return targets


def regulatory_blocks_capacity(phi_open: bool, baa_open: bool) -> bool:
    """Claire Whitfield's triggers win. Tom's capacity choice stays closed."""
    return phi_open or baa_open


def actor_may_resolve_capacity(actor_department_id: str) -> bool:
    """Only the revenue binding, which is Tom Callahan's demonstration account, may choose."""
    return actor_department_id == "revenue"
