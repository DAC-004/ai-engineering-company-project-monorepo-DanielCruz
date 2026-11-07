"""Deterministic supervisor. Copies specialist figures; never recomputes them."""

from __future__ import annotations

from decimal import Decimal

from agents.supplier_contracts.alerts import emit_missing_dpa_alert, process_alerts
from agents.supplier_contracts.approvals import (
    UntrustedApproverError,
    annual_evidence_from_contract,
    confirm_dpa_proceed,
    create_draft,
    required_approvers,
)
from agents.supplier_contracts.constants import CONSULTATION_LIMIT
from agents.supplier_contracts.contracts import run_contracts, schedule_dates
from agents.supplier_contracts.actor import ActorIdentity
from agents.supplier_contracts.facts import FactBlock, fact_blocks_from_results, render_fact_blocks
from agents.supplier_contracts.interpret import interpret_plan_result, write_from_facts_result
from agents.supplier_contracts.identity import (
    ALERTS_ID,
    FORBIDDEN_TOOLS,
    SUPERVISOR_ID,
    SUPERVISOR_TOOLS,
)
from agents.supplier_contracts.pricing import run_pricing
from agents.supplier_contracts.privacy import (
    OutOfScopeError,
    PatientLevelError,
    assert_clean_mapping,
    is_credible_clause_number,
    reject_out_of_scope,
    reject_patient_level,
)
from agents.supplier_contracts.serialize import response_payload
from agents.supplier_contracts.registry import SUPPLIERS, require_supplier
from agents.supplier_contracts.runtime import ContractRuntime
from agents.supplier_contracts.types import (
    ContractsRequest,
    PricingRequest,
    PricingResult,
    SupervisorRequest,
    SupervisorResponse,
)


class ConsultationLimitError(ValueError):
    pass


_CONTRACT_TERM_MARKERS = (
    "notice",
    "expir",
    "deadline",
    "renew",
    "dpa",
    "baa",
    "exit",
    "penalt",
    "clause",
    "agreement",
)


def _contracts_required(kind: str, tools: tuple[str, ...], question: str) -> bool:
    """Skip PDFs only for a true compare-only alternatives path.

    consult_contracts in the plan, or a notice/expiry/deadline question, still
    loads contract terms even if the model labeled the kind as compare.
    """
    if "consult_contracts" in tools:
        return True
    if kind != "compare":
        return True
    lowered = question.lower()
    return any(marker in lowered for marker in _CONTRACT_TERM_MARKERS)


def _dec_text(value: Decimal | None) -> str:
    if value is None:
        return "unknown"
    return format(value, "f")


def _citations_from_contracts(result) -> tuple[str, ...]:
    return tuple(
        f"{item.field} clause {item.clause} page {item.page} sha256={item.pdf_sha256}"
        for item in result.terms
        if item.field != "billing" and is_credible_clause_number(item.clause)
    )


class Supervisor:
    def __init__(self, runtime: ContractRuntime, complete=None, transport=None) -> None:
        self.runtime = runtime
        self.complete = complete
        self.transport = transport
        self.consultations = 0
        self._immediate_alerts: list[dict] = []
        self.last_plan_source = "canonical"
        self.last_plan_kind = "question"
        self.last_plan_parsed_kind: str | None = None
        self.last_plan_parsed_kind_status = "no_model"
        self.last_plan_json_shape = "no_model"
        self.last_plan_tools: tuple[str, ...] = ()
        self.last_write_source = "canonical"
        self.last_write_json_shape = "no_model"
        self.last_write_unknown_id_count = 0
        self.last_write_unknown_id_digest: str | None = None
        self.last_write_selected_count = 0
        self.last_contracts_consulted = False

    def safe_generation_diagnostics(self) -> dict[str, object]:
        """Counts, schema enums, and ID digests only. No model text, names, or billing."""
        return {
            "plan_source": self.last_plan_source,
            "resolved_kind": self.last_plan_kind,
            "parsed_kind": self.last_plan_parsed_kind,
            "parsed_kind_status": self.last_plan_parsed_kind_status,
            "plan_json_shape": self.last_plan_json_shape,
            "plan_tools": list(self.last_plan_tools),
            "write_source": self.last_write_source,
            "write_json_shape": self.last_write_json_shape,
            "unknown_id_count": self.last_write_unknown_id_count,
            "unknown_id_digest": self.last_write_unknown_id_digest,
            "write_selected_count": self.last_write_selected_count,
            "contracts_consulted": self.last_contracts_consulted,
        }

    def _count(self, tool: str) -> None:
        if tool in FORBIDDEN_TOOLS:
            self.runtime.audit.write(SUPERVISOR_ID, tool, rejected="forbidden")
            raise ValueError("forbidden_tool")
        if tool not in SUPERVISOR_TOOLS:
            self.runtime.audit.write(SUPERVISOR_ID, tool, rejected="not_allowed")
            raise ValueError("tool_not_allowed")
        self.consultations += 1
        if self.consultations > CONSULTATION_LIMIT:
            raise ConsultationLimitError("consultation_limit")

    def consult_pricing(self, supplier_id: str, calculation: str, product: str | None = None) -> PricingResult:
        self._count("consult_pricing")
        request = PricingRequest(supplier_id=supplier_id, calculation=calculation, product=product)
        result = run_pricing(self.runtime.price_rows(), request)
        self.runtime.audit.write(result.actor_id, calculation, supplier_id=supplier_id, formula=result.formula)
        return result

    def consult_contracts(
        self,
        supplier_id: str,
        question: str,
        previous: Decimal | None = None,
        proposed: Decimal | None = None,
    ):
        self._count("consult_contracts")
        supplier = require_supplier(supplier_id)
        result = run_contracts(
            ContractsRequest(supplier_id=supplier_id, question=question, contract_id=supplier.contract_id),
            pdf_path=self.runtime.pdf_path(supplier.contract_id),
            load_date=self.runtime.load_date,
            previous_price=previous,
            proposed_price=proposed,
        )
        self.runtime.audit.write(result.actor_id, "load_sanitized_terms", supplier_id=supplier_id)
        self._enqueue_missing_dpa(result)
        return result

    def _enqueue_missing_dpa(self, result) -> dict:
        """Claire is notified as soon as extracted terms show a missing DPA, not on a later tick."""
        row = emit_missing_dpa_alert(self.runtime.store, result)
        if row:
            self._immediate_alerts.append(row)
            self.runtime.audit.write(
                ALERTS_ID,
                "enqueue_internal_alert",
                supplier_id=result.supplier_id,
                kind="missing_dpa",
                recipient="claire",
            )
        return row

    def _dpa_blocks(self, contracts_result) -> bool:
        if not contracts_result.missing_dpa:
            return False
        return not self.runtime.store.dpa_proceed(
            contracts_result.supplier_id, pdf_sha256=contracts_result.pdf_sha256,
            contract_id=contracts_result.contract_id,
        )

    def _compose_answer(self, pricing: PricingResult | None, contracts) -> str:
        parts: list[str] = []
        if pricing:
            parts.append(
                f"{pricing.supplier_id} {pricing.product}: previous {_dec_text(pricing.previous_price)} "
                f"current {_dec_text(pricing.current_price)} {pricing.currency}; "
                f"ratio {_dec_text(pricing.change_ratio)}; above_threshold={pricing.above_threshold}; "
                f"annual {_dec_text(pricing.annual_incremental)} {pricing.currency} "
                f"({_dec_text(pricing.annual_incremental_usd)} USD); formula {pricing.formula}; "
                f"source {','.join(pricing.source_row_ids)}; quote_only={pricing.quote_only}."
            )
            for alternative in pricing.alternatives:
                parts.append(
                    f"Alternative {alternative.supplier_id} {alternative.display_name} "
                    f"{_dec_text(alternative.unit_price)} {alternative.currency} "
                    f"quote_only={alternative.quote_only} availability_assumed={alternative.availability_assumed} "
                    f"hypothetical_annual_difference={_dec_text(alternative.hypothetical_annual_difference)} "
                    f"same_country={alternative.same_country} same_category={alternative.same_category}."
                )
            if pricing.missing:
                parts.append("Pricing missing: " + ", ".join(pricing.missing) + ".")
        if contracts:
            if contracts.missing_contract:
                parts.append(f"{contracts.supplier_id} has no contract on file.")
            else:
                parts.append(
                    f"Contract {contracts.contract_id}: increase_allowed={contracts.increase_allowed} "
                    f"cap_ratio={_dec_text(contracts.cap_ratio)} cap_price={_dec_text(contracts.cap_price)} "
                    f"dpa_status={contracts.dpa_status} missing_dpa={contracts.missing_dpa} "
                    f"exit_penalty_uncertain={contracts.exit_penalty_uncertain}."
                )
                if contracts.exit_penalty_uncertain:
                    parts.append(
                        "Exit penalty averaging period is unspecified; no amount is calculated from the annual estimate."
                    )
                if contracts.expiry_offset_days is not None and contracts.notice_days is not None:
                    dates = schedule_dates(
                        contracts.expiry_offset_days,
                        contracts.notice_days,
                        self.runtime.load_date,
                    )
                    parts.append(
                        f"expiry {dates['expiry'].isoformat()} notice_deadline "
                        f"{dates['notice_deadline'].isoformat()} notice_days={contracts.notice_days}."
                    )
            parts.extend(_citations_from_contracts(contracts))
        return " ".join(parts)

    def _blocked(self, reason: str, **fields) -> SupervisorResponse:
        return SupervisorResponse(
            answer=reason,
            blocked=True,
            block_reason=reason,
            pricing=fields.get("pricing"),
            contracts=fields.get("contracts"),
            citations=fields.get("citations", ()),
            consultation_count=self.consultations,
            required_approvers=fields.get("required_approvers", ()),
            alerts=fields.get("alerts", ()),
            actor_id=SUPERVISOR_ID,
        )

    def _portfolio_missing_agreements(self, question: str) -> SupervisorResponse:
        self.runtime.ensure_seeded()
        self.last_plan_kind = "missing_agreements"
        self.last_plan_source = "canonical"
        self.last_contracts_consulted = True
        answers, citations = [], []
        # The supplied registry has four patient-data processors; the normal
        # consultation cap still applies, with no recursive supervisor loop.
        for supplier in SUPPLIERS:
            if not supplier.processes_patient_data:
                continue
            result = self.consult_contracts(supplier.supplier_id, question)
            if result.missing_dpa:
                answers.append(f"{supplier.supplier_id} {supplier.display_name}: missing_dpa=True dpa_status={result.dpa_status}; "
                               + ("no contract on file." if result.missing_contract else f"contract {result.contract_id}."))
                citations.extend(_citations_from_contracts(result))
        answer = " ".join(answers) if answers else "No missing patient-data agreement was found in the supplied registry."
        self.runtime.audit.write(SUPERVISOR_ID, "portfolio_agreement_review", count=len(answers))
        response = SupervisorResponse(answer=answer, blocked=False, block_reason=None, pricing=None, contracts=None,
            citations=tuple(citations), consultation_count=self.consultations, required_approvers=(),
            alerts=tuple(self._immediate_alerts), actor_id=SUPERVISOR_ID)
        assert_clean_mapping(response_payload(response))
        return response

    def handle(self, request: SupervisorRequest) -> SupervisorResponse:
        self.consultations = 0
        self._immediate_alerts = []
        reject_patient_level(request.question)
        reject_out_of_scope(request.question)
        if request.kind == "tick_alerts":
            return self._tick_alerts()
        question_lower = request.question.lower()
        portfolio_question = ("which suppliers" in question_lower or "all suppliers" in question_lower) and any(
            marker in question_lower for marker in ("data protection agreement", "dpa", "baa", "missing agreement"))
        if portfolio_question or (request.kind == "missing_agreements" and not request.supplier_id):
            return self._portfolio_missing_agreements(request.question)
        if not request.supplier_id:
            raise ValueError("supplier_id_required")
        supplier = require_supplier(request.supplier_id)
        self.runtime.ensure_seeded()
        plan = interpret_plan_result(
            request.question,
            supplier.supplier_id,
            kind_hint=request.kind,
            complete=self.complete,
            transport=self.transport,
        )
        kind = plan.kind
        calculation = plan.calculation
        self.last_plan_source = plan.source
        self.last_plan_kind = kind
        self.last_plan_parsed_kind = plan.parsed_kind
        self.last_plan_parsed_kind_status = plan.parsed_kind_status
        self.last_plan_json_shape = plan.json_shape
        self.last_plan_tools = plan.tools
        self.runtime.audit.write(
            SUPERVISOR_ID,
            "interpret_plan",
            supplier_id=supplier.supplier_id,
            source=plan.source,
            kind=kind,
            json_shape=plan.json_shape,
            parsed_kind_status=plan.parsed_kind_status,
            tools=list(plan.tools),
        )
        pricing = None
        contracts = None
        self.last_contracts_consulted = False
        if kind != "missing_agreements":
            pricing = self.consult_pricing(supplier.supplier_id, calculation, supplier.product)
        if _contracts_required(kind, plan.tools, request.question):
            contracts = self.consult_contracts(
                supplier.supplier_id,
                request.question,
                pricing.previous_price if pricing else None,
                pricing.current_price if pricing else None,
            )
            self.last_contracts_consulted = True
        if kind in {"brief", "draft_communication"} and contracts and self._dpa_blocks(contracts):
            self._enqueue_missing_dpa(contracts)
            self.runtime.audit.write(SUPERVISOR_ID, "compose_brief", supplier_id=supplier.supplier_id, blocked="missing_dpa")
            response = self._blocked(
                "missing_dpa_blocks_brief_and_draft",
                contracts=contracts,
                pricing=pricing,
                citations=_citations_from_contracts(contracts) if contracts else (),
                alerts=tuple(self._immediate_alerts),
            )
            assert_clean_mapping(response_payload(response))
            return response
        annual, annual_evidenced = annual_evidence_from_contract(contracts)
        # Briefs and drafts must not drop Sandra when the PDF annual figure is unknown.
        # Informational answers for quote-only/missing-contract suppliers stay unblocked.
        approval_artifact = kind in {"brief", "draft_communication"}
        approvers = tuple(
            required_approvers(
                supplier.supplier_id,
                annual,
                annual_evidenced=annual_evidenced if approval_artifact else annual is not None,
            )
        )
        blocks = fact_blocks_from_results(
            pricing=pricing,
            contracts=contracts,
            required_approvers=approvers,
            load_date=self.runtime.load_date,
            schedule_dates=schedule_dates,
        )
        if contracts and self.runtime.load_date is not None:
            blocks += (FactBlock("source_load_date", "source", f"Data-load date {self.runtime.load_date.isoformat()} from the supplied fixture manifest."),)
        if kind in {"brief", "draft_communication"}:
            if pricing and not pricing.alternatives:
                blocks += (FactBlock("alternative_none", "brief_required", "No alternative quote was evidenced for this calculation; availability is not assumed."),)
            if contracts and contracts.increase_allowed is False:
                recommendation = "Recommendation for human review: challenge the increase against the cited revision clause; compare evidenced quotes and review notice/exit leverage before negotiating."
            elif contracts and contracts.increase_allowed is True:
                recommendation = "Recommendation for human review: a permitted cap does not require acceptance; compare evidenced quotes and review notice/exit terms before deciding."
            else:
                recommendation = "Recommendation for human review: contractual permission is unproven; obtain missing terms before a financial decision."
            blocks += (FactBlock("recommendation", "brief_required", recommendation),)
            required = {"price_change", "annual_impact", "pricing_missing", "alternative_none", "no_contract"}
            blocks = tuple(FactBlock(block.fact_id,
                "brief_required" if block.fact_id in required or block.category == "alternative" else block.category,
                block.text) for block in blocks)
        if self.complete is None and self.transport is None:
            answer = render_fact_blocks(blocks)
            self.last_write_source = "canonical"
            self.last_write_json_shape = "no_model"
            self.last_write_unknown_id_count = 0
            self.last_write_unknown_id_digest = None
            self.last_write_selected_count = 0
        else:
            write = write_from_facts_result(
                request.question,
                blocks,
                complete=self.complete,
                transport=self.transport,
            )
            answer = write.answer
            self.last_write_source = write.source
            self.last_write_json_shape = write.json_shape
            self.last_write_unknown_id_count = write.unknown_id_count
            self.last_write_unknown_id_digest = write.unknown_id_digest
            self.last_write_selected_count = write.selected_count
        self.runtime.audit.write(
            SUPERVISOR_ID,
            "write_from_facts",
            supplier_id=supplier.supplier_id,
            source=self.last_write_source,
            json_shape=self.last_write_json_shape,
            unknown_id_count=self.last_write_unknown_id_count,
            unknown_id_digest=self.last_write_unknown_id_digest,
        )
        alerts = tuple(self._immediate_alerts)
        draft = None
        if kind == "draft_communication":
            self._count("draft_communication")
            draft = create_draft(
                self.runtime.store,
                supplier_id=supplier.supplier_id,
                kind="draft_communication",
                body=answer,
                annual_usd=annual,
                annual_evidenced=annual_evidenced,
            )
        if kind == "brief":
            self._count("compose_brief")
            answer = "Renegotiation brief. " + answer + f" Required approvers: {', '.join(approvers)}."
        response = SupervisorResponse(
            answer=answer,
            blocked=False,
            block_reason=None,
            pricing=pricing,
            contracts=contracts,
            citations=_citations_from_contracts(contracts) if contracts else (),
            consultation_count=self.consultations,
            required_approvers=approvers,
            alerts=alerts,
            actor_id=SUPERVISOR_ID,
            draft=draft,
        )
        self.runtime.audit.write(SUPERVISOR_ID, request.kind, supplier_id=supplier.supplier_id)
        assert_clean_mapping(response_payload(response))
        return response

    def confirm_dpa(self, actor: ActorIdentity, supplier_id: str) -> None:
        self.runtime.ensure_seeded()
        supplier = require_supplier(supplier_id)
        extracted = run_contracts(
            ContractsRequest(supplier_id=supplier_id, question="compliance confirmation", contract_id=supplier.contract_id),
            pdf_path=self.runtime.pdf_path(supplier.contract_id), load_date=self.runtime.load_date,
        )
        confirm_dpa_proceed(self.runtime.store, actor, supplier_id, contracts=extracted)
        self.runtime.audit.write(
            SUPERVISOR_ID,
            "dpa_proceed",
            supplier_id=supplier_id,
            confirmed_by="claire",
            actor_user_id=actor.user_id,
            contract_id=extracted.contract_id or "none",
            pdf_sha256=extracted.pdf_sha256 or "missing_contract",
            missing_dpa=extracted.missing_dpa,
        )

    def _tick_alerts(self) -> SupervisorResponse:
        self._count("enqueue_internal_alert")
        self.runtime.ensure_seeded()
        rows = self.runtime.price_rows()
        pricing_by_supplier = {}
        contracts_by_supplier = {}
        for supplier in SUPPLIERS:
            try:
                pricing_by_supplier[supplier.supplier_id] = run_pricing(
                    rows,
                    PricingRequest(supplier_id=supplier.supplier_id, calculation="increase", product=supplier.product),
                )
            except Exception:
                continue
            contracts_by_supplier[supplier.supplier_id] = run_contracts(
                ContractsRequest(supplier_id=supplier.supplier_id, question="tick", contract_id=supplier.contract_id),
                pdf_path=self.runtime.pdf_path(supplier.contract_id),
                load_date=self.runtime.load_date,
            )
        emitted = process_alerts(
            self.runtime.store,
            today=self.runtime.today,
            pricing_by_supplier=pricing_by_supplier,
            contracts_by_supplier=contracts_by_supplier,
        )
        self.runtime.audit.write(SUPERVISOR_ID, "enqueue_internal_alert", count=len(emitted))
        return SupervisorResponse(
            answer=f"emitted {len(emitted)} alerts",
            blocked=False,
            block_reason=None,
            pricing=None,
            contracts=None,
            citations=(),
            consultation_count=self.consultations,
            required_approvers=(),
            alerts=tuple(emitted),
            actor_id=SUPERVISOR_ID,
        )


def handle(runtime: ContractRuntime, request: SupervisorRequest) -> SupervisorResponse:
    try:
        return Supervisor(runtime).handle(request)
    except PatientLevelError as exc:
        runtime.audit.write(SUPERVISOR_ID, "reject_patient_level")
        return SupervisorResponse(
            answer="patient_level_data_rejected",
            blocked=True,
            block_reason=str(exc),
            pricing=None,
            contracts=None,
            citations=(),
            consultation_count=0,
            required_approvers=(),
            alerts=(),
            actor_id=SUPERVISOR_ID,
        )
    except OutOfScopeError as exc:
        runtime.audit.write(SUPERVISOR_ID, "reject_out_of_scope")
        return SupervisorResponse(
            answer="out_of_scope",
            blocked=True,
            block_reason=str(exc),
            pricing=None,
            contracts=None,
            citations=(),
            consultation_count=0,
            required_approvers=(),
            alerts=(),
            actor_id=SUPERVISOR_ID,
        )
    except UntrustedApproverError as exc:
        return SupervisorResponse(
            answer="untrusted_approver",
            blocked=True,
            block_reason=str(exc),
            pricing=None,
            contracts=None,
            citations=(),
            consultation_count=0,
            required_approvers=(),
            alerts=(),
            actor_id=SUPERVISOR_ID,
        )
    except ConsultationLimitError as exc:
        return SupervisorResponse(
            answer="consultation_limit",
            blocked=True,
            block_reason=str(exc),
            pricing=None,
            contracts=None,
            citations=(),
            consultation_count=CONSULTATION_LIMIT,
            required_approvers=(),
            alerts=(),
            actor_id=SUPERVISOR_ID,
        )
