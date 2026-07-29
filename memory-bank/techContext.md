# Technical Context

## Verified technology stack
- Root static Milestone 1 site: HTML + Tailwind CDN + browser JavaScript.
- Root Node tooling: npm scripts for local static serving and Vercel deployment.
- Milestone 2 module: TypeScript source under src/ with utility functions, domain types, sample data, and tests.
- Milestone 3 app: Next.js + React + TypeScript app under uis/talent-pipeline-tracker.

## Monorepo and workspace structure
- Single Git repository with top-level domains: uis/, services/, data/, agents/, skills/, mcps/, workflows/, packages/, shared/, docs/, infra/, scripts/, internal/, src/.
- No npm workspace configuration at root package.json.
- Separate package contexts currently exist at root and uis/talent-pipeline-tracker.

## Architectural boundaries
- Milestone 1 authoritative website artifacts are currently at repository root.
- Milestone 2 authoritative business logic is at src/.
- Milestone 3 authoritative artifact is uis/talent-pipeline-tracker/ and must be preserved unchanged.
- Milestone 4 requires new apps in uis/website and uis/backoffice (later phases).
- APIs must live in services/ only when explicitly required.

## Source-of-truth locations
- Company/business context: CONTEXT.md
- Milestone 1 public site: index.html, application.html, validation.js, assets/backgrounds/
- Milestone 2 logic: src/types/, src/utils/, src/data/, src/tests/, src/app.ts
- Milestone 3 artifact: uis/talent-pipeline-tracker/
- Milestone 4 governing requirements: .project-input/milestone-4/PROJECT-REQUIREMENTS.md
- Approved human constraints: .project-input/milestone-4/HUMAN-DECISIONS.md
- Branch integration map: .project-input/milestone-4/BRANCH-SOURCE-MAP.md

## Existing technical decisions and constraints
- Source-only first for Milestone 2 integration under src/.
- Minimal tooling adaptation from commit e713999 is allowed only after reproducible integration failure tied to missing M2 config.
- Do not repurpose or modify uis/talent-pipeline-tracker for Milestone 4 backoffice work.
- Keep .project-input/ operational and unstaged for submission.

## Validation commands currently available
- Root static site: npm run start
- Root Vercel tasks: npm run vercel:login, npm run vercel:link, npm run vercel:deploy
- Milestone 3 app checks (from app directory): npm run dev, npm run lint, npm run build
- Git read-only phase checks: git status --short, git branch --show-current

## Areas requiring explicit developer approval before modification
- .project-input/
- uis/talent-pipeline-tracker/
- src/ business-logic semantics (beyond integration-safe import usage)
- Root deployment settings tied to Milestone 1 delivery (vercel.json, deployment scripts)

## Uncertainties still unresolved
- Exact minimum config changes needed for importing src/ into uis/backoffice cannot be finalized until integration testing in that app.
- Root TypeScript build/test commands from original Milestone 2 commit are intentionally excluded and should only be restored if a verified failure requires them.
