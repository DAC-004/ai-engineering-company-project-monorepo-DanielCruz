# Candidate reconfirm

Read-only check during the 2026-10-07 checklist reconciliation. No service was restarted. The guest clock was not printed. This table is the pre-completion-fix observation. The `2026-10-07T13:58:18Z` install replaced `streaming_release_gate.py` and `rag.py`. The current host record is `docs/owasp/evidence/2026-10-07T1358Z-completion-release.md`.

| Check | Observed |
| --- | --- |
| `healthcore-api` PID | `74492` |
| `healthcore-api` active | `active` |
| `healthcore-web` PID | `45466` |
| `memory_policy.py` SHA-256 | `fdfd3a3282ab4bedb8e6fe2b82df935bf6c22a9036a48a9d03633f028a8d35c0` |
| `text_rules.py` SHA-256 | `6aef345eea6d1784225ae81adc67347bc5b021c068e549a896d7d2b48f966d87` |
| `streaming_release_gate.py` SHA-256 | `88387f4ad52725c9168a088d3362611090c7b61cfe66064c3cc70178227f667a` |
| `rag.py` SHA-256 | `a15d03168f4585ea68a35b1ac0851b6d3795b81d65c6980a9b2e95f6b5c17414` |
| `untrusted_content.py` SHA-256 | `7b2f767805fbd979fe7827fdabfd04f9b97209137efdbc7d2d8607ebb3b852e5` |
| `sshd -T` `permitrootlogin` | `no` |

These hashes match `docs/owasp/evidence/2026-10-07T1232Z-privacy-release.md`. The procedure is `docs/owasp/evidence/2026-10-07-candidate-hashes.sh`. Instance metadata was also read in this pass. One VNIC object was returned. Its keys were `macAddr`, `privateIp`, `subnetCidrBlock`, `virtualRouterIp`, `vlanTag`, and `vnicId`. It did not include `nsgIds` or a security-list name. That omission does not invalidate the 2026-10-05T22:49Z console observation in `docs/owasp/evidence/2026-10-05T2249Z-oci-console-observation.md`.
