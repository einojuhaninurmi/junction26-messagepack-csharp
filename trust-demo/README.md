# Earned Trust — local reference demo

A single English-language view of the **recorded** issue #2283 review. It does not run an AI assessment, calculate trust scores, verify identity or submit GitHub approvals.

From the repository root:

```sh
python3 trust-demo/server.py --port 2283
```

Open **http://127.0.0.1:2283/**. Python 3.12 and a modern browser are sufficient. No runtime packages, Node, build step, cloud account or external assets are required. The server binds only to loopback. Keep this terminal running; Ctrl-C stops it.

## Files and evidence

- `report.json`: review data, separate from the presentation. Derived from `evidence/review-2283.md`, the setup record and their logs. Missing evidence is explicitly described in Limits.
- `evidence-sha256.txt`: hashes of the existing evidence files consumed by this presentation, recorded when the demo was built. These hashes are not signatures.
- `report.schema.json`: closed JSON Schema for the data structure. The Python server validates its used subset (type, required, additionalProperties, const, pattern, minLength, minItems, properties and items) before serving. Browser validation repeats structural checks. Server startup also checks IDs, traceability references and evidence file existence.
- `server.py`: standard-library local server. Evidence links serve only explicitly listed artifacts, as plain text. It exposes neither the rest of the repository nor a decision-writing API.
- `index.html`, `app.js`, `style.css`: accessible, responsive presentation. Text from JSON and human inputs is inserted as text, not HTML.
- `test_report.py`, `test_chrome.py`: focused checks for the report contract and the decision/traceability flows.

The MessagePack production code, tests, setup correction and `evidence/setup` are unchanged by this demo. No new MessagePack assessment was run while building the presentation. The app's validation tests test the demo, not the issue fix.

## Human decision

Initial state: **Pending human review**, blank name, rationale and residual risk. Saving requires all fields and an explicit decision (Accept, Request changes or Defer). Save is explicit, not automatic.

A decision is stored in `localStorage` under a key containing the full base SHA, head SHA and review version. The same binding is validated inside the stored record and included in the JSON export. A different version or commit pair does not inherit an old decision. Maintain `reviewVersion` when the saved assessment changes; this demo does not automatically detect repository or evidence updates.

Export contains the **last saved** decision, not unsaved edits. The app identifies unsaved edits and storage errors. The typed name is self-declared; the timestamp comes from the browser clock. Neither is independently verified. This is not a signed, tamper-proof audit log or multi-user approval workflow. Local storage and exported JSON can be edited by their owner.

Storage belongs to the browser profile and exact origin (`http://127.0.0.1:2283`). A different port, `localhost` instead of `127.0.0.1`, private browsing or cleared browser data can yield an empty decision. Export a copy if you need to retain it. No decision is written to the repository or sent to a remote service.

## Verification

```sh
python3 trust-demo/server.py --check
python3 trust-demo/test_report.py
```

Browser checks use the installed Google Chrome through a small standard-library DevTools driver and a disposable profile. No browser packages are required:

```sh
python3 trust-demo/test_chrome.py
```

Run the server first. Browser tests use a temporary profile, do not touch the user's Chrome profile and leave no real human decision. They verify pending state, criterion-to-run navigation, all artifact URLs, save/reload, actual JSON download, version isolation, stale bindings, storage failure, invalid-report handling and mobile overflow. Screenshots are captured to `preview-desktop.png` and `preview-mobile.png`. See `validation-results.txt` and `browser-results.txt` for actual outcomes. Test-only decisions are not human approvals.

Verification on 2026-11-14: 5 report-validation tests and all 10 Chrome browser checks passed. The initial Chrome harness attempt rejected Chrome's valid WebSocket status text; `browser-initial-harness-error.txt` records that harness-only failure. The final driver accepts status 101 and validates the handshake. A preliminary Playwright download was cancelled as unnecessary; no Playwright checks were run. No MessagePack tests were rerun as part of this presentation task; all displayed product results are previously recorded evidence.

## Review-tool design refinement

The refined layout places F1 first, maps acceptance criteria in a table and keeps a desktop decision sidebar (after the main content on mobile). Technical details and learning notes are disclosures. Selecting Accept reveals explicit residual-risk acknowledgement, which is required for a new acceptance record. Existing decision bindings and exports remain available.

For the current screenshots and verification, see [design-evidence/README.md](design-evidence/README.md). Run the original browser checks plus the new design checks with:

```sh
python3 trust-demo/test_chrome.py --design-checks
```

## Collect new base/head evidence

```sh
python3 trust-demo/collect_evidence.py
```

This issue-specific command uses detached temporary Git worktrees and writes a unique structured execution report under `trust-demo/runs/`. It applies the same recorded Roslyn compatibility correction to both sides and verifies identical test/probe inputs and actual test execution. The UI presents these runs separately from the original AI review and uses separate human-decision versions. See [collector/README.md](collector/README.md) for exact behavior, statuses, provenance and failure checks.

## New AI code review boundary

The **Run AI review** action and provider-neutral server pipeline are implemented. Direct Anthropic is now integrated; a real key and a one-use token/cost preflight are required before a paid call. No genuine model review has been run, and no canned result is substituted. Read [ai/README.md](ai/README.md) for the adapter contract, required environment settings, excluded prior-review material, validation, provenance, test-double results and the exact information needed to implement a real provider. New AI reviews have independent human-decision bindings.
