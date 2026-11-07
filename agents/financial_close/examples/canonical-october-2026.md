# Canonical October 2026

Period: **2026-10**. Load date: **2026-11-06**. Status: **Incomplete**.

Fictional aggregate test data. Generation evidence: Actual local Qwen2.5-3B planner and guarded writer; both model hypotheses verified. Review state: awaiting Tom Callahan. Internal outbox only; no external distribution.

## 1. Executive summary

Close for 2026-10 is incomplete.

## 2. Consolidated result in USD

| Measure | Verified actual / known subtotal | Budget |
| --- | --- | --- |
| Revenue | 2,027,420.00 | 2,095,450.00 |
| Expenses | 1,708,135.81 | 1,705,142.00 |
| Result | Incomplete; no complete actual result | 390,308.00 |

Actual status: incomplete. Budget status: complete. Missing or excluded values are not zero.

## 3. Revenue by country and payer

| Line | Currency | Verified actual / known subtotal | Budget | Amount variance | Deviation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| United States / revenue / commercial insurance | USD | 1,120,000 | 1,150,000 | -30,000 | -2.6% | complete |
| United States / revenue / Medicare / Medicaid | USD | 468,000 | 520,000 | -52,000 | -10.0% | complete |
| United Kingdom / revenue / private | GBP | 271,000 | 260,000 | 11,000 | 4.2% | complete |
| United Kingdom / revenue / NHS contract | GBP | 75,000 | 75,000 | 0 | 0.0% | complete |

## 4. Expenses by country

| Line | Currency | Verified actual / known subtotal | Budget | Amount variance | Deviation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| United States / clinical consumables | USD | 46,816 | 44,800 | 2,016 | 4.5% | complete |
| United States / laboratory | USD | 48,150 | 45,000 | 3,150 | 7.0% | complete |
| United States / medical interpreting | USD | 17,550 | 17,550 | 0 | 0.0% | complete |
| United States / payroll | USD | 1,060,000 | 1,050,000 | 10,000 | 1.0% | complete |
| United States / clinic rent | USD | 179,000 | 180,000 | Unavailable | Unavailable | known subtotal |
| United Kingdom / clinical consumables | GBP | 9,450 | 9,450 | 0 | 0.0% | complete |
| United Kingdom / laboratory | GBP | 10,353 | 10,150 | 203 | 2.0% | complete |
| United Kingdom / payroll | GBP | 209,000 | 210,000 | -1,000 | -0.5% | complete |
| United Kingdom / clinic rent | GBP | 52,000 | 52,000 | 0 | 0.0% | complete |
| United Kingdom / clinical software licences | GBP | Missing | 8,000 | Unavailable | Unavailable | missing |

## 5. Relevant deviations

### United States / revenue / Medicare / Medicaid

Claims 4000 unchanged; denials 14.0 to 22.6. Revenue below budget. Hypothesis (not proved causality): Medicare: increased denials to collections or revenue shortfall.

Verified actual 468,000 USD; budget 520,000; amount variance -52,000; deviation -10.0%.

### United States / laboratory

Observed 19.26 vs budget-implied 18; qty 2500; variance 1.26; increase 3150. Hypothesis (not proved causality): Laboratory: higher supplier or unit price to expense increase. Unchanged quantity is a brief expectation, not observed budget quantity data.

Verified actual 48,150 USD; budget 45,000; amount variance 3,150; deviation 7.0%.

## 6. Missing or uncertain data

- United Kingdom / clinical software licences: missing actual.
- LED-202610-PHI1: uncertain quarantined.

## 7. Traceability annex

Reference FX: 1 GBP = 1.27 USD. Source: briefing:reference_exchange_rate:1 GBP = 1.27 USD.

| Source file | SHA-256 / status |
| --- | --- |
| budget.csv | df2fe7f5845384ba659ca62007b864186848a040ac1eb359d88e7ca0227cfdc3 |
| ledger.csv | 7f78ffd040dd3f862f1c01764a07f9a4d311cf8770dc741ab6e7cf9bf42c1361 |
| operations.csv | 039e6686defd607ed36f188328e941ecc48d05d053eb51456bd2171887682883 |

Derived figures may reference other figure IDs listed below. Their source records and calculation basis remain explicit.

| Figure ID | Value | Status | Calculation | Producing records / source figures |
| --- | --- | --- | --- | --- |
| consolidated.expense_budget_usd | 1705142.00 | complete | sum of the ten expense line budgets in native currency converted to USD at briefing FX | fx.rate; uk_consumables.budget; uk_laboratory.budget; uk_payroll.budget; uk_rent.budget; uk_software.budget; us_consumables.budget; us_interpreting.budget; us_laboratory.budget; us_payroll.budget; us_rent.budget |
| consolidated.known_expense_actual_usd | 1708135.81 | incomplete | sum of verified expense ledger actuals in native currency converted to USD at briefing FX; incomplete known subtotal | fx.rate; uk_consumables.verified_actual; uk_laboratory.verified_actual; uk_payroll.verified_actual; uk_rent.verified_actual; uk_software.verified_actual; us_consumables.verified_actual; us_interpreting.verified_actual; us_laboratory.verified_actual; us_payroll.verified_actual; us_rent.verified_actual |
| consolidated.known_revenue_actual_usd | 2027420.00 | incomplete | sum of verified revenue ledger actuals in native currency converted to USD at briefing FX; incomplete known subtotal | fx.rate; uk_nhs_revenue.verified_actual; uk_private_revenue.verified_actual; us_commercial_revenue.verified_actual; us_medicare_medicaid_revenue.verified_actual |
| consolidated.result_budget_usd | 390308.00 | complete | revenue_budget_usd - expense_budget_usd; GBP native amounts converted to USD at briefing FX | consolidated.expense_budget_usd; consolidated.revenue_budget_usd; fx.rate |
| consolidated.revenue_budget_usd | 2095450.00 | complete | sum of the four revenue line budgets in native currency converted to USD at briefing FX | fx.rate; uk_nhs_revenue.budget; uk_private_revenue.budget; us_commercial_revenue.budget; us_medicare_medicaid_revenue.budget |
| fx.rate | 1.27 | complete | briefing reference rate | briefing:reference_exchange_rate:1 GBP = 1.27 USD |
| operations.commercial.claims_submitted_actual | 6400 | complete | operations claims_submitted_actual for commercial insurance | operations.csv:6#039e6686defd |
| operations.commercial.claims_submitted_budget | 6500 | complete | operations claims_submitted_budget for commercial insurance | operations.csv:5#039e6686defd |
| operations.commercial.denial_rate_pct_actual | 12.0 | complete | operations denial_rate_pct_actual for commercial insurance | operations.csv:8#039e6686defd |
| operations.commercial.denial_rate_pct_budget | 12.0 | complete | operations denial_rate_pct_budget for commercial insurance | operations.csv:7#039e6686defd |
| operations.medicare.claims_submitted_actual | 4000 | complete | operations claims_submitted_actual for Medicare / Medicaid | operations.csv:2#039e6686defd |
| operations.medicare.claims_submitted_budget | 4000 | complete | operations claims_submitted_budget for Medicare / Medicaid | operations.csv:1#039e6686defd |
| operations.medicare.denial_rate_pct_actual | 22.6 | complete | operations denial_rate_pct_actual for Medicare / Medicaid | operations.csv:4#039e6686defd |
| operations.medicare.denial_rate_pct_budget | 14.0 | complete | operations denial_rate_pct_budget for Medicare / Medicaid | operations.csv:3#039e6686defd |
| uk_consumables.amount_variance | 0 | complete | verified_actual - budget | uk_consumables.budget; uk_consumables.verified_actual |
| uk_consumables.budget | 9450 | complete | sum(budget amounts for uk_consumables) | budget.csv:10#df2fe7f58453 |
| uk_consumables.known_subtotal | 9450 | complete | sum(verified amounts for uk_consumables); not a complete total | LED-202610-035; LED-202610-036; ledger.csv:36; ledger.csv:37 |
| uk_consumables.percent | 0 | complete | (verified_actual - budget) / budget | uk_consumables.budget; uk_consumables.verified_actual |
| uk_consumables.verified_actual | 9450 | complete | sum(verified expense amounts for uk_consumables) | LED-202610-035; LED-202610-036; ledger.csv:36; ledger.csv:37 |
| uk_laboratory.amount_variance | 203 | complete | verified_actual - budget | uk_laboratory.budget; uk_laboratory.verified_actual |
| uk_laboratory.budget | 10150 | complete | sum(budget amounts for uk_laboratory) | budget.csv:11#df2fe7f58453 |
| uk_laboratory.known_subtotal | 10353 | complete | sum(verified amounts for uk_laboratory); not a complete total | LED-202610-037; LED-202610-038; ledger.csv:38; ledger.csv:39 |
| uk_laboratory.percent | 0.02 | complete | (verified_actual - budget) / budget | uk_laboratory.budget; uk_laboratory.verified_actual |
| uk_laboratory.verified_actual | 10353 | complete | sum(verified expense amounts for uk_laboratory) | LED-202610-037; LED-202610-038; ledger.csv:38; ledger.csv:39 |
| uk_nhs_revenue.amount_variance | 0 | complete | verified_actual - budget | uk_nhs_revenue.budget; uk_nhs_revenue.verified_actual |
| uk_nhs_revenue.budget | 75000 | complete | sum(budget amounts for uk_nhs_revenue) | budget.csv:4#df2fe7f58453 |
| uk_nhs_revenue.known_subtotal | 75000 | complete | sum(verified amounts for uk_nhs_revenue); not a complete total | LED-202610-022; LED-202610-023; LED-202610-024; ledger.csv:22; ledger.csv:23; ledger.csv:24 |
| uk_nhs_revenue.percent | 0 | complete | (verified_actual - budget) / budget | uk_nhs_revenue.budget; uk_nhs_revenue.verified_actual |
| uk_nhs_revenue.verified_actual | 75000 | complete | sum(verified revenue amounts for uk_nhs_revenue) | LED-202610-022; LED-202610-023; LED-202610-024; ledger.csv:22; ledger.csv:23; ledger.csv:24 |
| uk_payroll.amount_variance | -1000 | complete | verified_actual - budget | uk_payroll.budget; uk_payroll.verified_actual |
| uk_payroll.budget | 210000 | complete | sum(budget amounts for uk_payroll) | budget.csv:12#df2fe7f58453 |
| uk_payroll.known_subtotal | 209000 | complete | sum(verified amounts for uk_payroll); not a complete total | LED-202610-039; LED-202610-040; ledger.csv:40; ledger.csv:41 |
| uk_payroll.percent | -0.004761904761904761904761904762 | complete | (verified_actual - budget) / budget | uk_payroll.budget; uk_payroll.verified_actual |
| uk_payroll.verified_actual | 209000 | complete | sum(verified expense amounts for uk_payroll) | LED-202610-039; LED-202610-040; ledger.csv:40; ledger.csv:41 |
| uk_private_revenue.amount_variance | 11000 | complete | verified_actual - budget | uk_private_revenue.budget; uk_private_revenue.verified_actual |
| uk_private_revenue.budget | 260000 | complete | sum(budget amounts for uk_private_revenue) | budget.csv:3#df2fe7f58453 |
| uk_private_revenue.known_subtotal | 271000 | complete | sum(verified amounts for uk_private_revenue); not a complete total | LED-202610-019; LED-202610-020; LED-202610-021; ledger.csv:19; ledger.csv:20; ledger.csv:21 |
| uk_private_revenue.percent | 0.04230769230769230769230769231 | complete | (verified_actual - budget) / budget | uk_private_revenue.budget; uk_private_revenue.verified_actual |
| uk_private_revenue.verified_actual | 271000 | complete | sum(verified revenue amounts for uk_private_revenue) | LED-202610-019; LED-202610-020; LED-202610-021; ledger.csv:19; ledger.csv:20; ledger.csv:21 |
| uk_rent.amount_variance | 0 | complete | verified_actual - budget | uk_rent.budget; uk_rent.verified_actual |
| uk_rent.budget | 52000 | complete | sum(budget amounts for uk_rent) | budget.csv:13#df2fe7f58453 |
| uk_rent.known_subtotal | 52000 | complete | sum(verified amounts for uk_rent); not a complete total | LED-202610-041; LED-202610-042; ledger.csv:42; ledger.csv:43 |
| uk_rent.percent | 0 | complete | (verified_actual - budget) / budget | uk_rent.budget; uk_rent.verified_actual |
| uk_rent.verified_actual | 52000 | complete | sum(verified expense amounts for uk_rent) | LED-202610-041; LED-202610-042; ledger.csv:42; ledger.csv:43 |
| uk_software.amount_variance | Missing | missing | verified_actual - budget | uk_software.budget; uk_software.verified_actual |
| uk_software.budget | 8000 | complete | sum(budget amounts for uk_software) | budget.csv:14#df2fe7f58453 |
| uk_software.known_subtotal | Missing | missing | sum(verified amounts for uk_software); not a complete total | No source value |
| uk_software.percent | Missing | missing | (verified_actual - budget) / budget | uk_software.budget; uk_software.verified_actual |
| uk_software.verified_actual | Missing | missing | sum(verified expense amounts for uk_software) | No source value |
| us_commercial_revenue.amount_variance | -30000 | complete | verified_actual - budget | us_commercial_revenue.budget; us_commercial_revenue.verified_actual |
| us_commercial_revenue.budget | 1150000 | complete | sum(budget amounts for us_commercial_revenue) | budget.csv:1#df2fe7f58453 |
| us_commercial_revenue.known_subtotal | 1120000 | complete | sum(verified amounts for us_commercial_revenue); not a complete total | LED-202610-001; LED-202610-002; LED-202610-003; LED-202610-004; LED-202610-005; LED-202610-006; LED-202610-007; LED-202610-008; LED-202610-009; ledger.csv:1; ledger.csv:2; ledger.csv:3; ledger.csv:4; ledger.csv:5; ledger.csv:6; ledger.csv:7; ledger.csv:8; ledger.csv:9 |
| us_commercial_revenue.percent | -0.02608695652173913043478260870 | complete | (verified_actual - budget) / budget | us_commercial_revenue.budget; us_commercial_revenue.verified_actual |
| us_commercial_revenue.verified_actual | 1120000 | complete | sum(verified revenue amounts for us_commercial_revenue) | LED-202610-001; LED-202610-002; LED-202610-003; LED-202610-004; LED-202610-005; LED-202610-006; LED-202610-007; LED-202610-008; LED-202610-009; ledger.csv:1; ledger.csv:2; ledger.csv:3; ledger.csv:4; ledger.csv:5; ledger.csv:6; ledger.csv:7; ledger.csv:8; ledger.csv:9 |
| us_consumables.amount_variance | 2016 | complete | verified_actual - budget | us_consumables.budget; us_consumables.verified_actual |
| us_consumables.budget | 44800 | complete | sum(budget amounts for us_consumables) | budget.csv:5#df2fe7f58453 |
| us_consumables.known_subtotal | 46816 | complete | sum(verified amounts for us_consumables); not a complete total | LED-202610-025; LED-202610-026; ledger.csv:25; ledger.csv:26 |
| us_consumables.percent | 0.045 | complete | (verified_actual - budget) / budget | us_consumables.budget; us_consumables.verified_actual |
| us_consumables.verified_actual | 46816 | complete | sum(verified expense amounts for us_consumables) | LED-202610-025; LED-202610-026; ledger.csv:25; ledger.csv:26 |
| us_interpreting.amount_variance | 0 | complete | verified_actual - budget | us_interpreting.budget; us_interpreting.verified_actual |
| us_interpreting.budget | 17550 | complete | sum(budget amounts for us_interpreting) | budget.csv:7#df2fe7f58453 |
| us_interpreting.known_subtotal | 17550 | complete | sum(verified amounts for us_interpreting); not a complete total | LED-202610-029; LED-202610-030; ledger.csv:29; ledger.csv:30 |
| us_interpreting.percent | 0 | complete | (verified_actual - budget) / budget | us_interpreting.budget; us_interpreting.verified_actual |
| us_interpreting.verified_actual | 17550 | complete | sum(verified expense amounts for us_interpreting) | LED-202610-029; LED-202610-030; ledger.csv:29; ledger.csv:30 |
| us_laboratory.amount_variance | 3150 | complete | verified_actual - budget | us_laboratory.budget; us_laboratory.verified_actual |
| us_laboratory.budget | 45000 | complete | sum(budget amounts for us_laboratory) | budget.csv:6#df2fe7f58453 |
| us_laboratory.budget_implied_unit_price | 18 | complete | laboratory budget divided by observed quantity | us_laboratory.budget; us_laboratory.verified_actual |
| us_laboratory.increase | 3150 | complete | verified laboratory actual minus budget | us_laboratory.budget; us_laboratory.verified_actual |
| us_laboratory.known_subtotal | 48150 | complete | sum(verified amounts for us_laboratory); not a complete total | LED-202610-027; LED-202610-028; ledger.csv:27; ledger.csv:28 |
| us_laboratory.observed_quantity | 2500 | complete | sum of laboratory test quantities | ledger.csv:27; ledger.csv:28 |
| us_laboratory.percent | 0.07 | complete | (verified_actual - budget) / budget | us_laboratory.budget; us_laboratory.verified_actual |
| us_laboratory.unit_price | 19.26 | complete | observed ClearPath Labs unit price | ledger.csv:27; ledger.csv:28 |
| us_laboratory.unit_price_variance | 1.26 | complete | observed unit price minus budget-implied unit price | us_laboratory.budget; us_laboratory.verified_actual |
| us_laboratory.verified_actual | 48150 | complete | sum(verified expense amounts for us_laboratory) | LED-202610-027; LED-202610-028; ledger.csv:27; ledger.csv:28 |
| us_medicare_medicaid_revenue.amount_variance | -52000 | complete | verified_actual - budget | us_medicare_medicaid_revenue.budget; us_medicare_medicaid_revenue.verified_actual |
| us_medicare_medicaid_revenue.budget | 520000 | complete | sum(budget amounts for us_medicare_medicaid_revenue) | budget.csv:2#df2fe7f58453 |
| us_medicare_medicaid_revenue.known_subtotal | 468000 | complete | sum(verified amounts for us_medicare_medicaid_revenue); not a complete total | LED-202610-010; LED-202610-011; LED-202610-012; LED-202610-013; LED-202610-014; LED-202610-015; LED-202610-016; LED-202610-017; LED-202610-018; ledger.csv:10; ledger.csv:11; ledger.csv:12; ledger.csv:13; ledger.csv:14; ledger.csv:15; ledger.csv:16; ledger.csv:17; ledger.csv:18 |
| us_medicare_medicaid_revenue.percent | -0.1 | complete | (verified_actual - budget) / budget | us_medicare_medicaid_revenue.budget; us_medicare_medicaid_revenue.verified_actual |
| us_medicare_medicaid_revenue.verified_actual | 468000 | complete | sum(verified revenue amounts for us_medicare_medicaid_revenue) | LED-202610-010; LED-202610-011; LED-202610-012; LED-202610-013; LED-202610-014; LED-202610-015; LED-202610-016; LED-202610-017; LED-202610-018; ledger.csv:10; ledger.csv:11; ledger.csv:12; ledger.csv:13; ledger.csv:14; ledger.csv:15; ledger.csv:16; ledger.csv:17; ledger.csv:18 |
| us_payroll.amount_variance | 10000 | complete | verified_actual - budget | us_payroll.budget; us_payroll.verified_actual |
| us_payroll.budget | 1050000 | complete | sum(budget amounts for us_payroll) | budget.csv:8#df2fe7f58453 |
| us_payroll.known_subtotal | 1060000 | complete | sum(verified amounts for us_payroll); not a complete total | LED-202610-031; LED-202610-032; ledger.csv:31; ledger.csv:32 |
| us_payroll.percent | 0.009523809523809523809523809524 | complete | (verified_actual - budget) / budget | us_payroll.budget; us_payroll.verified_actual |
| us_payroll.verified_actual | 1060000 | complete | sum(verified expense amounts for us_payroll) | LED-202610-031; LED-202610-032; ledger.csv:31; ledger.csv:32 |
| us_rent.amount_variance | Missing | missing | verified_actual - budget | us_rent.budget; us_rent.verified_actual |
| us_rent.budget | 180000 | complete | sum(budget amounts for us_rent) | budget.csv:9#df2fe7f58453 |
| us_rent.known_subtotal | 179000 | known_subtotal | sum(verified amounts for us_rent); not a complete total | LED-202610-033; LED-202610-034; ledger.csv:33; ledger.csv:34 |
| us_rent.percent | Missing | missing | (verified_actual - budget) / budget | us_rent.budget; us_rent.verified_actual |
| us_rent.verified_actual | 179000 | known_subtotal | sum(verified expense amounts for us_rent) | LED-202610-033; LED-202610-034; ledger.csv:33; ledger.csv:34 |
