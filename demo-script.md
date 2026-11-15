# Earned Trust in AI Code — issue #2283

**Length:** approximately 3 minutes. **Language:** English.

Start from the repository root with `env -u TRUST_REVIEW_API_KEY -u TRUST_REVIEW_PROVIDER -u TRUST_REVIEW_MODEL python3 trust-demo/server.py --port 2283` for a **saved-evidence presentation without a key**. Open:

<http://127.0.0.1:2283/?aiReview=ai-20261115T003045Z-238263583d55>

Do not press **Run AI review** or start a new collection during this presentation. This is a recorded first real review round, not a live model demonstration. A fresh browser will correctly show Pending human review in its local form: use the **recorded human decision** JSON link to show the actual exported decision rather than fabricating a new one.

## 0:00–0:25 — Requirement and frozen scope

**Show:** Requirement, its original issue link, and the expanded change-scope disclosure.

**Say:**

“The requirement is specific: a consumer using a closed generic value type from another assembly must not crash the analyzer or generator, and must receive a generated resolver. We fixed the comparison to the AI commit's actual parent, rather than assuming current master is the baseline. The separate Roslyn compatibility correction is applied equally to both versions and is outside the evaluated AI change.”

**Reference:** base `32258fdbee4bcd653c79f51b4376b5103c6f4d27`; head `9df83c38409c8bfad0517aebffe48211eda4a5b4`.

## 0:25–0:55 — Reproduce the evidence

**Show:** Reproducible evidence run `20261114T211745Z-9e9c520a`, base/head results and one actual command-log link.

**Say:**

“The collector uses temporary Git worktrees. Because the old version lacked these regressions, exactly the same test file is supplied to both sides, with matching hashes. All three tests actually execute: base fails all three with the reported exceptions; head passes all three. The independent probe also checks generated resolver presence and successful emit. A passing compiler exit alone would miss the original defect. This is targeted evidence, not a claim that every supported environment works.”

## 0:55–1:25 — The genuine Claude assessment

**Show:** New AI code review record `ai-20261115T003045Z-238263583d55`, model identifier and provenance disclosure.

**Say:**

“This record is a genuine Anthropic Claude Sonnet 5.5 assessment, separate from the saved example and from the collector. The model received the original requirement, frozen diff, code context and actual selected-run evidence. It did not receive the earlier prepared finding summary. However, the tests and probe can reveal defects: this is evidence-assisted review, not a blind benchmark. Input and instruction hashes, model and request identifiers preserve the connection to what was reviewed.”

## 1:25–2:00 — Demonstrated defect versus broader concerns

**Show:** F1's source example and base/head probe logs; then Claude's F1 and F2.

**Say:**

“The positional record null-key probe gives us a narrow, demonstrated gap: the head no longer crashes, but emits no MsgPack005. An ordinary null-key property still reports that diagnostic. Base already threw InvalidCastException here, so we must not describe this as a regression from previously correct behavior.

“Claude noticed the gap but classified its F1 as informational. Its F2 warns that the location filter affects more diagnostic paths. The missing diagnostic in this concrete probe is demonstrated; broader effects and other unsafe syntax paths remain concerns requiring additional validation. Existing file and evidence references establish traceability, not that every interpretation is correct.”

## 2:00–2:25 — Limits and a useful lesson

**Show:** Limits and the expanded lessons log.

**Say:**

“The exact example's runtime round-trip, Windows and NativeAOT remain unverified. The selected collection did not repeat the full solution suite. A separate earlier Mac suite passed with six existing skips; that historical result is not this model run's new execution. All successful results depend on the documented Roslyn setup correction.

“There was also a human-interface mistake: a review ID was first entered as the responsible person and then corrected to a name. That name remains self-declared, not verified identity. The correction is a user-reported lesson, not a captured event timeline.”

## 2:25–3:00 — Human request for changes

**Show:** Footer link **Recorded human request for changes (self-declared identity)**, opening `evidence/decisions/issue-2283-request-changes.json`.

**Say:**

“The recorded human decision is request_changes, bound to this AI review, evidence run and exact commits. It asks for a diagnostic fallback location and a regression test before acceptance. No residual risk is accepted for approval at this stage. We preserved that decision exactly as exported; we did not upgrade the model's severity, invent an approval, or apply the requested fix.

“This is a local reference demonstration of traceable evidence and human accountability. It is not an approved change, verified identity system, or finished production review product.”

## Presenter checks

- The genuine record must say `completed`, service `anthropic`, model `claude-sonnet-5-5`; test-double records are not substitutes.
- The decision must remain `request_changes`, not Accept. Do not re-save the form merely to make a fresh browser look decided.
- Show no key, credential headers, environment dumps or terminal secret entry.
- If asked about wider correctness or model reliability, state the recorded limits; do not invent trust percentages or extrapolate from one issue.
