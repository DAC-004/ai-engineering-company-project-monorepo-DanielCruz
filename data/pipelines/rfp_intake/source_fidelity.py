"""Rules for unsupported monetary and compliance claims in client-facing drafts."""

from __future__ import annotations

import re
from typing import Any

from data.pipelines.rfp_intake.grounding import normalize_optional_metadata_text

_DOLLAR_AMOUNT = re.compile(r"\$\s*[\d,]+(?:\.\d+)?")
_GBP_AMOUNT = re.compile(r"£\s*[\d,]+(?:\.\d+)?|\bgbp\s*[\d,]+", re.IGNORECASE)
_UNIT_PRICE_PHRASE = re.compile(
    r"\b(?:per[- ]?(?:appointment|visit|consultation|member|employee)|"
    r"each\s+(?:appointment|visit)|revenue\s+per|fee\s+per)\b",
    re.IGNORECASE,
)
_INVENTED_REVENUE = re.compile(r"\b(?:estimated|projected)\s+(?:revenue|income)\b", re.IGNORECASE)
_PRICE_AGREED = re.compile(
    r"\b(?:price|prices|rate|rates|fee|fees|discount).{0,60}\b(?:agreed|approved|stated)\b",
    re.IGNORECASE,
)
_ENSURES_HIPAA = re.compile(r"\bensures\s+compliance\s+with\s+hipaa\b", re.IGNORECASE)
_MEETS_REGULATORY_REQUIREMENT = re.compile(r"\bmeets the regulatory requirement\b", re.IGNORECASE)
_ENSURES_COMPLIANCE = re.compile(r"\bthis ensures compliance\b", re.IGNORECASE)
# Only when the BAA itself is treated as a USD-priced instrument.
# Co-occurrence of commercial USD quoting and a BAA requirement is allowed.
_BAA_AS_USD_INSTRUMENT = re.compile(
    r"\b(?:business associate agreement|baa)\b"
    r"(?:\s*\([^)]{0,40}\))?"
    r"(?:[\s,]+\w+){0,8}\s+"
    r"(?:quoted|included|priced)\s+in\s+usd\b"
    r"|\b(?:quoted|included|priced)\s+(?:a\s+)?(?:business associate agreement|baa)\s+in\s+usd\b"
    r"|\b(?:business associate agreement|baa)\s+in\s+usd\b",
    re.IGNORECASE,
)
_MONTH_NAME = re.compile(
    r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.IGNORECASE,
)
_YEAR = re.compile(r"\b20\d{2}\b")
_VOLUME_FIGURE = re.compile(r"\b\d+\s+(?:appointments?|visits?)\s+per\s+month\b", re.IGNORECASE)
_START_DATE_QUESTION = re.compile(
    r"\b(?:what|when)\b.{0,80}\b(?:proposed\s+)?start date\b|\bproposed start date\b",
    re.IGNORECASE,
)
_SUPPLIED_VOLUME_QUESTION = re.compile(
    r"\b(?:what|how many)\b.{0,80}\b(?:expected (?:patient |appointment )?volume|appointments?|visits?)\b",
    re.IGNORECASE,
)
_NO_SHOW_OR_CANCELLATION = re.compile(r"\bno-shows?|\bcancellations?\b", re.IGNORECASE)
_CONSENT_FORMS_IN_PLACE = re.compile(
    r"\b(?:patient )?consent forms are in place\b"
    r"|\bensure all necessary patient consent forms are in place\b"
    r"|\bconsent requirements and workforce training are in place\b",
    re.IGNORECASE,
)
_TRAINING_AS_IMPLEMENTED = re.compile(
    r"\bmaintain regular training\b|\btraining for all staff\b.*\bto reinforce\b",
    re.IGNORECASE,
)
_NO_EXTRA_SAFEGUARDS = re.compile(
    r"\bno\s+additional\s+(?:agreements?|safeguards?|measures?)"
    r"(?:\s+or\s+(?:agreements?|safeguards?|measures?))?"
    r"\s+(?:are\s+)?(?:needed|required)\b",
    re.IGNORECASE,
)
_NO_OTHER_AGREEMENTS_REQUIRED = re.compile(
    r"\bno\s+other\s+(?:agreements?|safeguards?|measures?)"
    r"(?:\s+or\s+(?:agreements?|safeguards?|measures?))?"
    r"\s+(?:are\s+)?(?:needed|required)\b",
    re.IGNORECASE,
)
_GENERATOR_SCAFFOLDING = re.compile(
    r"^\s*(?:Missing:|Missing information:|Add more details:|Information still needed:|Information still required:)",
    re.IGNORECASE,
)
_PLEASE_PROVIDE_OPEN_QUESTION = re.compile(r"\bplease provide an open question\b", re.IGNORECASE)
_RECORD_AN_OPEN_QUESTION = re.compile(r"\brecord an open question\b", re.IGNORECASE)
_DO_NOT_INVENT_A_PRICE = re.compile(r"\bdo not invent a price\b", re.IGNORECASE)
_DO_NOT_INVENT_A_HEADCOUNT = re.compile(r"\bdo not invent a headcount\b", re.IGNORECASE)
_DO_NOT_ASK_EXPECTED_VOLUME = re.compile(
    r"\bdo not ask what the expected volume is\b",
    re.IGNORECASE,
)
_STATE_THAT_CATEGORY_CLAUSE = re.compile(r",\s*state that category\.?\s*$", re.IGNORECASE)
_ORPHAN_THESE_RATES_QUESTION = re.compile(
    r"^\s*what would you estimate these rates to be\b",
    re.IGNORECASE,
)
_COVERED_POPULATION_UNSTATED = re.compile(
    r"\bcovered population\b.{0,80}\bwas not stated\b",
    re.IGNORECASE,
)
_NUMERIC_HEADCOUNT_UNSTATED = re.compile(
    r"\bnumeric headcount was not stated\b",
    re.IGNORECASE,
)
_ENSURE_CONSENT_REQUIREMENTS_MET = re.compile(
    r"\bensure all consent requirements are met\b",
    re.IGNORECASE,
)
_CONSENT_CONFIRMATION_CLAUSE = (
    "Consent requirements and workforce training are items to confirm with the client"
)
_EQUIPMENT_FACILITIES_IN_PLACE = re.compile(
    r"\b(?:all necessary )?(?:equipment and facilities|facilities and equipment) are in place\b",
    re.IGNORECASE,
)
_ENSURE_ENOUGH_STAFFING_CAPACITY = re.compile(
    r"\bensure(?:s|ing)?\s+(?:that\s+)?there(?:'s| is) enough staffing and capacity\b"
    r"|\benough staffing and capacity to handle\b",
    re.IGNORECASE,
)
# "confirm whether X is in place" asks; a bare "X are in place" asserts a completed state.
_VERIFICATION_WHETHER = re.compile(
    r"\b(?:confirm|verify|determine|ask)\s+(?:whether|if)\b",
    re.IGNORECASE,
)


def handoff_allows_monetary_figures(aspects: tuple[str, ...] | list[str]) -> bool:
    """True only when the handoff explicitly records agreed pricing, not merely a budget."""
    for aspect in aspects:
        if not isinstance(aspect, str) or not aspect.strip():
            continue
        folded = aspect.casefold()
        if "no prices" in folded or "no discounts" in folded:
            return False
        if "have been agreed" in folded and ("price" in folded or "discount" in folded):
            return True
        if _PRICE_AGREED.search(aspect):
            return True
    return False


def draft_contains_monetary_claim(text: str) -> bool:
    return bool(
        _DOLLAR_AMOUNT.search(text)
        or _GBP_AMOUNT.search(text)
        or _INVENTED_REVENUE.search(text)
        or (_UNIT_PRICE_PHRASE.search(text) and re.search(r"\d", text))
    )


def draft_asserts_unsupported_price(
    text: str,
    metadata: dict[str, Any],
    aspects: tuple[str, ...] | list[str],
) -> bool:
    if not draft_contains_monetary_claim(text):
        return False
    if handoff_allows_monetary_figures(aspects):
        return False
    # A budget range alone does not authorize unit prices or revenue estimates.
    _ = normalize_optional_metadata_text(metadata.get("budget_range"))
    return True


def _is_verification_whether_request(text: str) -> bool:
    return bool(_VERIFICATION_WHETHER.search(text))


_BAA_QUOTED_IN_USD = re.compile(
    r"\b(?:business associate agreement|baa)\b(?:\s*\([^)]{0,40}\))?(?:[\s,]+\w+){0,8}\s+"
    r"(?:quoted|included|priced)\s+in\s+usd\b",
    re.IGNORECASE,
)
_QUOTED_BAA_IN_USD = re.compile(
    r"\b(?:quoted|included|priced)\s+(?:a\s+)?(?:business associate agreement|baa)\s+in\s+usd\b",
    re.IGNORECASE,
)
_BAA_IN_USD = re.compile(r"\b(?:business associate agreement|baa)\s+in\s+usd\b", re.IGNORECASE)
_REQUIRED_BAA_CLAUSE = "A Business Associate Agreement is required before PHI exchange"


def keep_baa_requirement_without_usd_price(sentence: str) -> str | None:
    """Keep the BAA duty when the model priced the BAA in USD. Do not drop the clause."""
    if not _BAA_AS_USD_INSTRUMENT.search(sentence):
        return None
    rewritten = _BAA_QUOTED_IN_USD.sub(_REQUIRED_BAA_CLAUSE, sentence)
    rewritten = _QUOTED_BAA_IN_USD.sub(_REQUIRED_BAA_CLAUSE, rewritten)
    rewritten = _BAA_IN_USD.sub("Business Associate Agreement", rewritten)
    rewritten = re.sub(r"\s+", " ", rewritten).strip()
    rewritten = re.sub(r"\binclude a a business associate agreement\b", "include a Business Associate Agreement", rewritten, flags=re.IGNORECASE)
    if _BAA_AS_USD_INSTRUMENT.search(rewritten) or (
        "business associate agreement" not in rewritten.casefold() and not re.search(r"\bbaa\b", rewritten, re.IGNORECASE)
    ):
        return f"{_REQUIRED_BAA_CLAUSE}."
    if rewritten[-1:] not in ".!?":
        rewritten = f"{rewritten}."
    return rewritten


def rewrite_state_that_category_instruction(sentence: str) -> str | None:
    """Keep the stated category. Drop the generator instruction to name it."""
    if not _STATE_THAT_CATEGORY_CLAUSE.search(sentence):
        return None
    rewritten = _STATE_THAT_CATEGORY_CLAUSE.sub(".", sentence).strip()
    rewritten = re.sub(r"\s+\.", ".", rewritten)
    if rewritten[-1:] not in ".!?":
        rewritten = f"{rewritten}."
    return rewritten


def rewrite_false_unstated_population(sentence: str, covered_population: object) -> str | None:
    """Keep the stated category. Do not treat it as a missing population, and do not invent a headcount."""
    if not isinstance(covered_population, str) or not covered_population.strip():
        return None
    if _NUMERIC_HEADCOUNT_UNSTATED.search(sentence):
        return None
    if not _COVERED_POPULATION_UNSTATED.search(sentence):
        return None
    category = covered_population.strip()
    if any(character.isdigit() for character in category):
        rewritten = f"The covered population is {category}."
    else:
        rewritten = (
            f"The covered population category is {category}. "
            "A numeric headcount was not stated."
        )
    return rewritten


def rewrite_consent_met_as_confirmation(sentence: str) -> str | None:
    """Keep the consent topic. Do not leave a completed-measure 'ensure ... are met' claim."""
    if not _ENSURE_CONSENT_REQUIREMENTS_MET.search(sentence):
        return None
    if _is_verification_whether_request(sentence):
        return None
    return f"{_CONSENT_CONFIRMATION_CLAUSE}."


def draft_asserts_unsupported_compliance_assurance(text: str) -> bool:
    consent_in_place = bool(_CONSENT_FORMS_IN_PLACE.search(text)) and not _is_verification_whether_request(
        text
    )
    return bool(
        _ENSURES_HIPAA.search(text)
        or _ENSURES_COMPLIANCE.search(text)
        or _MEETS_REGULATORY_REQUIREMENT.search(text)
        or _BAA_AS_USD_INSTRUMENT.search(text)
        or consent_in_place
        or _TRAINING_AS_IMPLEMENTED.search(text)
        or _NO_EXTRA_SAFEGUARDS.search(text)
        or _NO_OTHER_AGREEMENTS_REQUIRED.search(text)
    )


def draft_mentions_irrelevant_uk_instrument_for_us_client(text: str, client_country: object) -> bool:
    """US clients should not carry UK DPA/GDPR requirement narration unless negating applicability."""
    if client_country != "US":
        return False
    folded = text.casefold()
    if "uk gdpr" not in folded and "uk client" not in folded and "data processing agreement" not in folded:
        return False
    if re.search(r"\b(?:does not apply|do not apply|not apply|without)\b", text, re.IGNORECASE):
        return False
    return True


def draft_asserts_invented_capacity_commitment(text: str) -> bool:
    """True when requested demand is treated as staffing HealthCore will already meet."""
    if _is_verification_whether_request(text):
        return False
    return bool(_ENSURE_ENOUGH_STAFFING_CAPACITY.search(text))


def draft_asserts_invented_facilities_in_place(text: str) -> bool:
    """True when equipment or facilities are stated as already in place."""
    if _is_verification_whether_request(text):
        return False
    return bool(_EQUIPMENT_FACILITIES_IN_PLACE.search(text))


def aspects_state_proposed_start(aspects: list[str] | tuple[str, ...]) -> bool:
    joined = " ".join(aspect for aspect in aspects if isinstance(aspect, str))
    return bool(_MONTH_NAME.search(joined) and _YEAR.search(joined))


def aspects_state_appointment_volume(aspects: list[str] | tuple[str, ...]) -> bool:
    joined = " ".join(aspect for aspect in aspects if isinstance(aspect, str))
    return bool(_VOLUME_FIGURE.search(joined))


def is_redundant_known_fact_question(sentence: str, aspects: list[str] | tuple[str, ...]) -> bool:
    """True when a question re-asks a start date or volume already in the handoff.

    No-show or cancellation assumption questions stay when they do not re-ask volume.
    """
    stripped = sentence.strip()
    if "?" not in stripped:
        return False
    if aspects_state_proposed_start(aspects) and _START_DATE_QUESTION.search(stripped):
        return True
    if aspects_state_appointment_volume(aspects) and _SUPPLIED_VOLUME_QUESTION.search(stripped):
        if _NO_SHOW_OR_CANCELLATION.search(stripped) and not re.search(
            r"\b(?:expected (?:patient |appointment )?volume|how many (?:appointments?|visits?))\b",
            stripped,
            re.IGNORECASE,
        ):
            return False
        return True
    return False


def is_generator_scaffolding_sentence(sentence: str) -> bool:
    stripped = sentence.strip()
    if not stripped:
        return True
    if _GENERATOR_SCAFFOLDING.match(stripped):
        return True
    if _PLEASE_PROVIDE_OPEN_QUESTION.search(stripped):
        return True
    if _RECORD_AN_OPEN_QUESTION.search(stripped):
        return True
    if re.search(r"\brequires an open question\b", stripped, re.IGNORECASE):
        return True
    if re.search(r"\bask whether a budget exists\b", stripped, re.IGNORECASE):
        return True
    if _DO_NOT_INVENT_A_PRICE.search(stripped):
        return True
    if _DO_NOT_INVENT_A_HEADCOUNT.search(stripped):
        return True
    if _DO_NOT_ASK_EXPECTED_VOLUME.search(stripped):
        return True
    if _ORPHAN_THESE_RATES_QUESTION.search(stripped):
        return True
    if re.fullmatch(
        r"(?:Missing|Missing information|Add more details|Information still needed|Information still required):.*",
        stripped,
        re.IGNORECASE,
    ):
        return True
    if re.search(r"\bask for these details first\b", stripped, re.IGNORECASE):
        return True
    if re.search(r"\badditional sentences to bring the section\b", stripped, re.IGNORECASE):
        return True
    if re.search(
        r"\b(?:add enough new sentences to bring the full section|additional sentences to bring the (?:full )?section)\b",
        stripped,
        re.IGNORECASE,
    ):
        return True
    if re.search(r"\babout 150 words\b", stripped, re.IGNORECASE) and re.search(
        r"\bbring the (?:full )?section\b", stripped, re.IGNORECASE
    ):
        return True
    if re.match(r"^\s*Addition:", stripped, re.IGNORECASE):
        return True
    if re.fullmatch(r"Missing\s+\w+.*", stripped, re.IGNORECASE) and "not stated" not in stripped.casefold():
        return True
    return False
