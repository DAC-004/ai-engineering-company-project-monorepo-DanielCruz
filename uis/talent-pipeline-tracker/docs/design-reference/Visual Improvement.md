# VISUAL_ONLY_HEALTHCORE_UPGRADE_PROMPT.md

You are acting as a Senior Full Stack Developer and master expert in Next.js App Router, TypeScript, React, Tailwind CSS, and REST API frontend implementation.

Your task is a **visual-only upgrade** for the existing Milestone 3 Talent Pipeline Tracker.

Do **not** rebuild the app. Do **not** change business logic. Do **not** change API behavior. Do **not** change routing behavior. Do **not** change data models. Do **not** add new features. This is strictly a professional UI polish pass so the Talent Pipeline Tracker visually matches the HealthCore public site while remaining fully compliant with the Milestone 3 rubric.

---

## Task Title

HealthCore Visual-Only Upgrade for Milestone 3 Talent Pipeline Tracker

---

## Objective

Improve only the visual presentation of the existing Talent Pipeline Tracker so it feels coherent with the HealthCore public website:

`https://workspace-eosin-zeta-flax.vercel.app/`

The final UI must look like an internal HealthCore People & Talent operations dashboard for a healthcare outpatient care network. The interface should feel professional, calm, clinical, organized, readable, and production-ready.

This is not a redesign of functionality. It is a visual refinement pass only.

---

## Required Visual Direction

Use the HealthCore public website as the visual reference.

The internal Talent Pipeline Tracker should visually align with these characteristics:

- Healthcare operations dashboard aesthetic.
- Clean white and very light blue/slate backgrounds.
- Professional blue accents.
- Slate or neutral text colors.
- Soft borders.
- Rounded cards and panels.
- Clear spacing and readable hierarchy.
- Calm, clinical, trustworthy visual tone.
- Modern but restrained layout.
- Accessibility-first contrast.
- No playful, cartoonish, neon, gaming, or generic startup styling.

The app must feel like it belongs to HealthCore, an outpatient healthcare organization, not like a generic recruiting demo.

---

## Strict Milestone 3 Compliance Rules

You must preserve all existing Milestone 3 functionality and rubric requirements.

Do not break or alter any of the following:

- Candidate list page at `/`.
- Candidate detail page at `/candidates/[id]`.
- Candidate fetching from `GET /records`.
- Single candidate fetching from `GET /records/:id`.
- Status filtering.
- Stage filtering.
- URL query parameter behavior using App Router search params.
- Search by candidate name or email without full page reload.
- Candidate detail navigation.
- Status update using `PATCH /records/:id`.
- Stage update using `PATCH /records/:id`.
- Notes list using `GET /records/:id/notes`.
- Add note using `POST /records/:id/notes`.
- Delete note using `DELETE /records/:id/notes/:note_id`.
- Candidate creation using `POST /records`.
- Candidate editing using `PUT /records/:id`.
- Async loading states.
- Async success feedback.
- Async error feedback.
- TypeScript API types.
- Existing REST API contracts.
- Existing validation behavior.
- Existing route structure.
- Existing App Router navigation behavior.
- Existing environment variable behavior.
- Existing folder organization.

If any proposed visual change risks breaking one of these requirements, do not make that change.

---

## Reference Files to Inspect

Before changing anything, inspect the existing Milestone 3 reference screenshots located at:

`/uis/talent-pipeline-tracker/docs/design-reference/`

Expected files:

- `Submit.png`
- `Evaluation(2).png`
- `Code Structure.png`
- `State-Async Handling.png`
- `Candidate.png`
- `Views-Routing.png`

Use these screenshots only as rubric and evaluation references. Do not import them into the app. Do not display them in the UI. Do not move or delete them.

---

## Scope of Allowed Changes

You may change only visual and presentation-related code.

Allowed:

- Tailwind class names.
- Spacing.
- Borders.
- Typography scale.
- Font weight.
- Background colors.
- Card styling.
- Table styling.
- Form control styling.
- Button styling.
- Badge styling.
- Empty state styling.
- Loading state styling.
- Error state styling.
- Success state styling.
- Page shell layout.
- Header visual structure.
- Responsive layout classes.
- Visual grouping of existing information.
- Accessibility improvements that do not change behavior.
- Small JSX wrapper elements only when needed for layout or visual hierarchy.

Not allowed:

- No API endpoint changes.
- No API client behavior changes.
- No request method changes.
- No response shape changes.
- No type model changes unless required only for visual display and already compatible.
- No route changes.
- No page renames.
- No query parameter behavior changes.
- No search behavior changes.
- No filtering behavior changes.
- No note behavior changes.
- No create/edit behavior changes.
- No validation logic changes.
- No state-management changes.
- No new external state library.
- No new UI component library.
- No Redux, Zustand, Jotai, MobX, shadcn, MUI, Chakra, DaisyUI, Bootstrap, or Ant Design.
- No full page reloads.
- No unrelated refactors.
- No fake data replacing API data.
- No hardcoded candidate data.
- No removal of loading, success, or error states.
- No weakening TypeScript with broad `any` usage.

---

## Visual Upgrade Requirements

### 1. Overall App Shell

Upgrade the app shell to feel like a HealthCore internal dashboard.

Use:

- Light page background.
- Clean max-width container.
- Professional header area.
- Strong page title hierarchy.
- Subtle HealthCore-oriented supporting copy.
- Card-based sections with soft borders and shadows.
- Consistent spacing between sections.

Avoid:

- Harsh black backgrounds.
- Neon colors.
- Oversized gradients.
- Cartoon icons.
- Unstructured vertical lists.
- Cheap-looking default form controls.

---

### 2. Header and Page Titles

Improve visual hierarchy for the main dashboard and detail pages.

Preferred user-facing visual labels, if these labels already exist or can be adjusted without affecting logic:

- `HealthCore People & Talent`
- `Internal Talent Pipeline`
- `Candidate Records`
- `Candidate Record`
- `Application Status`
- `Hiring Stage`
- `Internal Notes`
- `Register Candidate`
- `Update Candidate Record`

Only adjust user-facing text when it does not conflict with the milestone requirements or existing API/data behavior.

---

### 3. Candidate List Page Visuals

Improve the `/` page visually while preserving all behavior.

The candidate list should:

- Display candidates in a clean table, card list, or responsive hybrid layout.
- Clearly show candidate name, position, status, and stage.
- Make each candidate row/card visually clickable without breaking Next.js navigation.
- Use status and stage badges with restrained healthcare-style colors.
- Keep filters and search visually grouped in a professional toolbar.
- Show empty states in a polished card or panel.
- Show loading states in a clear, non-jarring way.
- Show error states with visible but professional styling.

Search and filters must continue working without full page reload.

---

### 4. Filter and Search Visuals

Improve search and filter controls visually.

Controls should:

- Be aligned and grouped logically.
- Use accessible labels.
- Have consistent height, padding, border radius, and focus states.
- Use HealthCore-like blue focus rings or border accents.
- Work well on mobile and desktop.

Do not change filter logic. Do not remove URL query parameter behavior.

---

### 5. Candidate Detail Page Visuals

Improve `/candidates/[id]` visually while preserving all behavior.

The detail page should:

- Present candidate information in organized cards or sections.
- Make key fields easy to scan.
- Visually separate contact details, application details, status/stage controls, and notes.
- Keep status and stage update controls easy to find.
- Make update feedback visible and professional.
- Preserve all existing PATCH behavior.
- Preserve all existing note behavior.

Do not change the candidate ID routing behavior.

---

### 6. Forms Visuals

Improve candidate create/edit forms visually while preserving all submission and validation behavior.

Forms should:

- Use consistent labels.
- Use clean input styling.
- Show inline validation clearly.
- Have visually distinct primary and secondary actions.
- Use readable spacing.
- Look appropriate for a professional internal healthcare operations tool.

Do not change form data contracts. Do not change validation logic except for purely visual presentation of existing validation messages.

---

### 7. Notes Visuals

Improve internal notes presentation visually.

Notes should:

- Appear as clear internal review items.
- Show note content in readable cards or rows.
- Keep delete actions visible but not visually aggressive.
- Preserve note add and delete behavior.
- Preserve note loading, success, and error feedback.

---

### 8. Loading, Success, Error, and Empty States

The screenshots emphasize async handling. Do not remove or hide these states.

Upgrade them visually:

- Loading states should look intentional.
- Error states should be visible, professional, and understandable.
- Success states should be subtle but clear.
- Empty states should explain what happened without sounding casual or playful.

Do not introduce silent failures.

---

### 9. Responsive Behavior

Ensure the visual upgrade remains usable across common viewport sizes.

Required:

- Mobile-friendly layout.
- Desktop layout with clear spacing.
- No horizontal overflow.
- Forms remain readable.
- Tables or candidate lists adapt cleanly.
- Buttons and controls remain usable on smaller screens.

Do not change routing or functional behavior to achieve responsiveness.

---

## Accessibility Requirements

Preserve or improve accessibility.

Required:

- Maintain visible focus states.
- Maintain semantic labels for inputs and selects.
- Preserve readable color contrast.
- Do not rely on color alone for critical status meaning.
- Keep buttons identifiable.
- Keep links visually recognizable.
- Do not replace text labels with unlabeled icons.

---

## Implementation Method

Proceed carefully:

1. Inspect the current UI files.
2. Identify components/pages that control layout and visual presentation.
3. Apply visual-only Tailwind refinements.
4. Keep API, state, hooks, handlers, routes, and data flow intact.
5. Avoid broad rewrites.
6. Do not change component responsibilities unless strictly necessary for layout.
7. Do not add new dependencies.
8. Do not import the design-reference screenshots.
9. Do not touch `.env.local`.
10. Do not change REST API contracts.

---

## Required Final Verification

After the visual-only upgrade, run the standard quality checks from inside `/uis/talent-pipeline-tracker/`:

- `npm run lint`
- `npm run build`

If either command fails, fix only issues introduced by the visual upgrade.

---

## Final Cursor Report Required

Return a final report with these sections:

1. Visual upgrade summary.
2. Files modified.
3. Confirmation that no API logic was changed.
4. Confirmation that no routes were changed.
5. Confirmation that no endpoint contracts were changed.
6. Confirmation that status/stage filters still use URL query parameters.
7. Confirmation that search still works without full page reload.
8. Confirmation that candidate create/edit behavior was preserved.
9. Confirmation that note add/delete behavior was preserved.
10. Confirmation that all loading, success, error, and empty states still exist.
11. Confirmation that the app visually aligns with the HealthCore public website.
12. Confirmation that all six design-reference screenshots remain in `/docs/design-reference/`.
13. `npm run lint` result.
14. `npm run build` result.
15. Remaining risks, if any.

---

## Absolute Stop Conditions

Stop and report instead of changing code if:

- The app does not exist at `/uis/talent-pipeline-tracker/`.
- The current implementation is missing major Milestone 3 functionality.
- A requested visual change would require changing API logic.
- A requested visual change would require changing route behavior.
- The HealthCore visual direction conflicts with the local milestone context or rubric.
- The six design-reference screenshots are missing.

This task is complete only when the application looks visually coherent with HealthCore and still passes the Milestone 3 rubric without functional regressions.
