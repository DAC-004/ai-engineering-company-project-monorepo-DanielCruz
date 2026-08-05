# Skill: Milestone Phase Readiness Check

## Objective
Produce a repository-grounded readiness report before closing a milestone phase, confirming scope compliance, validations, and staging safety.

## When to use
- Before asking the developer to commit phase work.
- After implementing changes that span multiple folders.
- When requirements include explicit validation and source-of-truth compliance checks.

## Inputs
- Phase requirement file path (for example .project-input/milestone-4/02-AGENT-INFRASTRUCTURE.md).
- Current human decisions file path.
- List of files changed in the phase.
- Required validation commands for affected workspaces.

## Expected output
A structured checklist report that includes:
1. Requirement-by-requirement status (satisfied, partial, missing, uncertain).
2. Validation commands executed and observed outcome.
3. git status --short summary.
4. Exact files ready for staging.
5. One proposed commit message.
6. Any stop conditions that require human decision.

## Ordered execution requirements
1. Read the phase requirement file and extract mandatory deliverables and exclusions.
2. Read HUMAN-DECISIONS and apply the latest approved constraints.
3. Compare changed files against scope and protected-path rules.
4. Run required validation commands for only the affected workspaces.
5. Collect git status --short and classify files as stageable or operational-only.
6. Generate the final readiness report and stop for human Git actions.

## Acceptance criteria (independently verifiable)
- Exactly one objective is stated.
- Inputs and expected outputs are explicitly documented.
- The execution section is ordered and actionable.
- The output includes git status --short, stageable files, and one commit message.
- Report flags .project-input/ as operational-only when present.
- Report does not claim validations that were not run.

## Failure and stop conditions
- Stop if source-of-truth files conflict and no human decision resolves precedence.
- Stop if required validations cannot be executed in the available workspace.
- Stop if protected files are modified without explicit approval.
- Stop if the phase request exceeds declared scope (for example, asks for product features during infrastructure phase).
