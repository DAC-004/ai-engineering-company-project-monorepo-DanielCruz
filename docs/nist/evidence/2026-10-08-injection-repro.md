# Injection demonstration, recorded invocation

Date executed: 2026-10-08, after the review of evidence ZIP (8).

`docs/nist/evidence/2026-10-08-nist-pytest.txt` contains a summary line only (`6 passed in 1.87s`) and is UTF-16. It does not contain the pytest invocation. `memory-bank/progress.md` attributes that historical count to `tests/pipelines/test_nist_protections.py` at a time when that file had fewer tests. The current file is larger. That 6-pass count is not the result of the command below.

## Verified command

Working directory: `services/api`

Interpreter: `services/api/.venv` (Python 3.13.12). No API key, database URL, or other secret was set for this run. The two tests replace retrieval and generation with a refusal stub, or call `keep_chunks()` and `safe_output()` directly.

```
.\.venv\Scripts\python.exe -m pytest ..\..\tests\pipelines\test_nist_protections.py::test_policy_override_is_blocked_before_the_model ..\..\tests\pipelines\test_nist_protections.py::test_retrieved_medication_instruction_is_dropped -v --tb=short --override-ini testpaths=
```

Selected tests:

- `test_policy_override_is_blocked_before_the_model`
- `test_retrieved_medication_instruction_is_dropped`

Expected observable result: both pass. The override test returns the fixed refusal, does not call retrieval or generation, and writes a decision line whose reason is `policy_override` without the question. The medication test keeps the clean protocol chunk and replaces the embedded instruction before return.

Observed result: exit 0. `2 passed in 2.08s`. Log: `docs/nist/evidence/2026-10-08-injection-repro-pytest.txt`.

A first attempt used `tests\pipelines\test_nist_protections.py` while the working directory was `services/api`. Pytest reported `file or directory not found` and collected 0 items. That path is not the demonstration. The command above is the one that passed.

## Historical counts whose arguments are not in the logs

These files were preserved. Their counts are not combined with the 2-pass result above.

| Log | What the file contains | What is not in the file |
| --- | --- | --- |
| `docs/nist/evidence/2026-10-08-gap-closure-pytest.txt` | `69 passed in 16.50s` | The pytest arguments and the node ids. |
| `docs/nist/evidence/2026-10-08-c05-path-pytest.txt` | `77 passed in 17.13s` | The pytest arguments and the node ids. |
| `docs/nist/evidence/2026-10-08-approval-note-pytest.txt` | `8 passed in 3.04s` | The node ids. |

The 8-pass file was written by this session from `services/api` with:

```
.\.venv\Scripts\python.exe -m pytest ..\..\tests\pipelines\test_rfp_approval.py -q --tb=line --override-ini testpaths=
```

That command selects the whole `tests/pipelines/test_rfp_approval.py` module. The observed summary was `8 passed in 3.04s`, which matches the saved log. It was not rerun for this review.

The 69-pass and 77-pass arguments were not recovered from those logs, from `memory-bank/progress.md`, or from `docs/nist/phi-surface-map.md`. The surface map names individual tests that exist in the tree. That list is not a reconstruction of either historical command.
