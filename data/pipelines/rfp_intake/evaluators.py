"""Parallel readability, relevance, and compliance checks for one section.

Each evaluator returns only its own criterion. The merge keeps those fields
apart so the workers do not overwrite one another.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from data.pipelines.rfp_intake.phi import screen_generated, screen_structure
from data.pipelines.rfp_intake.readability import readability_metrics

READABILITY_LOW = 8.0
READABILITY_HIGH = 14.0
_TOKEN = re.compile(r"[a-z0-9]+")
_VOLUME = re.compile(r"\b\d{2,}\s+(?:employees|students|people|lives)\b", re.IGNORECASE)
_STOPWORDS = frozenset(
    {
        "about",
        "after",
        "again",
        "agreement",
        "before",
        "being",
        "between",
        "client",
        "could",
        "every",
        "from",
        "have",
        "healthcore",
        "include",
        "including",
        "into",
        "must",
        "other",
        "section",
        "should",
        "stated",
        "their",
        "there",
        "these",
        "this",
        "under",
        "using",
        "which",
        "while",
        "with",
        "would",
    }
)


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN.findall(text.casefold()) if len(token) >= 5 and token not in _STOPWORDS}


def _numeric_score(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def evaluate_readability(draft: str) -> dict[str, Any]:
    """Pass only a numeric Flesch-Kincaid grade inside the chosen band."""
    metrics = readability_metrics(draft)
    score = _numeric_score(metrics.get("flesch_kincaid_grade"))
    if score is None:
        reason = metrics.get("unavailable_reason") or "No numeric Flesch-Kincaid grade was returned."
        return {
            "pass": False,
            "score": None,
            "details": f"{reason} Write at least 100 words of plain business sentences.",
        }
    if score < READABILITY_LOW or score > READABILITY_HIGH:
        return {
            "pass": False,
            "score": score,
            "details": (
                f"Flesch-Kincaid grade {score} is outside {READABILITY_LOW:g} to {READABILITY_HIGH:g}. "
                "Rewrite the section in plain sentences of at least 100 words."
            ),
        }
    return {
        "pass": True,
        "score": score,
        "details": f"Flesch-Kincaid grade {score} is inside {READABILITY_LOW:g} to {READABILITY_HIGH:g}.",
    }


def evaluate_relevance(draft: str, aspects: list[str]) -> dict[str, Any]:
    """An aspect is missing when none of its significant words appear in the draft."""
    draft_tokens = _tokens(draft)
    missing: list[str] = []
    for aspect in aspects:
        if not isinstance(aspect, str) or not aspect.strip():
            continue
        aspect_tokens = _tokens(aspect)
        if aspect_tokens:
            if aspect_tokens.isdisjoint(draft_tokens):
                missing.append(aspect)
        elif aspect.strip().casefold() not in draft.casefold():
            missing.append(aspect)
    if missing:
        return {
            "pass": False,
            "missing_aspects": missing,
        }
    return {"pass": True, "missing_aspects": []}


def evaluate_compliance(
    draft: str,
    department_id: str,
    metadata: dict[str, Any],
    *,
    allowed_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Apply HealthCore rules. contains_phi is set from the original draft."""
    screened = screen_generated(draft, allowed_names=allowed_names)
    text = screened.text.casefold()
    country = metadata.get("client_country")
    population = metadata.get("covered_population")
    rule_ids: list[str] = []
    violations: list[str] = []
    if screened.detected:
        rule_ids.append("HC-NO-PHI")
        violations.append(
            "Remove patient names, diagnoses, and identifiers. Store only the redacted section."
        )
    if department_id == "compliance" and country == "US" and "business associate agreement" not in text:
        rule_ids.append("HC-US-BAA")
        violations.append("US client_country requires a Business Associate Agreement clause in the compliance section.")
    if department_id == "compliance" and country == "UK":
        if "data processing agreement" not in text or "uk gdpr" not in text:
            rule_ids.append("HC-UK-DPA")
            violations.append(
                "UK client_country requires a Data Processing Agreement clause that references UK GDPR."
            )
    if department_id == "revenue" and country == "US" and not re.search(r"\busd\b", text):
        rule_ids.append("HC-CURRENCY")
        violations.append("US client_country requires pricing in USD in the revenue section.")
    if department_id == "revenue" and country == "UK" and not re.search(r"\bgbp\b", text):
        rule_ids.append("HC-CURRENCY")
        violations.append("UK client_country requires pricing in GBP in the revenue section.")
    if country == "US" and re.search(r"\bgbp\b", text) and department_id in {"revenue", "compliance"}:
        if "HC-CURRENCY" not in rule_ids:
            rule_ids.append("HC-CURRENCY")
        violations.append("The draft quotes GBP. A US client must be quoted in USD.")
    if country == "UK" and re.search(r"\busd\b", text) and department_id in {"revenue", "compliance"}:
        if "HC-CURRENCY" not in rule_ids:
            rule_ids.append("HC-CURRENCY")
        violations.append("The draft quotes USD. A UK client must be quoted in GBP.")
    if country == "US" and department_id == "compliance" and "uk gdpr" in text:
        if "HC-US-BAA" not in rule_ids:
            rule_ids.append("HC-US-BAA")
        violations.append("A US client must use a Business Associate Agreement, not a UK GDPR instrument.")
    if country == "UK" and department_id == "compliance" and "business associate agreement" in text and "data processing agreement" not in text:
        if "HC-UK-DPA" not in rule_ids:
            rule_ids.append("HC-UK-DPA")
        violations.append("A UK client must use a Data Processing Agreement referencing UK GDPR, not only a BAA.")
    population_missing = not isinstance(population, str) or not population.strip()
    if population_missing and _VOLUME.search(screened.text):
        rule_ids.append("HC-NO-INVENTED-VOLUME")
        violations.append(
            "Covered population was not in the handoff. Remove the invented headcount and record an open question."
        )
    return {
        "pass": not violations,
        "rule_ids": rule_ids,
        "violations": violations,
        "contains_phi": screened.detected,
    }


def _feedback(readability: dict[str, Any], relevance: dict[str, Any], compliance: dict[str, Any]) -> str:
    notes: list[str] = []
    if not readability["pass"]:
        notes.append(str(readability["details"]))
    if not relevance["pass"]:
        joined = "; ".join(str(aspect) for aspect in relevance["missing_aspects"])
        notes.append(f"Address these missing aspects from the handoff: {joined}.")
    if not compliance["pass"]:
        notes.extend(str(item) for item in compliance["violations"])
    if not notes:
        return "The section passed readability, relevance, and compliance."
    return " ".join(notes)


def merge_evaluation(
    department_id: str,
    readability: dict[str, Any],
    relevance: dict[str, Any],
    compliance: dict[str, Any],
    *,
    allowed_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Combine one criterion from each evaluator, then redact derived strings."""
    contains_phi = bool(compliance.get("contains_phi"))
    result: dict[str, Any] = {
        "department_id": department_id,
        "readability": readability,
        "relevance": relevance,
        "compliance": compliance,
        "overall_pass": bool(readability["pass"] and relevance["pass"] and compliance["pass"] and not contains_phi),
        "feedback_for_generator": _feedback(readability, relevance, compliance),
        "contains_phi": contains_phi,
    }
    screened, structure_phi, _blocked = screen_structure(result)
    assert isinstance(screened, dict)
    # screen_structure only catches labeled fields. Walk prose as well.
    prose_phi = False

    def walk(item: object) -> object:
        nonlocal prose_phi
        if isinstance(item, str):
            generated = screen_generated(item, allowed_names=allowed_names)
            if generated.detected:
                prose_phi = True
            return generated.text
        if isinstance(item, list):
            return [walk(entry) for entry in item]
        if isinstance(item, dict):
            return {key: walk(value) for key, value in item.items()}
        return item

    screened_result = walk(screened)
    assert isinstance(screened_result, dict)
    if structure_phi or prose_phi:
        screened_result["contains_phi"] = True
        compliance_result = screened_result.get("compliance")
        if isinstance(compliance_result, dict):
            compliance_result["contains_phi"] = True
            compliance_result["pass"] = False
        screened_result["overall_pass"] = False
    return screened_result


def evaluate_in_parallel(
    draft: str,
    aspects: list[str],
    department_id: str,
    metadata: dict[str, Any],
    *,
    allowed_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Run the three evaluators together. None of them waits for another department."""
    with ThreadPoolExecutor(max_workers=3) as pool:
        readability_task = pool.submit(evaluate_readability, draft)
        relevance_task = pool.submit(evaluate_relevance, draft, aspects)
        compliance_task = pool.submit(
            evaluate_compliance,
            draft,
            department_id,
            metadata,
            allowed_names=allowed_names,
        )
        readability = readability_task.result()
        relevance = relevance_task.result()
        compliance = compliance_task.result()
    return merge_evaluation(
        department_id,
        readability,
        relevance,
        compliance,
        allowed_names=allowed_names,
    )
