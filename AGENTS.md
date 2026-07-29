# Repository Agent Operating Guide

## Mandatory session-start reads
Every coding agent must read these files at the beginning of each session, in order:
1. memory-bank/projectbrief.md
2. memory-bank/techContext.md
3. memory-bank/progress.md
4. .project-input/milestone-4/PROJECT-REQUIREMENTS.md
5. .project-input/milestone-4/HUMAN-DECISIONS.md
6. .project-input/milestone-4/BRANCH-SOURCE-MAP.md
7. CONTEXT.md
8. Root and relevant folder README files for the area being changed

## Source-of-truth and anti-duplication rules
- Do not duplicate Milestone 2 business logic from src/ into any new app.
- Preserve Milestone 3 artifact at uis/talent-pipeline-tracker/ unchanged.
- Treat CONTEXT.md as business truth and avoid generic placeholder assumptions.
- Treat .project-input/ as operational instruction material, not submission deliverable content.

## Protected files and folders (require explicit developer approval)
- .project-input/
- uis/talent-pipeline-tracker/
- src/ business-logic behavior and contracts
- Root deployment files for Milestone 1 delivery (vercel.json and scripts/deploy-vercel.sh)

## Conditions that require stopping for human review
- Missing or conflicting source-of-truth evidence.
- Any requested change that would modify protected paths.
- Any need to restore Milestone 2 root tooling from commit e713999 without a reproducible integration failure.
- Any ambiguity about whether a change introduces duplication of business logic.
- Any need for Git write operations.

## Mandatory pre-commit workflow
1. Scope check: confirm all edited files are inside approved phase scope and not in protected paths.
2. Source check: verify every technical claim against repository files and update memory-bank/progress.md with current state changes.
3. Validation check: run only relevant validation commands for affected workspaces.
4. Diff check: review git status --short and ensure .project-input/ remains unstaged operational material.
5. Commit prep check: provide exact staging file list and one proposed commit message; stop for developer-run Git writes.

## Validation expectations by workspace
- Root static-site changes: run npm run start when runtime behavior is affected.
- uis/website changes (future phase): run npm run dev in that app; run additional checks required by phase instructions.
- uis/backoffice changes (future phase): run npm run dev and verify Milestone 2 output is visibly rendered.
- uis/talent-pipeline-tracker is preserved; no validation runs should be triggered by direct edits because edits are disallowed without explicit approval.

## Progress tracking requirement
- Whenever project state changes, update memory-bank/progress.md in the same phase so future agents inherit accurate state.

## Git restrictions
Agents must not execute Git write operations, including: git add, git commit, git push, branch creation/switch, merge, rebase, cherry-pick, reset, restore, clean, or Git config/credential changes.
Read-only Git inspection commands are allowed.
