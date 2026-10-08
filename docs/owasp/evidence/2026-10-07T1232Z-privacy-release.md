# Privacy release, 2026-10-07T12:32Z

Host `healthcore-audit` `150.136.171.59`. This file records the install and the three live questions. It does not record Daniel's approval, a commit, or a critical finding.

## Installed files

Exported from the staged Git blobs and checked as LF before copy.

| File | Staged blob | Installed SHA-256 |
| --- | --- | --- |
| `services/api/app/agent/memory_policy.py` | `888797ca88a7ed7094a50cc336b6418555cc7805` | `fdfd3a3282ab4bedb8e6fe2b82df935bf6c22a9036a48a9d03633f028a8d35c0` |
| `services/api/app/agent/guardrails/text_rules.py` | `167969c5d01e703d54aebd2062cb7272b81b0678` | `6aef345eea6d1784225ae81adc67347bc5b021c068e549a896d7d2b48f966d87` |
| `services/api/app/services/streaming_release_gate.py` | `735ce23f657a6c2d4ef70c789d24648c58280332` | `88387f4ad52725c9168a088d3362611090c7b61cfe66064c3cc70178227f667a` |

`data/pipelines/rag.py` was not replaced. Its host SHA-256 stayed `a15d03168f4585ea68a35b1ac0851b6d3795b81d65c6980a9b2e95f6b5c17414`. The staged blob remains `aec89847f06bf878210560d4da27a21d6e04c868`.

Backups of the previous three files are in `/var/backups/healthcore-rag-20261007T020559Z/` as `memory_policy.py.before` (`00f224061448ef70f258066934f0e02842588f6d74bcc1133e9072a36bf7b74c`), `text_rules.py.before` (`ba1559866507f998d865b9062f74d9fb2a2ea97e05847260c2a3774a65eda4b5`), and `streaming_release_gate.py.before` (`c3d7d7b017372f6510edbd809ca673f63b59dc515004d98d3693e129097f5339`). Rollback is to install those three backups as `root:healthcore` mode `640` and restart only `healthcore-api`.

Installed mode is `root:healthcore` `640`. API PID `74492`, user `healthcore`, uid `997`, start `Wed Oct 7 12:32:20 2026`, `ActiveEnterTimestamp` `Wed 2026-10-07 12:32:20 UTC`. `GET /health` returned `{"status":"ok"}` after four refused connections during startup. Previous API PID `73277` stopped. Web PID stayed `45466`.

Controls recorded before and after this restart were the same: `permitrootlogin no`; guard `7b2f767805fbd979fe7827fdabfd04f9b97209137efdbc7d2d8607ebb3b852e5`; renewal hook `897a8ce6a9db4217f4593d68816b0d8ac54f41fe6336de72ba8bd41bf0c1e20a`; iptables v4 `a68125969ab048887572a285afa246aba1db443109ffb716c974cd6e82792e3a`; v6 `91f2b4508d7e2bc907dcecc099275f274d94cd93f6a5c28d264359fbb1034815`; nginx site `cbf1f5e3f0a0eacd93042921c67303988626bd45c5e8cd1432fda87514d350da`; renewal config `87973a9d06e500a8e017d4b81aba64eb6ba81611394047bf12faaf3d1820a198`; fullchain `1ff1114b16178cbc523e9db74bc7215958feaad2d492cc33020ea5b6b552d605`; 17 `InstanceServices` lines; one OUTPUT jump. This restart did not change those hashes. The renewal-config hash is the value observed at 12:32Z, not a claim that it equals the 11:28Z record.

## Local tests before install

`uv run pytest tests/services/test_streaming_release_gate.py tests/pipelines/test_gated_generation_stream.py tests/pipelines/test_rag.py -q --tb=line` from the repository root exited 0: `134 passed in 2.03s`.

From `services/api`: `uv run pytest ../../tests/pipelines/test_phi_surfaces.py ../../tests/pipelines/test_agent_memory.py ../../tests/pipelines/test_agent_guardrails.py -q --tb=line` exited 0: `52 passed in 4.98s`.

The cancellation check blocks active and passive wording, singular and plural references, and US and UK spellings, including a relation longer than eight words. The private-pay policy sentence is not that match. These tests are not the live host result.

## Live answers on PID 74492

`POST http://127.0.0.1:8000/knowledge/query` has no bearer. Retrieval and the model were not patched. Unauthenticated WebSocket `/ws/chat/rag-live-check` returned `HTTP/1.1 101` and close `1008`.

Cancellation, `2026-10-07T12:32:55Z` to `12:33:50Z`, HTTP 200, 364 characters:

The appointment policy requires a cancellation to be made more than 24 hours in advance without any charge. If a cancellation is made less than 24 hours in advance or if it's a no-show, a charge of 50 USD (or 40 GBP in the UK) applies for private-pay patients. For Medicare or Medicaid patients, there is no no-show fee, but the incident is logged in their record.

That text includes the private-pay qualification and the Medicare or Medicaid sentence from `docs/company-knowledge-base/healthcore-appointment-policy.en.md` lines 9-13. It does not end at "applies for".

Reminder, `12:33:50Z` to `12:34:04Z`, HTTP 200, 79 characters: "The last reminder sent before an appointment is 2 hours before the appointment."

Routine, `12:34:04Z` to `12:34:16Z`, HTTP 200, 66 characters: "The average availability for a routine appointment is 3 to 5 days."

The journal since `2026-10-07 12:32:20 UTC` is 1157 characters. It records the stop of PID `73277`, the start of PID `74492`, `GET /health` 200, the WebSocket accept, and three `POST /knowledge/query` 200 lines. Counts were 0 for `Traceback`, `Replacing an invented cancellation notice`, `Refusing an invented cancellation deadline`, `Retrying grounded generation`, and the listed clinical terms. These answers are model text. They do not prove the written-hour fallback.
