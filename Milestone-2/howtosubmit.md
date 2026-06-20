# Milestone 2 — How to Submit

HealthCore · AI Engineering · 4Geeks Academy

Use this guide to implement, test, and submit Milestone 2 (Backend / Logic in TypeScript). All work must match your assigned company context in [`CONTEXT.md`](../CONTEXT.md) at the repository root.

---

## What You Need to Do

Implement **Backend / Logic** in **TypeScript**. All entity names, fields, and rules must match exactly what is specified in `CONTEXT.md`.

### Backend / Logic checklist

- [ ] Define **TypeScript interfaces** for all main entities specified in `CONTEXT.md`.
- [ ] Implement **filtering functions** to search for elements by one or more criteria (e.g. category, price range, status).
- [ ] Implement **sorting functions** to sort arrays by different criteria (ascending, descending, multiple fields).
- [ ] Implement **linear search** to find elements in unsorted arrays.
- [ ] Implement **binary search** to find elements in previously sorted arrays.
- [ ] Create **aggregation functions** to generate reports: count elements by category; calculate totals, averages, maximums, and minimums.
- [ ] Implement **business validations** to ensure objects comply with the rules in `CONTEXT.md` before processing.
- [ ] All functions must have **explicit types** for parameters and return values.
- [ ] Follow the **single responsibility principle** — each function performs only one task.
- [ ] Include a clear **command to validate or execute** the TypeScript code during development.

> **IMPORTANT:** Field names, entity types, and validation rules in your implementation must match exactly what is specified in your **CONTEXT.md**. A generic implementation that ignores the context will not be accepted.

---

## Frontend / Testing (Optional)

Optional manual testing interface for your TypeScript functions.

- [ ] Create a simple HTML page with **Tailwind CSS** to manually test functions.
- [ ] Include buttons or controls for operations like **filter, search, sort, and generate reports**.
- [ ] Clearly display operation results in the interface.

If you add an `index.html` for testing, it must be servable locally or in Codespaces:

```bash
npx http-server . -p 3000 -a 0.0.0.0
```

---

## Code Quality

- [ ] **Naming conventions:** Use descriptive names; `camelCase` for variables and functions, `PascalCase` for interfaces.
- [ ] **Pure functions:** Each function must be pure — rely only on parameters and do not modify global variables.
- [ ] **Comments:** Write comments only for complex logic, not for obvious code.
- [ ] **Edge cases:** Correctly handle empty arrays, missing elements, and null values.
- [ ] **Variable declaration:** Use `const` by default and `let` only when values change.
- [ ] **Formatting:** Maintain consistent indentation and formatting.

---

## What We Will Evaluate

### Technical correctness

- [ ] **TypeScript interfaces** correctly model entities specified in `CONTEXT.md`, including all fields and types.
- [ ] **Filtering functions** correctly return elements based on specified criteria.
- [ ] **Sorting** works correctly in ascending and descending order.
- [ ] **Linear search** finds elements in unsorted arrays without errors.
- [ ] **Binary search** works correctly on sorted arrays, returning the correct index or `-1` if the element is not found.
- [ ] **Aggregations** correctly calculate totals, averages, counts, and extreme values.
- [ ] **Validations** reject data that does not comply with business rules defined in `CONTEXT.md`.
- [ ] **Compilation:** No TypeScript compilation errors in any file.
- [ ] **Documentation:** A documented command to run TypeScript validation or execution locally, for example:
  - `npx tsc --noEmit`
  - `npm run typecheck`

### Structure and organization

- [ ] Code is organized in separate files by responsibility (types, utils, validations).
- [ ] Each function has a single clearly identifiable responsibility.
- [ ] Variable, function, and interface names are descriptive and follow TypeScript conventions.

### Context adaptation

- [ ] All entity names, fields, and types match exactly those specified in `CONTEXT.md`.
- [ ] Implemented validations correspond to the business rules defined in `CONTEXT.md`.
- [ ] Generated reports respond to the specific needs described in `CONTEXT.md`.

### Code quality (evaluation)

- [ ] Functions are pure: they do not depend on external variables or modify global state.
- [ ] Edge cases are handled correctly: empty arrays, elements not found, null values.
- [ ] Code follows TypeScript best practices: explicit types, appropriate use of `const`/`let`, avoids `any`.

---

## Suggested folder layout

Place Milestone 2 code under this folder or a dedicated subfolder (for example `Milestone-2/src/`):

```
Milestone-2/
├── howtosubmit.md          ← this file
├── src/
│   ├── types/              ← interfaces from CONTEXT.md
│   ├── utils/              ← filter, sort, search, aggregate
│   └── validations/        ← business rule checks
├── tsconfig.json
└── package.json            ← scripts: typecheck, build, test
```

---

## Commands to document in your README

At minimum, document how to type-check and run your code:

```bash
npm install
npm run typecheck    # e.g. npx tsc --noEmit
```

If you add an optional test UI:

```bash
npx http-server . -p 3000 -a 0.0.0.0
```

---

## Before you submit

1. Read [`CONTEXT.md`](../CONTEXT.md) and confirm every entity, field, and validation rule matches your code.
2. Run `npx tsc --noEmit` (or your documented command) with zero errors.
3. Walk through the evaluation checklists above and mark each item complete.
4. Open a pull request with a short summary of what you implemented and how to run it.
