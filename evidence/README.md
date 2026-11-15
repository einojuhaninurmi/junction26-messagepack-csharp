# Evidence retained for the Earned Trust reference demo

The evaluated MessagePack change remains frozen at base `32258fdbee4bcd653c79f51b4376b5103c6f4d27` and head `9df83c38409c8bfad0517aebffe48211eda4a5b4`. Demo/setup work is outside that diff. The conditional Roslyn 4.11.0 setup correction is separate from the evaluated production change.

The recorded first genuine model round is `trust-demo/ai-reviews/ai-20261115T003045Z-238263583d55/`. Its result, exact submitted input and instructions are retained unchanged, with matching SHA-256 provenance. It is linked to actual collection `20261114T211745Z-9e9c520a`. The decision in `decisions/issue-2283-request-changes.json` is the exact corrected JSON supplied by the user. Its review/run/commit bindings were verified. It is a self-declared human request for changes, not authenticated identity, GitHub approval or model approval.

Claude's concrete F1 describes the missing MsgPack005 probe result but labels it informational. Its broader filter/path concerns are not all demonstrated by those probes. The decision requests a diagnostic fallback and a regression test; neither is implemented here. See the root `demo-script.md` for a three-minute presentation.

## Privacy curation before the demo commit

`privacy-redactions.json` records SHA-256 before/after metadata curation. Unnecessary computer names and local test-run user attributes were removed from TRX files; host-derived original TRX filenames and their log references were neutralized. Author/committer identity in a presentation metadata copy was omitted. Original bytes were retained outside the repository, not committed. Test names, counts, outcomes, diagnostic content, commits and execution times were not changed.

The genuine model request/response/instructions and the supplied human decision were **not** rewritten. The input's original public repository security-contact text and technical execution paths remain because this exact input and its hash are necessary provenance; no new personal profiles or duplicate decisions were collected. The supplied responsible-person name is retained only where required by that decision. The initial wrong-name entry is a user-reported lesson, not a captured event record; no invented event timestamp or earlier decision is stored.

`trust-demo/evidence-sha256.txt` now checks the privacy-curated presentation artifacts. Historical statements that hashes were unchanged refer to the earlier checkpoints. `trust-demo/design-evidence/data-before.sha256` is a historical before-design snapshot, not a current checksum after the added lessons/decision link.

API-key patterns, credential material, private-key blocks and access-key patterns were checked without displaying matches. No actual secret was detected in the staged evidence. Provider request/message IDs and usage counters are audit metadata, not API keys. Test-double credentials in test source are explicit nonfunctional fixtures. Build outputs, Python caches, root preview caches and local failed API attempts are excluded. Earlier diagnostic logs are retained only as audit/debug evidence, not passed checks or genuine model results.
