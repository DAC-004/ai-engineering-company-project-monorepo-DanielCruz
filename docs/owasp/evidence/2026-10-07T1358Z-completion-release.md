# Completion-release correction

`StreamingReleaseGate.complete()` released a benign "for the patients" hold through the end of the buffer. That hold also contained an unfinished name or instruction prefix. `output_failure` accepts those unfinished prefixes, so the flush published them.

This is one completion defect. It is not a new PHI rule, and passing these tests does not establish general PHI protection.

## Before

Command, run before the implementation change:

`uv run pytest tests/services/test_streaming_release_gate.py::test_completion_does_not_flush_a_protected_prefix_inside_a_benign_for_phrase -q --tb=line`

Exit code 1. One failure. The released hold contained `patient A`:

`for the patients. Please review patient A`

The same completion path releases `ignore all your` inside `Bring the form for the patients. Note: ignore all your`.

## Corrected behavior

`complete()` still releases a benign cancellation hold when the finished text is not a cancellation match. If that hold also ends in an unfinished detector prefix, only the text before that prefix is released. The prefix is dropped. `interrupt()` still drops the whole hold and returns an empty string. A later `push()` emits nothing.

The only production caller is `data/pipelines/rag.py` `_local_llm_complete`. The returned answer is `gate.committed`, which already includes the completion release. That release is also appended once to the observation releases, `on_release`, and, when `forward_kept` is true, the kept-release callback. It is not appended to `committed` a second time. `published_before_iterator_close` stays false when the only release happens after `StopIteration`.

## After, local

`uv run pytest tests/services/test_streaming_release_gate.py::test_completion_does_not_flush_a_protected_prefix_inside_a_benign_for_phrase tests/pipelines/test_gated_generation_stream.py::test_completion_release_matches_the_answer_without_a_protected_prefix -q --tb=short`

Exit code 0. `2 passed in 1.33s`.

`uv run pytest tests/services/test_streaming_release_gate.py tests/pipelines/test_gated_generation_stream.py tests/pipelines/test_rag.py -q --tb=line`

Exit code 0. `136 passed in 1.95s`.

From `services/api`:

`uv run pytest ../../tests/pipelines/test_phi_surfaces.py ../../tests/pipelines/test_agent_memory.py ../../tests/pipelines/test_agent_guardrails.py -q --tb=line`

Exit code 0. `52 passed in 4.99s`.

The streaming tests cover character input, the whole string, fixed-width splits, and cuts inside both protected prefixes. The private-pay policy sentence is still committed in full. The existing singular, plural, active, and passive cancellation cases stay blocked. The earlier `134 passed` result did not include this completion case.

## Host install

Procedure: `docs/owasp/evidence/2026-10-07-completion-deploy.sh`. Backup directory `/var/backups/healthcore-rag-20261007T020559Z`. The previous privacy backups were not replaced. This install saved `streaming_release_gate.py.88387f4a` and `rag.py.a15d0316`.

| File | Before SHA-256 | Installed SHA-256 |
| --- | --- | --- |
| `streaming_release_gate.py` | `88387f4ad52725c9168a088d3362611090c7b61cfe66064c3cc70178227f667a` | `7567c2d67c3e8abb5f46abda061ab2fa616bff5ff78844379a6e71efaf9d3587` |
| `rag.py` | `a15d03168f4585ea68a35b1ac0851b6d3795b81d65c6980a9b2e95f6b5c17414` | `0a6e2649fb472c633a62870fb3b6cd16ee0940e0f56b460cf7ba1f2ebda8bae3` |

Both candidate files had zero CR bytes. Installed mode is `root:healthcore` `640`. `memory_policy.py` stayed `fdfd3a3282ab4bedb8e6fe2b82df935bf6c22a9036a48a9d03633f028a8d35c0`. `text_rules.py` stayed `6aef345eea6d1784225ae81adc67347bc5b021c068e549a896d7d2b48f966d87`. `untrusted_content.py` stayed `7b2f767805fbd979fe7827fdabfd04f9b97209137efdbc7d2d8607ebb3b852e5`.

Restart was `healthcore-api` only. Four loopback connection failures occurred while the process was starting. The next health body was `{"status":"ok"}`. API user `healthcore`. API PID `75937`. Active enter `2026-10-07T13:58:18Z`. The installed-module check printed `GATE_CHECK_OK`.

Web PID stayed `45466`. `nginx`, `ssh`, and `certbot-renew.timer` stayed active. `permitrootlogin` stayed `no`. Renewal hook, iptables v4, iptables v6, nginx site, renewal config, and `fullchain.pem` hashes were unchanged. InstanceServices count stayed 17. The OUTPUT jump count stayed 1. Certificate issuer remained Let's Encrypt `CN=YE1`, notBefore Oct 6 01:51:44 2026 GMT, notAfter Oct 12 17:51:43 2026 GMT.

## Live answers on PID 75937

`python3 /tmp/hc-rag-live-queries.py` exited 0. Unauthenticated websocket close was 1008.

| Question | Started | Status | Characters | Result |
| --- | --- | --- | --- | --- |
| Cancellation notice | `2026-10-07T13:59:54Z` | 200 | 364 | 24-hour no-charge rule, 50 USD or 40 GBP for private-pay patients, and the Medicare or Medicaid no-show sentence |
| Last reminder | `2026-10-07T14:00:50Z` | 200 | 79 | 2 hours before the appointment |
| Routine availability | `2026-10-07T14:01:04Z` | 200 | 66 | 3 to 5 days |

The listed clinical-term scan printed `none` for each answer. The journal since `2026-10-07T13:58:18Z` is 1222 bytes and 20 lines. Counts were zero for traceback, invented-notice replacement, invented-deadline refusal, grounding retry, and the refusal warning. It also has no `generate_answer backend` line, so the journal does not name the backend. These answers are not the insufficient-information refusal. They do not prove the written-hour fallback.

## Limit

The gate still uses the existing prefix families. An unfinished string that is not one of those prefixes is not newly blocked. Finite fixtures do not cover later model text.
