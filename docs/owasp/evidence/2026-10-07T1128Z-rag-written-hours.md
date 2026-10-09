# Written-hour cancellation deploy

Host `healthcore-audit`, public address `150.136.171.59`. Only `data/pipelines/rag.py` was installed. The bytes came from Git blob `aec89847f06bf878210560d4da27a21d6e04c868`, which was the staged index object for `data/pipelines/rag.py`. The CRLF working copy was not copied. The export had 59071 bytes and 0 CR. Its SHA-256 is `a15d03168f4585ea68a35b1ac0851b6d3795b81d65c6980a9b2e95f6b5c17414`.

Rollback was defined as restoring `/var/backups/healthcore-rag-20261007T020559Z/rag.py.a628fa8b` at `root:healthcore` mode `640`, restarting only `healthcore-api`, and requesting `GET /health`. Rollback was not used.

## Install

`2026-10-07T11:28:00Z`. The host file before the copy was SHA-256 `a628fa8bd78e168f97e47bad79c01bf6fc87e1cb54f3dfe98c6756358e7c68c7`, with 0 CR. That file was saved as `rag.py.a628fa8b` in the existing backup directory. The candidate saved as `rag.py.aec89847` had SHA-256 `a15d03168f4585ea68a35b1ac0851b6d3795b81d65c6980a9b2e95f6b5c17414`, 0 CR, and different bytes from the backup. It contains `def _canonical_hour`, the `(?:-|\s+)` hour token, and the negation lookahead. `py_compile` with the API virtualenv succeeded.

Installed path `/opt/healthcore/app/data/pipelines/rag.py`, owner `root`, group `healthcore`, mode `640`. Installed SHA-256 `a15d03168f4585ea68a35b1ac0851b6d3795b81d65c6980a9b2e95f6b5c17414`, equal to the export. The same hash was read again after the restart.

`systemctl restart healthcore-api` ran. The first four loopback health connections were refused while the process was starting. The next check returned `{"status":"ok"}`. `API_ACTIVE` was `active`.

- API PID `73277`
- Service user `healthcore`, uid `997`
- Process start `Wed Oct 7 11:28:00 2026`
- Unit `ActiveEnterTimestamp` `Wed 2026-10-07 11:28:01 UTC`
- Health body `{"status":"ok"}`
- Command: `/opt/healthcore/app/services/api/.venv/bin/python /opt/healthcore/app/services/api/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000`

The previous API PID `62587` stopped during this restart. Web PID stayed `45466`.

## Controls, before and after the restart

These values were identical in the before snapshot at `2026-10-07T11:28:00Z` and the after snapshot at `2026-10-07T11:28:05Z`.

| Check | Value |
| --- | --- |
| `healthcore-web` PID | `45466` |
| `healthcore-web` | active |
| `nginx` | active |
| `ssh` | active |
| `certbot-renew.timer` | active |
| `permitrootlogin` | `no` |
| Guard `untrusted_content.py` | `7b2f767805fbd979fe7827fdabfd04f9b97209137efdbc7d2d8607ebb3b852e5` |
| Renewal hook | `897a8ce6a9db4217f4593d68816b0d8ac54f41fe6336de72ba8bd41bf0c1e20a` |
| `/etc/iptables/rules.v4` | `a68125969ab048887572a285afa246aba1db443109ffb716c974cd6e82792e3a` |
| `/etc/iptables/rules.v6` | `91f2b4508d7e2bc907dcecc099275f274d94cd93f6a5c28d264359fbb1034815` |
| `/etc/nginx/sites-available/healthcore.conf` | `cbf1f5e3f0a0eacd93042921c67303988626bd45c5e8cd1432fda87514d350da` |
| `/etc/letsencrypt/renewal/150.136.171.59.conf` | `0871f37b878dfa6037c57031dccddcd84541c94a76a43ebb4eb924fc72819e50` |
| `fullchain.pem` | `1ff1114b16178cbc523e9db74bc7215958feaad2d492cc33020ea5b6b552d605` |
| Certificate | issuer `C=US, O=Let's Encrypt, CN=YE1`; notBefore `Oct 6 01:51:44 2026 GMT`; notAfter `Oct 12 17:51:43 2026 GMT` |
| `InstanceServices` lines | 17 |
| OUTPUT jump to `169.254.0.0/16` | 1 |

SSH, firewall, nginx, the renewal hook, and the certificate file were not edited. Only `healthcore-api` was restarted.

## Live answers on PID 73277

`POST http://127.0.0.1:8000/knowledge/query` has no bearer. Retrieval and the model were not patched. The appointment policy text used for comparison is `docs/company-knowledge-base/healthcore-appointment-policy.en.md`: cancelling more than 24 hours in advance has no charge; cancelling less than 24 hours in advance or a no-show is 50 USD or 40 GBP for private-pay patients; reminders are sent at 48h, 24h, and 2h; a routine appointment has average availability of 3 to 5 days.

| Question | Started | Ended | Result |
| --- | --- | --- | --- |
| What notice does the appointment policy require before a cancellation? | `2026-10-07T11:28:56Z` | `2026-10-07T11:29:48Z` | HTTP 200, 239 characters. "The appointment policy requires a cancellation to be made more than 24 hours in advance without any charge. If a cancellation is made less than 24 hours in advance or if it's a no-show, a charge of 50 USD (or 40 GBP in the UK) applies for " |
| When is the last reminder sent before an appointment? | `2026-10-07T11:29:48Z` | `2026-10-07T11:30:02Z` | HTTP 200, 79 characters. "The last reminder sent before an appointment is 2 hours before the appointment." |
| What is the average availability for a routine appointment? | `2026-10-07T11:30:02Z` | `2026-10-07T11:30:14Z` | HTTP 200, 66 characters. "The average availability for a routine appointment is 3 to 5 days." |

The cancellation answer states the 24-hour no-charge rule and the less-than-24-hour or no-show fee of 50 USD or 40 GBP. It does not state a 2-hour cancellation notice. It ends at "applies for" and does not include the policy words "private-pay patients". It is not the joined retrieved cancellation lines, and it is not the insufficient-information refusal.

The reminder answer names the last reminder interval as 2 hours. The policy lists 48h, 24h, and 2h, so 2h is the last of those three. The routine answer states 3 to 5 days, which is the policy sentence for routine availability.

An unauthenticated WebSocket to `/ws/chat/rag-live-check` returned `HTTP/1.1 101 Switching Protocols` and close code `1008`. No chat generation was sent. PHI term counts in the three answers were 0.

The journal since `2026-10-07 11:28:01 UTC` is 1090 characters. It records the stop of PID `62587`, the start of PID `73277`, one `GET /health` 200, the WebSocket accept, and three `POST /knowledge/query` 200 lines. It contains no `Traceback`, no `Replacing an invented cancellation notice`, no `Refusing an invented cancellation deadline`, and no `Retrying grounded generation`. Category-term counts in that slice were 0.

These responses are model text. They do not show that the written-hour replacement or refusal ran.

## Previously recorded unit tests

This deploy did not rerun the tests. The last workstation result, recorded before this install, was:

`uv run pytest tests/pipelines/test_rag.py -q --tb=short`

Exit code 0. Observed: `69 passed in 1.39s`.

Those mocked `generate_answer` tests are the evidence for the written-hour fallback. They are not host requests, and they are not the live answers above.
