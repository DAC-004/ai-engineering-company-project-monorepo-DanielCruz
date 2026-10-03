# HealthCore Project Brief

## Verified company description
HealthCore is an outpatient healthcare network founded in 2011 in Austin, Texas. It operates 12 clinics across the US (Texas, Florida, Georgia) and UK (London, Manchester), with about 200 employees and cross-jurisdiction compliance obligations (HIPAA and UK GDPR).

## Business problem
HealthCore has grown faster than its systems. Core problems are fragmented records across US/UK systems, high no-show rates, billing denials, manual compliance processes, and inconsistent leadership visibility into real-time KPIs.

## Project objectives for this monorepo
1. Keep one coherent company monorepo as the implementation base.
2. Preserve approved milestone artifacts as sources of truth.
3. Evolve from static/public and utility artifacts into maintainable applications under uis/.
4. Prepare an AI-ready structure that can later support services, agents, skills, and workflows without duplicating business logic.

## Primary stakeholders documented in context
- Executive leadership: Dr. Sandra Okonkwo
- Clinical Operations: Dr. Marcus Reid
- Patient Experience and Access: Priya Nair
- Revenue Cycle and Billing: Tom Callahan
- Compliance and Data Governance: Claire Whitfield
- People and Workforce: Diane Foster
- Technology: James Osei and the HealthCore Digital team

## Scope boundaries for Milestone 4
- Build required agent infrastructure first.
- Build separate uis/website and uis/backoffice apps in later phases.
- Integrate Milestone 2 business logic by importing from src/; no duplication.
- Do not alter Milestone 3 artifact at uis/talent-pipeline-tracker.
- Do not add speculative product APIs, product agents, or product skills in this phase.

## Relationship among repository components
- Public website: current source of truth is root static site (index.html, application.html, validation.js); later migrated to uis/website.
- Business logic: TypeScript module in src/ (Milestone 2) is the reusable logic source.
- Back office: must be a separate app under uis/backoffice and consume src/ logic by import.
- Future services: centralized APIs belong under services/ when required by milestone scope.
- Agent infrastructure: root AGENTS.md plus memory-bank and .agents rules/skills guide coding-agent behavior.
- Product agents and automations: reserved for agents/, skills/, mcps/, workflows/ in future phases when explicitly required.
