# OCI console observation, 2026-10-05T22:49Z

This file was written on 2026-10-07. It preserves Daniel's supplied console observation. It is not a new OCI inspection, and it is not a screenshot.

Daniel supplied the console screenshots on 2026-10-05 at 6:49 PM UTC-4, which is 2026-10-05T22:49Z. They were inspected in that session. The image files are not in this repository. Local session copies remain outside the Git tree. No repository path is assigned to those images.

Observed on those pages:

- `public subnet-healthcore-vcn`, Security, Security Lists: exactly one attached list, `Default Security List for healthcore-vcn`. The table says page 1 of 1 and 1 of 1 total items. State Available. Created Oct 05, 2026, 17:49:42 UTC.
- `healthcore-audit`, Networking, Primary VNIC: Network security groups shows no attached group. Attached VNICs is one row, `healthcore-vcn` marked Primary VNIC, page 1 of 1 and 1 of 1 total items. Subnet `public subnet-healthcore-vcn`. Public address `150.136.171.59`. Private address `10.0.0.134`.

The same session's earlier rule page, supplied at 2026-10-05T22:13Z, showed that list with stateful TCP 22 from `0.0.0.0/0`, ICMP type 3 code 4 from `0.0.0.0/0`, ICMP type 3 from `10.0.0.0/16`, and all protocols out to `0.0.0.0/0`. TCP 80 and 443 were not on that page.

Later recorded change: on 2026-10-06, stateful TCP 80 and TCP 443 from `0.0.0.0/0` were added to that same list. `docs/owasp/evidence/2026-10-06T024540Z-public-http-reachability.txt` records the added rules and says existing rules stayed unchanged. Its sentence that membership and NSG questions were not reopened means that pass did not repeat the console check. It does not withdraw the 22:49Z observation. No later evidence records a second attached security list or a network security group. Guest firewall, certificate, and application deploys do not change those OCI attachments.

Instance metadata that omits `nsgIds` or a security-list name does not invalidate this console observation.
