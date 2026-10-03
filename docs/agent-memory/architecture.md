# HealthCore operational memory

The support agent keeps a curated store of operational notes. RAG stays a read-only tool against the `healthcore_knowledge` collection. Memory uses a separate SQLite file, `data/process/agent_memory/support_agent_memory.sqlite`, through `read_relevant` and `write_approved`. The LangGraph checkpointer is runtime state, not this store. Approved notes are not appended to an unbounded system prompt. A turn loads a bounded set for the authenticated user.

## Why this store

Memorable HealthCore facts are few and exact: a clinic protocol, a country-level administrative exception, a patient-free incident pattern, or a staff preference for how operational information is presented. Lookup is by owner, subject key, and terms in the current question.

Ruled out:

- Redis or a prompt cache. This agent path has no Redis, and these notes are not a session cache.
- A Qdrant collection, including any `*_knowledge` collection. Similarity search can attach a note to the wrong clinic, and mixing notes into curated documents breaks retrieval evals.
- A knowledge graph. These facts do not need relationship traversal.
- Fine-tuning. A weight update cannot be tied to one approval or forgotten on request.

## What can never be remembered

HIPAA and UK GDPR both apply. The same appearance check covers US and UK clinics. There is no country allow path. The check looks for a patient name, including a full name followed by "is a patient", a medical record number, date of birth, diagnosis, insurance or NHS number, clinical note, lab result, or visit content such as a named patient cancelling an appointment. A staff name in an operational preference, such as Diane Foster, is not by itself patient information.

The check rejects a proposal that appears to contain patient information before the user is asked to remember it. It is not a guarantee that every PHI phrase will be found.

The user decision for the required example is: accept `Patient Johnson cancelled tomorrow's appointment, note that down.` on the agent endpoint, and refuse it without copying that patient content into the response, logs, events, tables, memory, checkpoints, traces, or downstream tool calls. The refusal explains that patient information cannot be stored. Audit keeps a tombstone with a timestamp and no message body.

## Who can approve a write

`thread_id` locates a conversation. It does not authorize one. `POST /agent/query` already validates a bearer with `get_current_user` when a token is present. Memory uses that user's id. The token, email, and password hash are not stored. A proposal and its facts belong to that owner. Another caller who sends the same `thread_id` does not see the proposal and cannot approve it. The `approved` audit row's `actor_user_id` and the fact's `authorized_by_user_id` are the owner. An unanswered expiry has a null actor, so the audit shows that nobody authorized a write. A knowledge question with no bearer does not stage or read memory.

## Proposals and decisions

After a safe answer, an explicit criterion can add one `memory_proposal` to that same response. The fact is not written yet. The criterion allows a proposal only when the turn states a new or corrected clinic protocol, patient-free incident pattern, or staff presentation preference, nothing equivalent is already stored, and no proposal is still pending.

The next message is classified against that proposal as `approve`, `reject`, `edit`, or `unclear`. The classifier reads a structured label. It does not search the message for the word yes. Low confidence, invalid output, or a generation-model failure is `unclear`. That result discards the proposal.

- `approve` writes the pending text for that owner and records `approved`.
- `reject` writes no fact and records `rejected`.
- `edit` replaces the pending text, records `edited`, and writes a fact only after a later `approve`.
- `unclear` records `discarded_ambiguous` and does not write a fact.

A message can approve and ask another question. The proposal is resolved, then the existing graph answers the other question.

Each of those events has its own `occurred_at`, an `originating_ref` for the user turn, and the outcome. Safe text is stored. Patient content is not.

Staging, approval, rejection, edit, ambiguous discard, unanswered expiry, and a PHI tombstone each commit the change and its audit event in one transaction. If the audit insert fails, that change is rolled back. An approved fact cannot remain without its `approved` row, a pending proposal cannot remain without its `proposed` row, and a rejection, edit, discard, or expiry cannot change the proposal without its audit row.

## Forgetting

If the user never replies, nothing is written. The pending proposal stays until the next message on that owner's thread, or until 24 hours after its last update. Expiry records `expired_unanswered` with a null actor. Silence is not approval. An unclear reply discards the proposal immediately.

Those time and size limits are design choices. The graded requirement is a working cleanup and a defined result when nobody replies.

- 24 hours lets a staff member answer the next clinic morning and still drops an abandoned offer inside one operational day.
- Active facts expire after 180 days so a road-closure explanation does not stay for years. This is not a HIPAA or UK GDPR retention period.
- At most 30 active facts per store. Twelve clinics and three note kinds are a small set. The cap is a backstop. The normal cleanup is one active fact per owner and subject key. A newer approved fact for that key supersedes the older one.

Consolidation screens text again before leaving it active. A row that fails is replaced with `phi withheld` and deactivated.

## False corrections

Approval authorizes a write. It does not verify the claim. Every fact is stored with `claim_status=unverified`. Nothing in this flow sets a verified status.

Another user's later turn does not load the note, and the note is not written into `healthcore_knowledge`. That isolation is what the code can verify. The approving user's own later turn does load the note, labeled unverified, because the approved-memory cycle requires the note to show up again. If that turn also retrieves company knowledge, the retrieved answer stays in the reply and the note does not replace it. The label, the 180-day expiry, and the 30-fact cap only limit that owner's copy. They do not prove the claim is true. Two people who share one login are one actor.

## Why this is still one agent

Self-evaluation is one criterion and one optional `memory_proposal` field on the same support agent. Intent classification runs only while a proposal is pending. There is no second agent and no new graph.

## Examples

Memorable:

1. At the Manchester clinic, internal referrals now go through the coordinator before the specialist — that changed last quarter.
2. That high no-show alert at the Austin clinic was because of a road closure that week, not a real problem with the reminder programme.
3. The weekly report for Diane Foster needs vacancies broken down by role, not just by clinic — she asked for that two weeks ago.

The referral system failing on Monday mornings because of the overnight batch job is an incident pattern. "patient Smith had a failed referral" is not.

A country-level administrative correction does not need a city name. A UK correction is stored as `uk_administrative_exception` and a US correction as `us_administrative_exception`, so approving one does not supersede the other. A later correction for the same country supersedes that country's note. One sentence that compares both countries is a single proposal; approving it updates both country keys and leaves no third shared key. A question about the exception, and the same sentence with a patient name, are not proposals.

Not memorable:

1. What's this week's no-show rate?
2. Patient Johnson cancelled tomorrow's appointment, note that down. This is refused as patient information. It is not proposed and it is not stored.
3. Thanks, that settles my report.
