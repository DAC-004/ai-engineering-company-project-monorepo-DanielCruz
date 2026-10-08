# HealthCore NIST checklist index

This file is the tracked index. The authoritative item records are in `.project_specs/HEALTHCORE_SECURE_AI_CHECKLIST.md`, which is local-only and is copied into the review ZIP. A checked parent item there is the completion record. This index repeats that result so the two files do not disagree.

Audit date: 2026-10-08 pre-commit approval. Branch: `feature/nist-security-practices`. HEAD: `38a0806bcc2fc3106aa4e4f969fd893e87953d02`. Checked parent items: 55 of 61. Daniel approved the pre-commit audit and ZIP (10) on 2026-10-08. That approval authorizes staging. Commit, push, pull request, and submission are not done. A05 stays unchecked as a historical timing deviation. H02 through H06 stay unchecked.

| ID | Obligation | Board | Status |
| --- | --- | --- | --- |
| A01 | Use the existing company monorepo fork | checked | Verified |
| A02 | Update the fork and use the required branch | checked | Verified |
| A03 | Read HealthCore context before code changes | checked | Verified |
| A04 | Inspect credential management | checked | Verified |
| A05 | Map external model inputs before code changes | open | Historical timing missed. Present-day list rechecked and expanded on 2026-10-08. |
| B01 | Complete AI inventory with an owner per component | checked | Verified |
| B02 | Identify third-party control responsibility | checked | Verified |
| B03 | Include all five starting-inventory components | checked | Verified as inventory inclusion |
| B04 | Cover the full system-wide audit scope | checked | Verified as an inventory |
| C01 | Treat HIPAA and UK GDPR separately | checked | Verified |
| C02 | Document notification and patient-rights differences | checked | Verified |
| C03 | Verify applicable signed BAAs | checked | Evidenced non-applicability for the 2026-10-06 inspected host |
| C04 | Verify applicable DPAs | checked | Evidenced non-applicability for the 2026-10-06 inspected host |
| C05 | Verify the complete prohibited-data constraint | checked | Verified on the enforced write and response paths, including RFP text, allowed checkpoints, and generated answers. Finite detectors and unread historical rows remain a bound, not an open item. |
| C06 | Keep documentation output in physician review | checked | Confirmed absent. Not a passed control. |
| C07 | Verify actual-policy citation | checked | Verified |
| C08 | Verify metadata-only access auditing | checked | Chart-access log confirmed absent. Decision log is separate. |
| D01 | Eliminate hardcoded credentials | checked | Verified for current source |
| D02 | Validate and sanitize user input | checked | Verified |
| D03 | Separate system instructions and user content | checked | Verified |
| D04 | Mitigate indirect prompt injection | checked | Verified for the tested instruction |
| D05 | Validate generated executable output | checked | Verified as applicability |
| D06 | Rate-limit at least one model endpoint | checked | Verified |
| D07 | Trace agent actions and reasons | checked | Verified |
| D08 | Confirm irreversible actions require humans | checked | Verified |
| D09 | Gate clinical-note signing and sending | checked | Confirmed absent. Not a passed control. |
| D10 | Gate patient notifications | checked | Confirmed absent. Not a passed control. |
| D11 | Gate inter-clinic history sharing | checked | Confirmed absent. Not a passed control. |
| D12 | Gate and audit referral/appointment changes | checked | Confirmed absent. Sample counts are not a status change. |
| D13 | Implement and demonstrate urgent fixes | checked | Verified for the two implemented fixes |
| E01 | Demonstrate at least one HealthCore injection case | checked | Verified |
| E02 | Keep all audit evidence free of prohibited data | checked | Verified for test evidence |
| E03 | Make protections reproducibly demonstrable | checked | Verified |
| F01 | Govern | checked | Verified as report content |
| F02 | Identify | checked | Verified as report content |
| F03 | Protect | checked | Verified as report content |
| F04 | Detect | checked | Verified as report content |
| F05 | Respond | checked | Verified as report content |
| F06 | Recover | checked | Verified as report content |
| F07 | Prioritized roadmap and gap disposition | checked | Verified. Residual items are documented roadmap records. |
| F08 | Verify all HealthCore-specific report deliverables | checked | Verified as report content |
| G01 | Complete OWASP report: 10 categories × three lanes | checked | Verified from the existing audit |
| G02 | Document SSH access | checked | Verified from prior evidence |
| G03 | Document non-root deployment | checked | Verified from prior evidence |
| G04 | Document firewall rules | checked | Verified from prior evidence |
| G05 | Verify HTTPS-only clinical surfaces | checked | Verified from prior evidence |
| G06 | Block public infrastructure access | checked | Verified from prior evidence |
| G07 | Prioritize role and clinic boundaries | checked | Verified. The clinic 3 result was reclassified. |
| G08 | Prioritize keys, TLS, and safe traces | checked | Verified as an audit |
| G09 | Prioritize debug exposure and physician gates | checked | Verified as an audit |
| G10 | Deliver hardening proof and critical-fix evidence | checked | Verified when the ZIP is rebuilt |
| H01 | Place the NIST Markdown report in the delivery folder | checked | Verified |
| H02 | Daniel commits and pushes | open | Pending Daniel |
| H03 | Create the pull request in Daniel's fork | open | Pending push |
| H04 | Include injection evidence and gap status in the PR | open | Pending the PR |
| H05 | Request Daniel's tech-lead review | open | Pending PR |
| H06 | Record Daniel's approval and submission | open | Pending |
| U01 | Audit the completed implementation against every item | checked | Verified as this re-audit |
| U02 | Deliver the adherence and deliverables report | checked | Verified |
| U03 | Create and inspect the evidence ZIP | checked | Verified when the ZIP is rebuilt |
| U04 | Support final review and close findings | checked | ZIP (9) review recorded. Not final approval. |
