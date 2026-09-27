# Memory evidence cycles

Both cycles run in `tests/pipelines/test_agent_memory.py` against the real SQLite store and the real support-agent entrypoint. The model boundary is stubbed. The write gate, PHI screen, audit rows, and retrieval are not stubbed.

Run from `services/api`:

```powershell
uv run pytest --rootdir . ..\..\tests\pipelines\test_agent_memory.py -q -p no:cacheprovider --tb=short
```

## Approved cycle

Actor A says that Manchester internal referrals now go through the coordinator before the specialist.

- The reply asks to remember that sentence.
- The facts table stays empty.
- The audit row is `proposed`, with A's user id, an originating turn id, and a timestamp.

A then approves that pending proposal.

- The audit row is `approved`, with its own timestamp and originating turn.
- `authorized_by_user_id` is A.
- The fact's `claim_status` is `unverified`.

A later question from A about Manchester referrals includes the note, labeled unverified. Actor B, using A's `thread_id`, does not receive the pending proposal or the fact.

## Rejected cycle

Actor A receives a proposal for the Austin road-closure explanation and rejects it.

- The facts table stays empty.
- The audit row is `rejected`, with A's user id, an originating turn id, and its own timestamp.
- A later question does not include that note.

## Other checks in the same module

- A safe edit is audited as `edited` and does not write a fact until a later approval.
- An edit message that names a patient is `rejected_phi`, with a null body, and the previous safe pending text stays.
- The Johnson appointment sentence is refused without that name in the response, trace, checkpoint, or memory database.
- A memorable Manchester referral sentence that also says "John Smith is a patient" is refused. That name is not proposed, returned, or retained. The check still does not guarantee every PHI phrase.
- A generation-model failure while a proposal is pending is classified as unclear and discards the proposal. The word "yes" in that message does not approve a write.
- If the audit insert fails, approval does not leave a fact, staging does not leave a proposal, and rejection, edit, discard, and expiry do not change the pending proposal.
- A topic change discards the pending proposal.
- A second proposal is not staged while one is still pending.
- An approved false referral duration does not replace a retrieved 11-day knowledge answer and is not visible to another user.
- Consolidation supersedes by key, expires old facts, caps active rows, and blanks patient content.
- The memory path does not call the Qdrant client.
