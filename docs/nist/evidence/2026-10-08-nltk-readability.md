# NLTK readability failures

Date: 2026-10-08. These three tests failed in one pytest process and again when run alone:

- `tests/pipelines/test_rfp_evaluator.py::test_revenue_section_passes_readability_relevance_and_compliance`
- `tests/pipelines/test_rfp_evaluator.py::test_evaluators_enter_together`
- `tests/pipelines/test_rfp_grounding.py::test_short_text_records_why_no_grade_was_calculated`

`readability_metrics()` caught `LookupError` and recorded `LookupError; no grade was calculated`. The short-text test expected the scorer's own "fewer than 100 words" message. The local NLTK data did not satisfy the scorer, so the grade path was not reached.

`project_specs.md` evaluation criteria and `CONTEXT-healthcore.md` do not include a readability grade. The failures do not block the injection demonstration, the prohibited-data checks, or the NIST report. They are not counted in the 69-pass or 77-pass logs, and they are not counted as passing.
