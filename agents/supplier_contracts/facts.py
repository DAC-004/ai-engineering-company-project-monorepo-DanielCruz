"""Structured fact blocks derived from specialist results, not substring markers."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from agents.supplier_contracts.privacy import is_credible_clause_number
from agents.supplier_contracts.types import ContractsResult, PricingResult

MANDATORY_CATEGORIES = frozenset({"compliance", "approval", "source"})
# Notice, exit, and evidenced annual-value terms stay in briefs even when the
# model omits those ids from optional fact selection.
RETAINED_FACT_IDS = frozenset(
    {
        "expiry_notice",
        "exit_penalty",
        "exit_penalty_uncertain",
        "estimated_annual_value",
        "estimated_annual_value_uncertain",
    }
)


@dataclass(frozen=True)
class FactBlock:
    fact_id: str
    category: str
    text: str


def _dec_text(value: Decimal | None) -> str:
    if value is None:
        return "unknown"
    return format(value, "f")


def fact_blocks_from_results(
    *,
    pricing: PricingResult | None,
    contracts: ContractsResult | None,
    required_approvers: tuple[str, ...],
    load_date=None,
    schedule_dates=None,
) -> tuple[FactBlock, ...]:
    blocks: list[FactBlock] = []
    blocks.extend(_compliance_blocks(contracts))
    blocks.extend(_approval_blocks(required_approvers))
    blocks.extend(_source_blocks(pricing, contracts))
    if pricing:
        blocks.extend(_pricing_blocks(pricing))
    if contracts:
        blocks.extend(_contract_blocks(contracts, load_date, schedule_dates))
    return tuple(blocks)


def _compliance_blocks(contracts: ContractsResult | None) -> list[FactBlock]:
    if contracts is None:
        return [
            FactBlock(
                "compliance_unevaluated",
                "compliance",
                "Data-protection status was not evaluated for this request.",
            )
        ]
    if contracts.missing_dpa:
        return [
            FactBlock(
                "compliance_missing_dpa",
                "compliance",
                (
                    f"missing_dpa=True dpa_status={contracts.dpa_status}. "
                    "Brief and draft stay blocked until Compliance confirmation."
                ),
            )
        ]
    return [
        FactBlock(
            "compliance_dpa_recorded",
            "compliance",
            f"missing_dpa=False dpa_status={contracts.dpa_status}.",
        )
    ]


def _approval_blocks(required_approvers: tuple[str, ...]) -> list[FactBlock]:
    if required_approvers:
        return [
            FactBlock(
                "approval_required",
                "approval",
                "Required approvers: " + ", ".join(required_approvers) + ". Payload names are not identity.",
            )
        ]
    return [
        FactBlock(
            "approval_none",
            "approval",
            "No named approvers are required for this request.",
        )
    ]


def _source_blocks(pricing: PricingResult | None, contracts: ContractsResult | None) -> list[FactBlock]:
    blocks: list[FactBlock] = []
    if contracts is not None:
        for term in contracts.terms:
            if term.field == "billing" or not is_credible_clause_number(term.clause):
                continue
            blocks.append(
                FactBlock(
                    f"source_{term.field}_{term.clause}",
                    "source",
                    f"{term.field} clause {term.clause} page {term.page} sha256={term.pdf_sha256}",
                )
            )
        if not blocks and contracts.pdf_sha256:
            blocks.append(
                FactBlock("source_pdf", "source", f"pdf_sha256={contracts.pdf_sha256}")
            )
    if pricing is not None and pricing.source_row_ids:
        blocks.append(
            FactBlock(
                "source_price_rows",
                "source",
                "Price source rows: " + ",".join(pricing.source_row_ids),
            )
        )
    if not blocks:
        blocks.append(FactBlock("source_none", "source", "No clause or price-row source is attached."))
    return blocks


def _pricing_blocks(pricing: PricingResult) -> list[FactBlock]:
    blocks = [
        FactBlock(
            "price_change",
            "pricing",
            (
                f"{pricing.supplier_id} {pricing.product}: previous {_dec_text(pricing.previous_price)} "
                f"current {_dec_text(pricing.current_price)} {pricing.currency}; "
                f"ratio {_dec_text(pricing.change_ratio)}; above_threshold={pricing.above_threshold}; "
                f"formula {pricing.formula}; quote_only={pricing.quote_only}."
            ),
        ),
        FactBlock(
            "annual_impact",
            "pricing",
            (
                f"annual {_dec_text(pricing.annual_incremental)} {pricing.currency} "
                f"({_dec_text(pricing.annual_incremental_usd)} USD)."
            ),
        ),
    ]
    if pricing.quote_only:
        blocks.append(
            FactBlock(
                "quote_only",
                "pricing",
                f"{pricing.supplier_id} is quote-only. Availability is not assumed.",
            )
        )
    if pricing.missing:
        blocks.append(
            FactBlock(
                "pricing_missing",
                "pricing",
                "Pricing missing: " + ", ".join(pricing.missing) + ".",
            )
        )
    for alternative in pricing.alternatives:
        blocks.append(
            FactBlock(
                f"alternative_{alternative.supplier_id}",
                "alternative",
                (
                    f"Alternative {alternative.supplier_id} {alternative.display_name} "
                    f"{_dec_text(alternative.unit_price)} {alternative.currency} "
                    f"quote_only={alternative.quote_only} availability_assumed={alternative.availability_assumed} "
                    f"hypothetical_annual_difference={_dec_text(alternative.hypothetical_annual_difference)} "
                    f"same_country={alternative.same_country} same_category={alternative.same_category}."
                ),
            )
        )
    return blocks


def _contract_blocks(contracts: ContractsResult, load_date, schedule_dates) -> list[FactBlock]:
    if contracts.missing_contract:
        return [
            FactBlock(
                "no_contract",
                "contract",
                f"{contracts.supplier_id} has no contract on file.",
            )
        ]
    blocks = [
        FactBlock(
            "increase_allowed",
            "contract",
            (
                f"Contract {contracts.contract_id}: increase_allowed={contracts.increase_allowed} "
                f"cap_ratio={_dec_text(contracts.cap_ratio)} cap_price={_dec_text(contracts.cap_price)}."
            ),
        )
    ]
    if contracts.estimated_annual_value is not None and not contracts.estimated_annual_uncertain:
        annual_term = next((item for item in contracts.terms if item.field == "estimated_annual_value"), None)
        provenance = (
            f"clause {annual_term.clause} page {annual_term.page} sha256={annual_term.pdf_sha256}"
            if annual_term
            else "clause estimated_annual_value"
        )
        blocks.append(
            FactBlock(
                "estimated_annual_value",
                "contract",
                (
                    f"estimated_annual_value {format(contracts.estimated_annual_value, 'f')} "
                    f"{contracts.estimated_annual_currency or ''} from {provenance}."
                ),
            )
        )
    elif contracts.estimated_annual_uncertain:
        blocks.append(
            FactBlock(
                "estimated_annual_value_uncertain",
                "contract",
                "Estimated annual value was not evidenced in the contract terms.",
            )
        )
    exit_term = next((item for item in contracts.terms if item.field == "exit"), None)
    if exit_term:
        blocks.append(
            FactBlock(
                "exit_penalty",
                "contract",
                f"Exit clause {exit_term.clause} page {exit_term.page}: {exit_term.value}",
            )
        )
    if contracts.exit_penalty_uncertain:
        blocks.append(
            FactBlock(
                "exit_penalty_uncertain",
                "contract",
                "Exit penalty averaging period is unspecified; no amount is calculated from the annual estimate.",
            )
        )
    if (
        schedule_dates is not None
        and load_date is not None
        and contracts.expiry_offset_days is not None
        and contracts.notice_days is not None
    ):
        dates = schedule_dates(contracts.expiry_offset_days, contracts.notice_days, load_date)
        blocks.append(
            FactBlock(
                "expiry_notice",
                "contract",
                (
                    f"expiry {dates['expiry'].isoformat()} notice_deadline "
                    f"{dates['notice_deadline'].isoformat()} notice_days={contracts.notice_days}."
                ),
            )
        )
    return blocks


def render_fact_blocks(blocks: tuple[FactBlock, ...] | list[FactBlock]) -> str:
    return " ".join(block.text for block in blocks)


def catalog_for_model(blocks: tuple[FactBlock, ...]) -> list[dict[str, str]]:
    """IDs and categories only plus already-sanitized specialist text."""
    return [
        {"fact_id": block.fact_id, "category": block.category, "text": block.text}
        for block in blocks
    ]
