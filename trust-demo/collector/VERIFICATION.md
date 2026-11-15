# Actual collection verification

Date: 2026-11-14. SDK 8.0.428, Roslyn compiler 4.11.0-3.25569.22, macOS arm64, Python 3.12.5. Both sides used the same conditional Roslyn compatibility correction.

| Run ID | Collector exit | Collection outcome |
| --- | ---: | --- |
| `20261114T211107Z-43ec9dbc` | 2 | Intentional missing-dotnet environment exercise; neither check executed on either side |
| `20261114T211117Z-0ab4e209` | 0 | Prior observations reproduced; 31 logged commands |
| `20261114T211745Z-9e9c520a` | 0 | Same observations reproduced again; 31 logged commands |

Reports and their full provenance are under `trust-demo/runs/<run ID>/report.json`. Each contains actual command argv/cwd/log/exit metadata, check states, unique version, tools, setup diff references and input hashes. The initial environment run recorded 17 command attempts including cleanup; both dotnet launch attempts have null exit codes and an explicit execution error. Neither missing process nor missing result is a pass.

For **each** successful run:

| Check | Base | Head |
| --- | --- | --- |
| Exact three metadata regressions | 0 passed / 3 failed; AD0001, CS8785, IndexOutOfRangeException | 3 passed / 0 failed |
| Referenced-library probe | Generated resolver, emit true | Generated resolver, emit true |
| Metadata consumer / implicit resolver probe | AD0001 + CS8785, IndexOutOfRangeException, resolver absent, emit true | No diagnostics, resolver present, emit true |
| Unkeyed source control | MsgPack004 | MsgPack004 |
| Ordinary null-key source property | MsgPack005 | MsgPack005 |
| Positional record null key | AD0001 / InvalidCastException, no MsgPack005 | No MsgPack005; emit true |

All five probe cases completed on both sides. No actual contradiction with the prior recorded observations was found. This does not approve the change or fix F1. Base failures are expected reproduction evidence; harness exit 0 and the consumer's emit true are not product correctness verdicts.

Input hashes for test source, probe source/project and setup diff matched across base and head and across the two successful runs. Compiler versions matched. The seven collector tests compare the actual completed runs, reject missing/skipped tests and missing probe cases, and verify that a simulated changed diagnostic produces a comparison mismatch. The first cross-run assertion compared raw test array order; actual xUnit/TRX enumeration differed. `initial-repeat-order-check.txt` preserves that test-only failure. The final comparison sorts only the test identity list and still compares every identity and outcome; all other observed data remains compared unchanged.

Validation results:

- [data-test-results.txt](data-test-results.txt): all 5 existing report tests pass.
- [contract-test-results.txt](contract-test-results.txt): all 7 collector tests pass.
- [browser-test-results.txt](browser-test-results.txt): all 10 original, 5 design and 3 collector browser check groups pass. This includes actual JSON download, saved-decision restore, run-scoped decisions, all original evidence links and every first-successful-run command-log URL.
- Synthetic UI discrepancy: explicitly shown as a contradiction inside a disposable test browser only; no stored product run was fabricated or changed.
- Missing requested report: decision stays pending and its form is disabled, with a visible explanation.
- Original referenced evidence SHA-256 values and the original report/schema hashes match their existing manifests.
- `git worktree list` contains only the original working tree after collection. No temporary worktree remains.
- `git diff --check` passes. The only pre-existing tracked-file modification remains the separate Directory.Packages.props setup correction. No evaluated source was modified, and no commit or push was made.

No full solution rerun, runtime round-trip, Windows or NativeAOT check was performed by the collector. Those remain explicit limits, not newly established defects or passing checks. Browser tests supply no human approval.
