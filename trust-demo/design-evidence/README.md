# Review-tool design refinement

Recorded 2026-11-14. Local URL: http://127.0.0.1:2283/.

## Changes

- Inspected the existing running app in Chrome before editing; captured desktop (1440 × 1000 viewport) and mobile (390 × 844 viewport) full-page screenshots.
- Replaced the promotional hero, decorative brand mark, repeated headings and individual limit cards with a compact system-font review workspace. Neutral surfaces, blue links/actions, orange finding emphasis, subtle dividers and consistent spacing.
- Placed F1 and its base/head observations first. Preserved the distinction between a resolved metadata crash and a remaining source diagnostic gap; no claim of a regression from previously correct behavior.
- Added a semantic four-column acceptance table: requirement, observed result, evidence and limitation. Test case names remain available in a disclosure. Actual logs remain directly accessible.
- Moved the decision into a narrower desktop sidebar; it follows the full review body on mobile. A short list of unresolved/unverified items also appears immediately before the form.
- Moved full commit identifiers, technical scope, recorded runs, concept card and lessons log into native keyboard-operable disclosures.
- Changed the primary action to “Record decision”. Save/error feedback stays beside the action. Acceptance reveals a residual-risk explanation and requires an unchecked-by-default explicit acknowledgement. New saves/export records include `decision.residualRiskAcknowledged`; the existing origin storage key, SHA/version binding and previous saved records remain compatible. An older record without this field is not silently treated as acknowledged; a new acceptance save requires the checkbox.
- Green applies only to the recorded passed-test count, not skipped counts, whole rows or approval state. Actual loading and error feedback remains tied to report fetch/validation events. Reduced-motion mode disables the short save-feedback animation.

## Screenshots

| Viewport | Before | After |
| --- | --- | --- |
| Desktop | [before-desktop.png](before-desktop.png) | [after-desktop.png](after-desktop.png) |
| Mobile | [before-mobile.png](before-mobile.png) | [after-mobile.png](after-mobile.png) |

The original browser test captures its mobile screenshot after testing stale stored decisions, so the before-mobile capture contains that test-only rejection message. The final after screenshots are captured in a fresh pending state before test decisions. All test profiles are disposable; no human decision is supplied by these captures.

## Actual verification

Commands from repository root:

```sh
python3 trust-demo/server.py --check
python3 trust-demo/test_report.py
python3 trust-demo/test_chrome.py
python3 trust-demo/test_chrome.py --design-checks
shasum -a 256 -c trust-demo/design-evidence/data-before.sha256
```

- Server validation passed.
- All 5 existing data tests passed: [final-validation-results.txt](final-validation-results.txt).
- All 10 existing browser checks passed without removing or relaxing assertions: [after-browser-results.txt](after-browser-results.txt).
- Final run: all 10 original browser checks plus 5 design check groups passed, exit 0: [final-browser-results.txt](final-browser-results.txt). The groups verify desktop/mobile placement and table semantics, keyboard focus/Enter activation, contrast, reduced-motion behavior, and explicit acceptance acknowledgement with reload persistence. The layout group also verifies green spans contain only passed counts.
- Save/read-back, restore, SHA/version isolation, actual JSON download, unsaved-edit exclusion, all 11 artifact links, storage denial, malformed report handling and mobile overflow remain covered by the original assertions.
- Contrast checks cover the specified primary, secondary, blue-link, orange-finding and green-passed text colors on white at ≥ 4.5:1. This is not a full accessibility certification or a screen-reader audit. Screenshots were also visually inspected in both sizes.
- `report.json` and `report.schema.json` hashes match [data-before.sha256](data-before.sha256). Every previously recorded evidence hash in `trust-demo/evidence-sha256.txt` also matches. MessagePack source, setup correction and original evidence were not modified. No new product test results are claimed.

Two added keyboard-test attempts failed because the synthetic Enter event lacked its text/keypress information. Logs are preserved as `initial-design-keyboard-check.txt` and `keyboard-event-diagnostic.txt`. The final test sends the full Enter event, verifies focus and checks the same disclosure-open assertion. No app workaround or weakened assertion was used.

No commit or push was made.
