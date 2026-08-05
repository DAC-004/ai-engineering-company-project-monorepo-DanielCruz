# Rule: Milestone Source-of-Truth Guard

## Scope
Always active

## Purpose
Prevent repository regressions caused by modifying protected milestone artifacts, duplicating Milestone 2 logic, or confusing operational prompt files with deliverable source.

## Required behavior
- Use CONTEXT.md as business truth for company-specific content.
- Keep Milestone 2 logic sourced from src/ and integrated by import.
- Preserve uis/talent-pipeline-tracker/ unchanged unless explicit developer approval is given.
- Keep .project-input/ as operational guidance only and out of staged deliverable files.

## Prohibited behavior
- Copying or reimplementing src/ business logic into uis/backoffice or other apps.
- Modifying uis/talent-pipeline-tracker/ to satisfy Milestone 4 backoffice requirements.
- Treating .project-input/ files as submission artifacts.
- Using generic template assumptions when CONTEXT.md provides HealthCore-specific facts.

## Verification method
1. Run git status --short and inspect edited paths.
2. Confirm no modified files exist under uis/talent-pipeline-tracker/ unless explicitly approved.
3. Confirm no duplicate business-logic utility implementations were added outside src/.
4. Confirm .project-input/ remains operational and unstaged for submission.
