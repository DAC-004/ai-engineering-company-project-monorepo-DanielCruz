# Cursor Prompt — Visual-Only Professional Upgrade  
## Milestone 3 — Talent Pipeline Tracker

---

## Task Title

**Visual-Only UI Upgrade for Milestone 3 — Talent Pipeline Tracker**

---

## Role

You are a **Senior Full Stack Developer** with expert-level experience in:

- Next.js App Router
- React
- TypeScript
- Tailwind CSS
- REST API integration
- Internal SaaS dashboard interfaces
- Responsive enterprise UI design
- Accessibility-focused frontend development

You are working inside an existing course monorepo project. The application has already been built or partially built. Your task is **not** to rebuild the app from scratch. Your task is to perform a **professional visual-only refactor** that improves layout, spacing, typography, readability, and UI polish while preserving every functional requirement of the milestone.

---

## Project Context

This project is:

```txt
/uis/talent-pipeline-tracker/
```

It is part of **Milestone 3 — Talent Pipeline Tracker**.

The app is an internal People & Talent tool for a company running an active recruitment campaign. The People team is overwhelmed by manual candidate tracking in spreadsheets, separate interview notes, and email status updates. The frontend must provide a reliable operational interface for viewing candidates, filtering them, updating pipeline state, managing notes, and registering/editing candidates.

This is not a marketing site. It is not a playful demo. It should look and feel like a real internal business application that a People & Talent department could use on Monday morning.

---

## Mandatory First Step — Inspection Gate

Before writing or editing any code, inspect the existing project carefully.

You must inspect:

```txt
CONTEXT-company.md
app/
components/
types/
lib/
services/
hooks/
app/globals.css
docs/design-reference/
.env.example
package.json
```

Also inspect the actual current file structure before assuming filenames.

Do not begin implementation until you understand:

1. The company scenario and terminology from `CONTEXT-company.md`.
2. The current routes.
3. The current component structure.
4. The current API/data-access implementation.
5. The current TypeScript types.
6. The current filter/search behavior.
7. The current status/stage update behavior.
8. The current notes add/delete behavior.
9. The current create/edit candidate forms.
10. The current loading, error, empty, and success states.
11. The design-reference screenshots located in:

```txt
/uis/talent-pipeline-tracker/docs/design-reference/
```

The screenshots and milestone instructions are source-of-truth context. Use them to protect the evaluation requirements.

---

## Primary Objective

Perform a **visual-only upgrade** of the Talent Pipeline Tracker so it feels coherent with the previously improved HealthCore visual direction.

The UI should feel:

- Modern
- Spacious
- Professional
- Operational
- Trustworthy
- Healthcare-adjacent
- Enterprise-ready
- Easy to scan
- Appropriate for a real People & Talent workflow
- Polished enough for a business stakeholder review

The visual upgrade should improve:

- Global spacing
- Page width usage
- Typography scale
- Header/app shell design
- Candidate list readability
- Filter/search toolbar design
- Candidate detail layout
- Notes/activity-log presentation
- Forms
- Buttons
- Badges
- Loading states
- Error states
- Empty states
- Success feedback
- Responsive behavior

---

## Absolute Scope Boundary

This is a **visual-only refactor**.

You may update:

- Tailwind utility classes
- Layout wrappers
- Spacing
- Typography
- Border radius
- Borders
- Shadows
- Background colors
- Text colors
- Card layouts
- Table/list layouts
- Button styling
- Form styling
- Badge styling
- Loading/error/empty/success state presentation
- Responsive class names
- Component markup only when necessary to improve visual structure
- Small presentational component extraction if it reduces repetition and does not alter behavior

You must not change:

- API base URL behavior
- API endpoints
- API methods
- Request payload contracts
- Response parsing contracts
- Route paths
- Query parameter behavior
- Candidate filtering logic
- Candidate search logic
- Candidate detail fetching logic
- Status/stage update logic
- Notes list/add/delete logic
- New candidate creation logic
- Candidate edit logic
- Validation requirements
- Existing TypeScript data contracts
- Existing business terminology from `CONTEXT-company.md`
- Project architecture in a way that risks breaking evaluation
- Environment variable names
- Build tooling
- Package manager behavior

Do not introduce unrelated refactors.

---

## Technology Restrictions

Use only the existing approved stack:

```txt
Next.js App Router
React
TypeScript
Tailwind CSS
```

Do not add:

- shadcn/ui
- Material UI
- Chakra UI
- Bootstrap
- DaisyUI
- Redux
- Zustand
- Jotai
- MobX
- Unnecessary animation libraries
- New external UI kits
- New design-system dependencies

Component-level state with React hooks is sufficient for this milestone.

---

## Functional Requirements That Must Remain Intact

The visual upgrade must preserve all Milestone 3 requirements exactly.

---

### Candidate List Requirements

The candidate list page must still:

- Render candidate data fetched from the API.
- Display each candidate’s:
  - Full name
  - Position applied for
  - Current status
  - Current stage
- Filter by status using query parameters.
- Filter by stage using query parameters.
- Search by name without reloading the page.
- Search by email without reloading the page.
- Show a loading state while candidates are being fetched.
- Show an error state if candidate fetching fails.
- Navigate to the candidate detail page using Next.js routing.
- Avoid full page reloads for internal navigation.

The route must remain:

```txt
/
```

---

### Candidate Detail Requirements

The candidate detail page must still:

- Load the correct candidate by ID.
- Fetch candidate data from the correct API endpoint.
- Display all available candidate fields:
  - Name
  - Email
  - Phone
  - Position
  - LinkedIn
  - CV link
  - Years of experience
  - Status
  - Stage
  - Application date
- Include a control to update status using:

```txt
PATCH /records/:id
```

- Include a control to update stage using:

```txt
PATCH /records/:id
```

- Display notes fetched from:

```txt
GET /records/:id/notes
```

- Allow adding a new note using:

```txt
POST /records/:id/notes
```

- Allow deleting a note using:

```txt
DELETE /records/:id/notes/:note_id
```

The route must remain:

```txt
/candidates/[id]
```

---

### Candidate Management Requirements

The app must still:

- Include a form to register a new candidate using:

```txt
POST /records
```

- Include a form to edit an existing candidate using:

```txt
PUT /records/:id
```

- Validate required fields before submission.
- Show success feedback after successful form submission.
- Show error feedback after failed form submission.
- Keep all existing form fields required by the milestone.
- Preserve all existing create/edit routes.

---

### State and Async Handling Requirements

All API calls must still be handled with:

```txt
async/await
```

Every data-fetching operation must still communicate at least three states:

```txt
loading
success
error
```

After each of the following operations, the UI must update without requiring a full page reload:

```txt
PATCH
PUT
POST
DELETE
```

This applies to:

- Status update
- Stage update
- Note creation
- Note deletion
- Candidate creation
- Candidate edit

---

### Code Structure Requirements

Maintain or improve the clear folder structure.

Expected folders may include:

```txt
/components
/hooks
/types
/lib
/services
```

The application must continue to define and use TypeScript types for API data structures.

Do not collapse everything into route files.

Do not move files unnecessarily.

Do not remove existing useful abstraction layers.

---

## Company Context Requirement

The UI must reflect the assigned company scenario in `CONTEXT-company.md`.

Before changing labels, headings, empty states, helper text, or page descriptions, verify the company language in `CONTEXT-company.md`.

Use company-specific terminology where applicable.

Do not create a generic applicant tracking interface that ignores the company framing.

If the company context uses a specific business name, department name, team name, role terminology, or operational framing, preserve and reinforce that language visually.

---

## Visual Direction

The upgraded Talent Pipeline Tracker should visually align with the improved HealthCore build.

Use the following visual direction:

```txt
Professional healthcare-adjacent internal operations dashboard
```

The interface should use:

- Deep navy shells or page background areas
- White or soft off-white content surfaces
- Clinical teal accents
- Muted slate and blue-gray borders
- Subtle shadows
- Generous spacing
- Strong typography hierarchy
- Wide desktop layout
- Clean dashboard cards
- Polished form controls
- Professional status badges
- Clear operational feedback states

Avoid:

- Tiny text
- Narrow boxed-in containers
- Overly playful icons
- Harsh saturated colors
- Random gradients
- Cheap-looking cards
- Dense unspaced forms
- Unclear buttons
- Low-contrast text
- Decorative visuals that distract from candidate data
- Any change that weakens evaluation compliance

---

## Global Layout Requirements

### 1. Use More Screen Width

The current app should use more available desktop width.

Use a wider application container pattern similar to:

```css
width: min(94vw, 1600px);
margin-inline: auto;
```

Tailwind direction:

```txt
mx-auto w-[min(94vw,1600px)]
```

Avoid narrow containers like:

```txt
max-w-4xl
max-w-5xl
max-w-6xl
```

for primary application views unless the section is specifically a form or narrow reading panel.

Recommended layout shell:

```txt
min-h-screen bg-slate-950
```

Recommended main content wrapper:

```txt
mx-auto w-[min(94vw,1600px)] py-8 lg:py-10
```

The application should not look centered in a small column on desktop.

---

### 2. Create a Strong App Shell

The app should feel like a real internal tool.

Use a strong top-level shell with:

- A polished header
- Clear product title
- Short operational subtitle
- Primary action button for registering or adding a candidate
- Optional contextual campaign summary if already supported by existing data

Suggested header tone:

```txt
Talent Pipeline Tracker
People & Talent command center for active candidate review, pipeline updates, and internal notes.
```

Replace the wording only as needed to match `CONTEXT-company.md`.

Visual direction:

- Deep navy background
- White headline
- Muted slate/blue supporting text
- Teal accent line, badge, or small label
- Spacious padding
- Header aligned to the same wide container as the page content

Suggested Tailwind direction:

```txt
bg-slate-950 text-white border-b border-white/10
```

Header content wrapper:

```txt
mx-auto flex w-[min(94vw,1600px)] flex-col gap-5 py-6 md:flex-row md:items-center md:justify-between lg:py-8
```

---

### 3. Improve Page Rhythm

Apply consistent spacing across pages.

Recommended spacing system:

```txt
Page wrapper: py-8 lg:py-10
Major section spacing: space-y-6 lg:space-y-8
Card padding: p-5 md:p-6 lg:p-8
Toolbar padding: p-4 md:p-5
Grid gap: gap-5 md:gap-6 lg:gap-8
Form gap: gap-4 md:gap-5
Button height: h-11 or h-12
Input height: h-11 or h-12
```

Avoid:

```txt
p-2
gap-1
text-xs for main information
cramped tables
dense card stacks
```

---

## Typography Requirements

The current UI should be visually upgraded with a stronger type scale.

Use readable text sizes across the app.

Recommended type scale:

```txt
Main page title:
text-3xl md:text-4xl font-bold tracking-tight

Page subtitle:
text-base md:text-lg leading-7 text-slate-300 or text-slate-600 depending on background

Section title:
text-xl md:text-2xl font-semibold tracking-tight

Card title:
text-lg md:text-xl font-semibold

Body text:
text-base leading-7

Table/list primary text:
text-base font-semibold

Table/list secondary text:
text-sm md:text-base text-slate-500

Form labels:
text-sm font-semibold text-slate-700

Buttons:
text-sm md:text-base font-semibold

Badges:
text-xs md:text-sm font-semibold
```

Use `text-xs` only for compact metadata, small uppercase labels, or badge details.

Do not make important candidate data tiny.

---

## Color System Requirements

Use a restrained enterprise color system.

Recommended palette direction:

```txt
Page background:
slate-950, slate-100, slate-50

Primary text:
slate-950, slate-900

Secondary text:
slate-600, slate-500

Dark shell text:
white, slate-300

Primary accent:
teal-500, teal-600, cyan-500

Borders:
slate-200, slate-300, white/10

Cards:
white, slate-50

Success:
emerald

Warning:
amber

Error/destructive:
rose or red, used carefully

Neutral:
slate
```

Avoid large areas of bright saturated color.

Use accent color deliberately for:

- Primary button
- Focus rings
- Active filter states
- Status badges
- Small decorative separators
- Important indicators

---

## Header and Navigation Visual Requirements

Improve the application header/navigation so it feels polished and aligned.

The header should include:

- Product name
- Company/context-aware subtitle
- Primary action
- Clear navigation/back affordance when on detail or form pages

Header expectations:

- Wide aligned container
- Generous vertical padding
- Strong title hierarchy
- No cramped navigation
- Clear button states
- Good responsive behavior

Suggested top header structure:

```txt
<header>
  <div className="wide-container">
    <div>
      <p className="eyebrow">People & Talent Operations</p>
      <h1>Talent Pipeline Tracker</h1>
      <p>...</p>
    </div>

    <div>
      <Link>Add candidate</Link>
    </div>
  </div>
</header>
```

Use actual existing routes and labels from the app.

Do not invent a route that does not exist.

---

## Candidate List Page Visual Requirements

The candidate list page should feel like a dashboard for high-volume candidate review.

Recommended top-to-bottom structure:

1. Page summary or operational overview
2. Search/filter toolbar
3. Candidate list/table/card area
4. Loading/error/empty state area as needed

---

### Candidate List Container

The candidate list area should use a clean surface:

```txt
rounded-2xl border border-slate-200 bg-white shadow-sm
```

If using a table-like layout, use:

```txt
overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm
```

Rows should use:

```txt
border-b border-slate-100
hover:bg-slate-50
transition-colors
```

Desktop rows should be spacious enough to scan.

Recommended row padding:

```txt
px-5 py-4
```

or

```txt
px-6 py-5
```

---

### Candidate List Columns

On desktop, present candidate data in a clear table or table-like grid.

Must show:

- Candidate full name
- Position applied for
- Current status
- Current stage

If application date is already available in the list data, it may also be shown. Do not add new API requirements if not already available.

Suggested desktop columns:

```txt
Candidate
Position
Status
Stage
Applied
Action
```

If there is no application date in the list data, omit the Applied column.

The action should remain clear:

```txt
View details
```

or equivalent context-appropriate wording.

Do not remove the candidate detail navigation.

---

### Candidate Cards on Mobile

On mobile, candidate rows may become cards.

Each mobile card should show:

- Candidate name
- Email if already available in list data
- Position
- Status badge
- Stage badge
- View details action

Recommended mobile card styling:

```txt
rounded-xl border border-slate-200 bg-white p-4 shadow-sm
```

Cards should stack with:

```txt
space-y-3
```

No horizontal scrolling should occur on mobile.

---

## Filter and Search Toolbar Requirements

The filter/search toolbar is central to the milestone and must remain functional.

It should visually communicate that users can quickly narrow the pipeline.

Required controls:

- Search input for name/email
- Status filter
- Stage filter

Existing query-parameter behavior must remain unchanged.

The toolbar should:

- Be visually grouped
- Use larger controls
- Align horizontally on desktop
- Wrap or stack cleanly on tablet/mobile
- Use clear labels
- Have accessible focus states
- Avoid cramped spacing

Recommended toolbar surface:

```txt
rounded-2xl border border-slate-200 bg-white p-4 shadow-sm md:p-5
```

Recommended toolbar layout:

```txt
grid grid-cols-1 gap-4 lg:grid-cols-[minmax(280px,1fr)_220px_220px_auto]
```

or adapt to the existing implementation.

Recommended input/select styling:

```txt
h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-base text-slate-900 shadow-sm
focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2
```

Recommended label styling:

```txt
mb-1.5 block text-sm font-semibold text-slate-700
```

Do not remove `useSearchParams` behavior if already implemented.

Do not replace query-parameter filtering with local-only state.

---

## Status and Stage Badge Requirements

Status and stage should be visually scannable.

Create or improve badge styling without changing the actual values.

Badges should be:

- Consistent
- Subtle
- Professional
- Readable
- Rounded
- Not overly bright
- Not dependent on color alone

Recommended badge base:

```txt
inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset
```

Suggested color mapping direction:

```txt
New / Applied / Screening:
bg-sky-50 text-sky-700 ring-sky-200

Interview / Technical / In Review:
bg-indigo-50 text-indigo-700 ring-indigo-200

Offer / Hired / Accepted:
bg-emerald-50 text-emerald-700 ring-emerald-200

Rejected / Closed:
bg-rose-50 text-rose-700 ring-rose-200

Pending / Unknown / General:
bg-slate-100 text-slate-700 ring-slate-200
```

Use actual status/stage values from the API/types.

Do not mutate API values for visual display in a way that breaks updates.

---

## Candidate Detail Page Visual Requirements

The candidate detail page should feel like a profile workspace, not a plain data dump.

Recommended desktop layout:

```txt
grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_420px] lg:gap-8
```

Main column:

- Candidate profile header card
- Candidate information sections
- Edit candidate action if already present

Right/sidebar column:

- Status/stage update card
- Notes/activity log card
- Metadata/actions if already present

On mobile:

- Stack all sections in one column
- Keep actions close to the relevant content
- Preserve readability

---

### Candidate Profile Card

The candidate profile card should include:

- Candidate name as the main title
- Position applied for
- Status badge
- Stage badge
- Contact information
- Application date
- LinkedIn/CV links if available

Recommended card styling:

```txt
rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:p-8
```

Recommended information layout:

```txt
grid grid-cols-1 gap-4 md:grid-cols-2
```

Each detail item can use:

```txt
rounded-xl border border-slate-200 bg-slate-50 p-4
```

Label:

```txt
text-sm font-semibold text-slate-500
```

Value:

```txt
mt-1 text-base font-medium text-slate-950
```

Do not remove any field.

---

### Status and Stage Update Card

The status/stage update controls should be visually important but not overwhelming.

Recommended card:

```txt
rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6
```

The controls should:

- Have clear labels
- Use larger select controls
- Show current values
- Preserve PATCH behavior
- Display loading/submitting state if already implemented
- Display success/error feedback

Recommended select styling:

```txt
h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-base text-slate-900 shadow-sm
focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2
```

Do not make status/stage updates require unnecessary additional clicks if the existing interface supports single-interaction updates.

---

## Notes UI Requirements

The notes section should look like an internal activity log.

It must remain fully functional:

- Load notes
- Add note
- Delete note
- Show loading state
- Show error state
- Show empty state

Recommended notes card:

```txt
rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-6
```

Recommended note item:

```txt
rounded-xl border border-slate-200 bg-slate-50 p-4
```

The note item should show:

- Note text
- Date/time metadata if available
- Author metadata if available
- Delete control

Recommended note text:

```txt
text-base leading-7 text-slate-800
```

Recommended note metadata:

```txt
text-sm text-slate-500
```

Delete action should be visible but restrained:

```txt
text-sm font-semibold text-rose-700 hover:text-rose-800
```

If no notes exist, show a polished empty state:

```txt
No internal notes yet.
Add a note to capture interview context, follow-up items, or screening observations.
```

Adjust wording to match `CONTEXT-company.md` if needed.

Do not delete notes automatically.

Do not hide the delete control if it already exists.

---

## New Candidate and Edit Candidate Form Visual Requirements

Forms should feel professional, organized, and easy to complete.

Use larger controls and clear grouping.

Recommended form container:

```txt
rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:p-8
```

Recommended form layout:

```txt
grid grid-cols-1 gap-5 md:grid-cols-2
```

For full-width fields like notes, links, or longer text:

```txt
md:col-span-2
```

Recommended label:

```txt
mb-1.5 block text-sm font-semibold text-slate-700
```

Recommended input/select/textarea:

```txt
w-full rounded-xl border border-slate-300 bg-white px-3 text-base text-slate-900 shadow-sm
focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2
```

Inputs/selects should use:

```txt
h-11
```

Textareas should use:

```txt
min-h-28
```

Form actions should have clear hierarchy:

Primary:

```txt
h-11 rounded-xl bg-slate-950 px-5 text-sm font-semibold text-white shadow-sm hover:bg-slate-800
```

Secondary:

```txt
h-11 rounded-xl border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-700 hover:bg-slate-50
```

Do not remove validation.

Do not remove required fields.

Do not change form submission endpoints.

---

## Buttons and Links

All buttons and action links should be consistent.

Primary button visual direction:

```txt
inline-flex h-11 items-center justify-center rounded-xl bg-slate-950 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2
```

Secondary button visual direction:

```txt
inline-flex h-11 items-center justify-center rounded-xl border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2
```

Destructive button visual direction:

```txt
inline-flex h-10 items-center justify-center rounded-xl border border-rose-200 bg-rose-50 px-4 text-sm font-semibold text-rose-700 transition hover:bg-rose-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:ring-offset-2
```

Text links should be clearly visible:

```txt
font-semibold text-teal-700 hover:text-teal-800 hover:underline
```

Do not use plain unstyled browser-default links for important actions.

---

## Loading State Requirements

Improve loading states visually across the app.

Required areas:

- Candidate list
- Candidate detail
- Notes panel
- Forms during submission, if already implemented

Preferred loading design:

- Skeleton-like cards or rows
- Muted slate backgrounds
- Consistent spacing with the final layout
- Clear loading text when necessary

Candidate list loading example direction:

```txt
rounded-2xl border border-slate-200 bg-white p-5 shadow-sm
```

Inside:

```txt
space-y-3
```

Skeleton rows:

```txt
h-14 rounded-xl bg-slate-100
```

Do not rely only on console logs.

Do not remove existing loading checks.

---

## Error State Requirements

Improve error states so failures are clear to the user.

Error states should include:

- Clear title
- Short explanation
- Visible styling
- Retry action if already supported
- No silent failure

Recommended error container:

```txt
rounded-2xl border border-rose-200 bg-rose-50 p-5 text-rose-900
```

Recommended title:

```txt
text-base font-semibold
```

Recommended body:

```txt
mt-1 text-sm leading-6
```

Do not hide API errors.

Do not swallow exceptions silently.

Do not replace required visible errors with `console.error`.

---

## Empty State Requirements

Improve empty states for:

- No candidates returned
- No candidates matching filters/search
- No notes for a candidate

Empty states should be professional and helpful.

Recommended empty state card:

```txt
rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center shadow-sm
```

Candidate empty state example:

```txt
No candidates match the current filters.
Adjust the search, status, or stage filters to review more records.
```

Notes empty state example:

```txt
No internal notes yet.
Add a note to capture screening context or next steps.
```

Use company-appropriate wording from `CONTEXT-company.md`.

---

## Success Feedback Requirements

Success states should be clear and professional.

Use success feedback after:

- Status update
- Stage update
- Note added
- Note deleted
- Candidate created
- Candidate edited

If success feedback already exists, visually improve it.

Recommended success alert:

```txt
rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800
```

Do not create intrusive success behavior that interrupts workflow.

---

## Responsive Requirements

The upgraded UI must work cleanly at:

```txt
1920px desktop
1440px desktop
1366px laptop
1024px tablet
768px tablet
430px mobile
390px mobile
360px mobile
```

---

### Desktop Requirements

On desktop:

- The app should use a wide layout.
- The content should not appear boxed into a narrow center column.
- Candidate list/table should be easy to scan.
- Filters should align horizontally when space allows.
- Candidate detail should use a two-column layout when appropriate.
- Forms may use two-column grids.
- Header should feel spacious and premium.

---

### Tablet Requirements

On tablet:

- Filters may wrap.
- Detail page may stack if necessary.
- Tables should not cause awkward overflow.
- Candidate rows/cards should remain readable.
- Forms should remain usable.

---

### Mobile Requirements

On mobile:

- No horizontal scrolling.
- Header stacks cleanly.
- Candidate list becomes stacked cards if table layout is too wide.
- Filters stack vertically.
- Buttons remain tappable.
- Forms use one column.
- Text remains readable.
- Status/stage badges wrap cleanly.
- Notes remain readable.
- Detail sections stack in logical order.

Recommended mobile button behavior:

```txt
w-full sm:w-auto
```

---

## Accessibility Requirements

Preserve and improve accessibility.

Required:

- Form controls must have labels.
- Buttons must have visible text or accessible labels.
- Focus states must be visible.
- Keyboard navigation must remain possible.
- Text contrast must be readable.
- Color cannot be the only method of communicating status.
- Links must be distinguishable from body text.
- Interactive elements must have sufficient target size.
- Do not remove semantic HTML.
- Do not replace buttons with non-interactive divs.
- Do not remove `aria-*` attributes if they already exist.

Recommended focus ring:

```txt
focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2
```

---

## Detailed Page-by-Page Implementation Guidance

---

### `/` Candidate List Page

Upgrade the page into a polished candidate pipeline dashboard.

Recommended sections:

```txt
1. Header/app shell
2. Optional summary metrics area
3. Filter/search toolbar
4. Candidate list/table
5. Empty/loading/error states
```

If summary metrics already exist or can be derived safely from loaded candidates without new API calls, they may be styled as cards.

Potential summary cards:

- Total candidates
- Active review
- Interview stage
- Offers or final stage

Only create summary metrics if they are computed safely from already-fetched data and do not change API behavior.

Summary card styling:

```txt
rounded-2xl border border-white/10 bg-white/10 p-5 text-white shadow-sm backdrop-blur
```

or, in main content:

```txt
rounded-2xl border border-slate-200 bg-white p-5 shadow-sm
```

Do not add metrics that are inaccurate or require new backend assumptions.

---

### `/candidates/[id]` Candidate Detail Page

Upgrade this page into a profile workspace.

Recommended sections:

```txt
1. Back link to candidate list
2. Candidate profile header card
3. Candidate data grid
4. Status/stage update card
5. Notes/activity log card
6. Edit action if already available
```

Back link styling:

```txt
inline-flex items-center text-sm font-semibold text-slate-600 hover:text-slate-950
```

Candidate name should be highly visible:

```txt
text-3xl md:text-4xl font-bold tracking-tight text-slate-950
```

Status and stage should appear near the candidate name.

---

### New Candidate Page

Upgrade the form visually.

Recommended page structure:

```txt
1. Back link
2. Page title and subtitle
3. Form card
4. Form actions
5. Success/error feedback
```

Use company-aware language.

Do not change the POST behavior.

---

### Edit Candidate Page

Upgrade the form visually.

Recommended page structure:

```txt
1. Back link
2. Page title and subtitle
3. Form card prefilled with current data
4. Form actions
5. Success/error feedback
```

Do not change the PUT behavior.

---

## Tailwind Implementation Guidance

Prefer utility classes that are explicit and easy to audit.

Use a consistent set of classes across shared UI patterns.

Common surface class direction:

```txt
rounded-2xl border border-slate-200 bg-white shadow-sm
```

Common dark shell direction:

```txt
bg-slate-950 text-white
```

Common muted page background:

```txt
bg-slate-100
```

Common section spacing:

```txt
space-y-6 lg:space-y-8
```

Common card padding:

```txt
p-5 md:p-6 lg:p-8
```

Common control classes:

```txt
h-11 rounded-xl border border-slate-300 bg-white px-3 text-base text-slate-900 shadow-sm
```

Common focus:

```txt
focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2
```

---

## Regression Protection

While making visual changes, continuously protect the following:

- Do not break route navigation.
- Do not break filter query parameters.
- Do not break search behavior.
- Do not break status updates.
- Do not break stage updates.
- Do not break notes.
- Do not break new candidate creation.
- Do not break candidate editing.
- Do not break loading/error/success states.
- Do not change API URLs.
- Do not change API methods.
- Do not change payload field names.
- Do not change TypeScript interfaces in a way that conflicts with API data.
- Do not commit `.env.local`.
- Keep `.env.example` documenting required variables.

---

## Environment File Requirement

Confirm that `.env.local` is not committed.

The project should use:

```txt
NEXT_PUBLIC_API_URL=https://playground.4geeks.com/tracker/api/v1
```

A `.env.example` file should document the required environment variable.

Do not expose private tokens.

Do not hardcode secrets.

---

## Required Validation Commands

After visual implementation, run:

```bash
npm run lint
npm run build
```

Fix any lint or build issues caused by your changes.

Do not leave the project in a broken build state.

---

## Manual Functional Validation Checklist

After implementation, manually verify:

### Candidate List

- [ ] Candidate list loads from API.
- [ ] Full name is visible.
- [ ] Position is visible.
- [ ] Status is visible.
- [ ] Stage is visible.
- [ ] Status filter works.
- [ ] Stage filter works.
- [ ] Filters use query parameters.
- [ ] Search by name works without full reload.
- [ ] Search by email works without full reload.
- [ ] Loading state is visible.
- [ ] Error state is visible when applicable.
- [ ] Empty state is visible when filters return no results.
- [ ] Candidate detail navigation works.

### Candidate Detail

- [ ] Detail page loads correct candidate by ID.
- [ ] Name is visible.
- [ ] Email is visible.
- [ ] Phone is visible.
- [ ] Position is visible.
- [ ] LinkedIn is visible if available.
- [ ] CV link is visible if available.
- [ ] Years of experience is visible.
- [ ] Status is visible.
- [ ] Stage is visible.
- [ ] Application date is visible.
- [ ] Status update works with PATCH.
- [ ] Stage update works with PATCH.
- [ ] Success feedback appears after update.
- [ ] Error feedback appears after failed update.

### Notes

- [ ] Notes load from API.
- [ ] Notes are readable.
- [ ] Empty notes state appears when no notes exist.
- [ ] New note can be added.
- [ ] Note can be deleted.
- [ ] Loading state appears where appropriate.
- [ ] Error state appears where appropriate.

### Candidate Management

- [ ] New candidate form renders correctly.
- [ ] Required field validation still works.
- [ ] New candidate can be submitted with POST.
- [ ] Success feedback appears after creation.
- [ ] Error feedback appears after failure.
- [ ] Edit candidate form renders correctly.
- [ ] Existing candidate data is displayed in edit form.
- [ ] Existing candidate can be updated with PUT.
- [ ] Success feedback appears after edit.
- [ ] Error feedback appears after failure.

### Routing

- [ ] `/` works.
- [ ] `/candidates/[id]` works.
- [ ] Existing new candidate route works.
- [ ] Existing edit candidate route works.
- [ ] Internal navigation uses Next.js routing.
- [ ] No full page reloads occur for app navigation.

### Responsive

- [ ] 1920px desktop looks wide and professional.
- [ ] 1440px desktop looks balanced.
- [ ] 1366px laptop looks balanced.
- [ ] 1024px tablet works without awkward overflow.
- [ ] 768px tablet works cleanly.
- [ ] 430px mobile has no horizontal scroll.
- [ ] 390px mobile has no horizontal scroll.
- [ ] 360px mobile has no horizontal scroll.
- [ ] Filters stack cleanly on mobile.
- [ ] Forms are usable on mobile.
- [ ] Candidate cards/rows are readable on mobile.
- [ ] Notes are readable on mobile.

### Accessibility

- [ ] Focus states are visible.
- [ ] Inputs have labels.
- [ ] Buttons are keyboard accessible.
- [ ] Links are distinguishable.
- [ ] Text contrast is readable.
- [ ] Status/stage are not communicated by color alone.
- [ ] No semantic HTML was downgraded unnecessarily.

---

## Acceptance Criteria

This task is complete only when all of the following are true:

- The application visually feels coherent with the improved HealthCore visual system.
- The app looks like a real internal People & Talent operations tool.
- The desktop layout uses available screen width effectively.
- Typography is larger, clearer, and more professional.
- Candidate list is easier to scan.
- Filter/search controls look polished and remain fully functional.
- Status and stage badges are professional and readable.
- Candidate detail page is clearly organized.
- Notes section looks like an internal activity log.
- New/edit candidate forms are cleaner and easier to use.
- Loading states are visible and polished.
- Error states are visible and useful.
- Empty states are professional and helpful.
- Success feedback is visible after successful operations.
- Mobile layout has no horizontal scrolling.
- Tablet layout remains balanced.
- All Milestone 3 functionality still works.
- No API endpoints or contracts were changed.
- No route paths were changed.
- No external UI libraries were added.
- No external state-management libraries were added.
- `.env.local` was not committed.
- `npm run lint` passes.
- `npm run build` passes.

---

## Final IDE Agent Report Required

When finished, provide a concise but complete report with the following sections:

```md
## Visual Upgrade Report

### Files Changed

List every file changed.

### Visual Improvements Implemented

Explain the spacing, layout, typography, card, toolbar, table/list, form, button, badge, loading, error, empty, and responsive improvements.

### Functionality Preserved

Confirm that API behavior, route paths, query parameters, status/stage updates, notes, candidate creation, and candidate editing were not changed.

### Validation Results

Include results for:

- npm run lint
- npm run build

### Manual Testing Completed

Confirm testing for:

- Candidate list
- Filters
- Search
- Candidate detail
- Status update
- Stage update
- Notes list/add/delete
- New candidate form
- Edit candidate form
- Desktop responsiveness
- Tablet responsiveness
- Mobile responsiveness

### Issues Found and Fixed

List any issues found during the visual refactor and how they were fixed.

### Notes

Mention any important implementation details or constraints.
```

---

## PR Description Template

Use this structure for the Pull Request description:

```md
## What functionalities I implemented

- Completed a visual-only upgrade of the Talent Pipeline Tracker.
- Improved global layout width, spacing, and typography.
- Updated the app shell/header to feel more professional and aligned with the company context.
- Improved the candidate list for better scanability.
- Improved the filter/search toolbar while preserving query-parameter behavior.
- Improved candidate detail layout into a clearer profile/workspace view.
- Improved status and stage badge styling.
- Improved notes section presentation.
- Improved new/edit candidate form styling.
- Improved loading, error, empty, and success states.
- Verified responsive behavior across desktop, tablet, and mobile.

## What challenges I encountered and how I solved them

One challenge was improving the visual structure without changing the milestone functionality. I solved this by limiting the work to Tailwind classes, layout wrappers, and presentational markup while preserving existing API calls, route paths, query-parameter behavior, and TypeScript contracts.

Another challenge was making the desktop layout feel more professional without breaking mobile responsiveness. I solved this with a wider fluid container, responsive grid layouts, larger form controls, and stacked mobile layouts that avoid horizontal scrolling.

## Screenshots

Add screenshots if available:
- Candidate list desktop
- Candidate detail desktop
- Mobile candidate list
- Mobile detail/form view
```

---

## Final Instruction

Make the application visually better, more spacious, and more professional, but do not compromise the Milestone 3 evaluation requirements.

This is a strict visual-only refactor.

Do not ship unless the app still passes:

```bash
npm run lint
npm run build
```

and the manual validation checklist above.
