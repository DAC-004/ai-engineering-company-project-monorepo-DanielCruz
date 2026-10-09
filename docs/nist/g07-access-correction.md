# G07 access-control correction

Date: 2026-10-08. This note corrects the classification of one result. It does not rewrite the 2026-10-06 capture.

## What was demonstrated

`docs/owasp/evidence/2026-10-06-stage2-results.md` records an isolated run of the real inventory router. A second authenticated user received HTTP 200 for orders whose types were `consumption` and `delivery` and whose clinic id was 3. Anonymous inventory writes in the correction pass returned 401. The other user's RFP decision returned 403 `not_department_owner`.

## Applicable rule

`services/api/app/services/inventory_service.py` states that `clinic_id` is recorded on movements and does not partition catalog rows or the stock formula. `GET /inventory/orders` returns that list to any authenticated user. `UserInDB` has no clinic field, so there is no assignment that would make clinic 3 another user's clinic.

G07's source text is an audit of staff role boundaries on referral and compliance tools, and of cross-clinic record access through agents. The clinic 3 result is a supply-movement list. It is not a referral tool and not an agent read of a patient record. `docs/owasp/owasp-top10-audit.md` A01-AG records that no cross-clinic clinical record read was found on the agent path. No referral notifier exists in this runtime. The RFP department check is the role boundary that was exercised, and it rejected the wrong account.

## Classification

The HTTP 200 is the inventory contract, not a bypass of a clinic-binding rule. Treating it as an unresolved unauthorized-access gap was incorrect. No ownership filter was added. The 2026-10-06 matrix row remains the original observation, including its instruction not to add a filter only to close the row.

The inventory contract cited above is `services/api/app/services/inventory_service.py` and `GET /inventory/orders` in `services/api/app/routers/inventory.py`. Both files are in the review ZIP.

Separate observations in that same OWASP row are not this correction. Their disposition is `docs/nist/finding-disposition.md`: supplier mutations require a bearer, and incident-result reads stay available to any authenticated operator because that is the route contract. No clinic filter was added to inventory.
