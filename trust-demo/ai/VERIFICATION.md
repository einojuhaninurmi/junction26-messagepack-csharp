# AI boundary verification — no genuine model run

2026-11-14. Production provider registry: empty. No provider-specific API, SDK, HTTP request format or fake production provider was added.

Actual passing checks:

| Check | Result | Log |
| --- | --- | --- |
| AI material/response/provenance/error unit tests | 18 passed | `unit-test-results.txt` |
| Ephemeral local HTTP contract tests | 6 passed | `http-test-results.txt` |
| Original report tests | 5 passed | `data-test-results.txt` |
| Existing collector contract tests | 7 passed | `collector-test-results.txt` |
| Chrome checks (10 original + 5 design + 3 collector + 3 AI groups) | All 21 groups passed | `browser-test-results.txt` |

All provider replies in tests are explicitly labelled TEST-DOUBLE or TEST-DOUBLE ONLY. Successful test records are created only in temporary directories or injected into disposable browser responses; none are stored as completed production reviews. The real demo endpoint was tested only with absent provider configuration. At verification, its stored attempts all had `status: not_run`, `missing_configuration`, null model/service/input hashes and no result.

The tests demonstrate response shape validation; unknown evidence, invalid revision, missing/directory/unsafe paths and invalid line-range annotations; existing-reference caveats; error/timeout handling; late-result rejection; secret suppression; preservation of old records; same-origin JSON protection; and distinct AI review decision IDs, restore and export. A deliberately hostile material string remains in the untrusted material field and is not promoted to instructions. This tests the boundary, not a real model's injection resistance.

Material preparation was exercised against actual run `20261114T211745Z-9e9c520a`. It uses 22 numbered context files (11 per revision), the pinned diff and 19 evidence entries. It excludes prior assessment prose, the prepared finding and comparison expectations. Input generation is deterministic for the same frozen evidence files. Tests/probe may reveal defects: this is explicitly evidence-assisted, not blind.

The original evidence SHA-256 manifest and original `report.json`/schema hashes still match. The evaluated MessagePack code and collector were not modified; no new MessagePack tests or model-quality conclusions are claimed. Existing collector and UI tests remain intact and pass. New AI reviews require their own human decision, never an inherited approval. No commit or push was made.

Unverified: actual provider transport, real authentication, genuine model behavior/quality, provider JSON/role support, real token/cost constraints, actual provider error/cancellation semantics and data-retention behavior. These require provider selection and an explicitly implemented adapter. See README.md for the exact integration information still needed.
