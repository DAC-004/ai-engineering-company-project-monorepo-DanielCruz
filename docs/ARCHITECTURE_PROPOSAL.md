# HealthCore Backend Architecture Proposal

## Purpose and Scope

This document proposes how HealthCore's future backend should be organized before implementation starts.

It is a technical reasoning artifact only. It does not include runnable backend code, package installation, endpoint implementation, or database setup.

## Repository and Business Evidence Used

This proposal is based on the current transversal monorepo and approved milestone artifacts:

- HealthCore business and operations context in [CONTEXT.md](../CONTEXT.md)
- Milestone 1 care-request fields and rules in [application.html](../application.html) and [validation.js](../validation.js)
- Milestone 2 domain models and transformation/validation logic in [src/types/models.ts](../src/types/models.ts), [src/utils/validations.ts](../src/utils/validations.ts), and [src/utils/transformations.ts](../src/utils/transformations.ts)
- Milestone 4 monorepo boundaries in [README.md](../README.md), [services/README.md](../services/README.md), [uis/README.md](../uis/README.md), [uis/website/README.md](../uis/website/README.md), and [uis/backoffice/README.md](../uis/backoffice/README.md)
- Existing architectural constraints in [AGENTS.md](../AGENTS.md), [memory-bank/projectbrief.md](../memory-bank/projectbrief.md), and [memory-bank/techContext.md](../memory-bank/techContext.md)

## 1. Proposed Architectural Pattern

### Pattern selection

The recommended pattern is a domain-oriented modular monolith using layered architecture, implemented as one central FastAPI backend inside services.

In practical terms:

- One backend application (single deployment unit) for the current phase
- Multiple domain modules (care requests, appointments, clinics, billing, compliance, workforce, reporting)
- Layers inside each domain (router/API layer, application/service layer, domain rules layer, infrastructure/adapters layer)

### Why this fits HealthCore specifically

HealthCore is not a small single-flow app. It is a cross-country healthcare operation with:

- Two jurisdictions (US and UK) and dual compliance constraints (HIPAA and UK GDPR)
- Interdependent workflows (care access, scheduling, billing outcomes, compliance evidence, executive KPI reporting)
- Existing validated business rules from Milestone 1 and Milestone 2 that must stay consistent across web forms, internal dashboards, and future API clients

A modular monolith keeps those cross-domain rules consistent while the team is still in early backend formation. It avoids premature distributed complexity while preserving clear boundaries for later extraction if needed.

### Strengths

- Strong consistency for shared rules (for example, country-dependent phone/payment/member identifier rules)
- Lower operational overhead than microservices during early delivery
- Easier traceability for regulated workflows because domain rules and audit-related logic stay in one controlled codebase
- Compatible with current repository guidance that centralizes backend work under services

### Limitations and tradeoffs

- Requires strict module boundaries to avoid becoming a "big ball of mud"
- Team coordination is needed to prevent cross-domain shortcuts in routers/services
- Independent scaling per domain is limited compared with fully split services

### Consequence of this decision

The team should optimize for domain boundaries first, deployment splitting later. If operational load or ownership pressure grows, domains can be extracted incrementally from an already modular internal structure.

## 2. Proposed Backend Folder and Module Structure

### Location in current monorepo

The backend should live under services, consistent with current repository guidance:

- services/api as the single backend service for now

### Proposed structure

```text
services/
  api/
    app/
      main.py
      core/
        config.py
        cors.py
        security.py
      schemas/
        common.py
      routers/
        health.py
        care_requests.py
        appointments.py
        clinics.py
        billing.py
        compliance.py
        workforce.py
        reporting.py
      domains/
        care_requests/
          service.py
          validators.py
          models.py
        appointments/
          service.py
          models.py
        clinics/
          service.py
          models.py
        billing/
          service.py
          models.py
        compliance/
          service.py
          models.py
        workforce/
          service.py
          models.py
        reporting/
          service.py
          models.py
      repositories/
        interfaces.py
      integrations/
        ehr_us.py
        ehr_uk.py
      tests/
        ...
```

### Separation criteria

- Domain separation: aligned with HealthCore operating units and workflows in CONTEXT
- Responsibility separation:
  - routers: HTTP contracts and request/response handling
  - domains/*/service.py: use-case orchestration and domain rules
  - domains/*/validators.py: explicit business rule validation (including cross-field and country-specific checks)
  - repositories/integrations: data-source adapters and external-system boundaries
  - core: cross-cutting concerns (configuration, CORS, shared security hooks)

This organization aligns with the selected pattern because domain modules remain isolated while still sharing a single application runtime.

## 3. Proposed FastAPI Routers and Endpoint Grouping

### Router grouping strategy

Routers are grouped by business domain, not by HTTP method and not by technical type alone.

Suggested route groups:

- /health
  - Operational health checks for platform monitoring
- /care-requests
  - Public and internal flows around submitted care requests
  - Justification: Milestone 1 and Milestone 2 center on care-request data and validation rules
- /appointments
  - Scheduling state and appointment lifecycle operations
  - Justification: linked to care requests and no-show tracking requirements
- /clinics
  - Clinic metadata, location mappings, and country alignment rules
  - Justification: existing country-location constraints are explicit in current artifacts
- /billing
  - Payment models, claims/denial workflow surfaces, and revenue-cycle operations
  - Justification: strong business pressure from high denial rate in US and mixed UK payment models
- /compliance
  - Consent, audit-support, and jurisdiction-related policy surfaces
  - Justification: HIPAA and UK GDPR obligations are first-class operational constraints
- /workforce
  - HR-related operational endpoints for internal workflows
  - Justification: current business context includes hiring, onboarding, and CME tracking gaps
- /reporting
  - Aggregated KPI and operational metrics endpoints for backoffice/executive views
  - Justification: existing Milestone 2 reporting logic and executive KPI needs

### Domain alignment note

The route groups above are intentionally aligned with real HealthCore departments and workflows rather than generic CRUD-only grouping.

## 4. FastAPI Conventions and How They Influence This Proposal

### Conventions applied

From FastAPI's documented "bigger applications" guidance:

- Keep a clear application entry point (app/main.py)
- Split routers into separate modules and register with include_router
- Use APIRouter prefixes/tags/dependencies at router scope to reduce duplication
- Keep shared dependencies and config in dedicated modules

From FastAPI's CORS and settings guidance:

- Configure explicit allowed origins for browser clients instead of wildcard when credentials may be used
- Keep environment-dependent configuration in environment variables with typed validation

### Impact on final proposal

These conventions directly drive:

- A small composition root (main.py)
- Domain-specific router files under routers/
- Centralized config/CORS handling under core/
- Environment-driven backend URLs/origins by deployment stage

### Research sources

- FastAPI docs: Bigger Applications - Multiple Files
  - https://fastapi.tiangolo.com/tutorial/bigger-applications/
- FastAPI docs: CORS
  - https://fastapi.tiangolo.com/tutorial/cors/
- FastAPI docs: Settings and Environment Variables
  - https://fastapi.tiangolo.com/advanced/settings/

## 5. Frontend and Backend as Separate Systems

### Current repository reality

The monorepo already contains separate frontend applications:

- Public app in uis/website
- Internal app in uis/backoffice

The backend should remain a separate service under services, communicating through HTTP APIs.

### API communication model

- Browser clients call backend endpoints over HTTPS using environment-specific base URLs
- Frontends should not import backend runtime internals directly
- Shared contracts should be versioned at API boundary; if needed, shared DTO/type definitions can be placed under shared package locations, without duplicating business behavior

### Environment variables and base URL strategy

At minimum:

- website frontend: NEXT_PUBLIC_API_BASE_URL
- backoffice frontend: NEXT_PUBLIC_API_BASE_URL
- backend service: allowed-origin and service-config env vars per environment

Expected environment behavior:

- Local development: frontend localhost origins point to local backend base URL
- Production: frontend deployed origins point to production backend URL

### CORS policy implications

- Allow only explicit origins for website and backoffice deployments
- Avoid blanket wildcard origin in environments that require credentials or protected headers
- Maintain separate allowed-origin lists for development and production to reduce accidental exposure

### Monorepo boundary recommendation

Keep one repository with separate runtime units:

- uis/website (public frontend)
- uis/backoffice (internal frontend)
- services/api (backend)

This is consistent with existing monorepo structure and avoids introducing a repository split before backend contracts stabilize.

## 6. Risks and Points of Attention

1. Mixed responsibilities across routers and domain services
If teams put business rules directly into route handlers, behavior will diverge between endpoints and become difficult to test. For HealthCore this is high risk because country and compliance rules are strict and cross-field.

2. Duplicate rule definitions between frontend and backend without a clear source of truth
Current validations already exist in Milestone 1 and Milestone 2 artifacts. If backend redefines these inconsistently, patients and operators can see contradictory acceptance/rejection results.

3. Route sprawl and unclear ownership
If endpoints are added to generic files (for example, one catch-all router), team ownership weakens and future changes for billing/compliance/workforce interfere with each other.

4. CORS and environment misconfiguration
If allowed origins/base URLs are not environment-specific, frontends can fail in production or expose broader attack surface than intended.

5. Compliance traceability gaps
If compliance-sensitive operations are spread with no clear module boundary, audit and legal review work becomes costly and error-prone under HIPAA/UK GDPR obligations.

## 7. Known Unknowns and Explicit Gaps

The repository and current milestones do not yet define several implementation-level decisions. These should be resolved before coding starts, not guessed during endpoint development:

- Authoritative identity/authentication model for public users vs internal staff
- Persistence and data ownership boundaries across US EHR, UK EHR, billing tools, and internal stores
- Priority sequencing of domain rollout (which domain routers are implemented first)

No assumptions are made here beyond the available evidence.

## 8. Decision Summary

Proposed direction:

- Build one FastAPI backend service under services/api
- Use a domain-oriented layered modular monolith
- Organize routers by HealthCore business domains
- Keep frontend and backend as separate systems connected via explicit API contracts
- Enforce environment-specific base URL and CORS configuration from day one
- Treat compliance and consistency risks as first-order architecture constraints

This structure gives the team immediate implementation clarity while preserving room for future extraction and scaling.