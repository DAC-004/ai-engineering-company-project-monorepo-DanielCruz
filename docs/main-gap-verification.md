# Main-gap fixes prepared for review

Remote main remains b93a51c. Nothing is merged or deployed by this update. PR44 remains held/open for Daniel's review; its title/description are unchanged.

The current PR44 code plus the scoped tokenizer-fixture correction passes all169API tests, zero failures/errors/skips. The fixture previously replaced explicitly configured NLTK_DATA with an absent per-worktree directory, causing real readability scoring to return LookupError and the two RFP tests to fail. It now honors configured offline assets. No evaluator, threshold, role check or assertion changed. Existing PR44 isolated SQL fixtures are preserved.

Enhance tasks have their own review branches/PRs, not silently merged into this one: Audit Log PR45, Asynchronous Processing PR46, and feature/security-hardening still being finalized. Their final source/evidence documents describe what is verified. Main still requires separately approved integration of those reviewable changes; this document does not claim those unmerged features are already present on main.

No source cleanup, external email, credentials/permissions change, unrelated service interruption or merge was performed.
