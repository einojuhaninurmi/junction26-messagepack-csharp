# Reproducible issue #2283 evidence collection

From the repository root, one command creates a new run:

```sh
python3 trust-demo/collect_evidence.py
```

Python 3.12+, Git with worktree support, the repository-selected .NET SDK and NuGet access/cache are required. This environment selected SDK 8.0.428 and compiler 4.11.0-3.25569.22. No API key, model service or GitHub integration is used. Git writes worktree registration under `.git`; .NET needs its normal restore/process permissions. Under a sandbox, run with the required native permissions rather than suppressing checks.

Each invocation creates `trust-demo/runs/<UTC timestamp>-<random suffix>/report.json` and its artifacts. Run IDs are unique. The invocation's exit code is:

- **0:** all required checks executed, and their observations reproduced the previously recorded behavior. This includes three expected failing **base** tests; it is not product approval.
- **1:** execution completed but a prior observation or shared-input comparison differed. Differences are preserved in `contradictions` and per-case `expected` / `actual` / `matches` values. A changed observation can be an improvement, not necessarily a defect.
- **2:** an environment/prerequisite/collection/cleanup failure prevented a complete comparison. Missing results are not passing results.

## Frozen inputs and exact execution

The collector reads base/head SHA and the original review version from `trust-demo/report.json`:

- Base: `32258fdbee4bcd653c79f51b4376b5103c6f4d27`
- Head: `9df83c38409c8bfad0517aebffe48211eda4a5b4`

It creates two detached temporary **Git worktrees** at these exact commits. It never switches the main working tree or commits changes. Cleanup removes only those owned temporary worktrees, including their intentional overlays. Cleanup commands and failures are logged. Temporary paths in recorded argv/cwd identify where an actual command ran; those directories are removed afterward.

Both trees receive exactly the same setup change:

```diff
-    <MicrosoftCodeAnalysisVersion Condition="'$(IsAnalyzerProject)'=='true'">4.12.0</MicrosoftCodeAnalysisVersion>
+    <MicrosoftCodeAnalysisVersion Condition="'$(IsAnalyzerProject)'=='true'">4.11.0</MicrosoftCodeAnalysisVersion>
```

The unconditional 4.12.0 dependency setting is preserved. Per-side full setup patches and hashes are stored. These setup overlays are outside the evaluated AI change.

`checks.json` pins check version `2283-checks-1`, the three full test names, project path and all five probe case names. The whole regression test file is read **from the pinned head commit**, snapshotted and copied byte-for-byte into both worktrees. Base originally lacks these tests: this is a documented test overlay, not a claim about an untouched-base build. Discovery must confirm every full name; TRX must then show exactly the same three identities with Passed or Failed outcomes. Zero discovered tests, missing TRX, missing identities and skipped tests cannot count as a pass.

Both sides execute:

1. `dotnet --info` and the selected SDK's `csc.dll -version`.
2. A fresh Debug build of `tests/MessagePack.SourceGenerator.Tests/MessagePack.SourceGenerator.Tests.csproj` in that newly created worktree.
3. `dotnet test ... --no-build --no-restore --filter '<exact three FullyQualifiedName clauses>' --list-tests`.
4. The same filtered `dotnet test` with TRX output.
5. Build and execute the identical diagnostic probe against that side's freshly built binaries.

The probe source is the existing `evidence/review-2283/Probe.cs`. Its snapshot and the generated identical `Probe.csproj` are saved. Projects live outside worktree MSBuild imports. The only per-side project argument is `EvidenceBin`, which selects that side's new test-output assemblies. Both executions use the same probe source/project hashes. SDK selection still occurs from the corresponding worktree cwd. Harness exit 0 means it completed: the parser separately verifies five cases, diagnostics, exception types, resolver presence and emit observations.

All commands use argv arrays without a shell. Every command has its actual cwd, timestamps, combined stdout/stderr log, exit code (null if it could not start or timed out) and execution status in the JSON. Check statuses distinguish `passed`, `test_failed`, `observed`, `environment_blocked` and `not_run`. Tool and runner/harness source provenance are included. No log is presented as a fresh AI assessment.

## Viewing runs and human decisions

Start the existing demo if it is not running:

```sh
python3 trust-demo/server.py --port 2283
```

Open http://127.0.0.1:2283/ and refresh after collection. The **Reproducible evidence runs** section lists completed reports, including blocked runs. Partial runs without a finalized report are not treated as completed. Invalid finalized reports are explicitly reported by the index. The local server validates run structure and artifact existence and serves only the artifacts declared by that run.

The original AI assessment/data is unchanged. The decision form defaults explicitly to that original assessment. Showing a run does **not** apply the original decision to it. Choose **Use selected run as decision scope** to bind a new decision to the run's version (`<original review>+run.<run ID>`) and the same full base/head SHA pair. It starts pending unless that exact run already has its own saved decision. The URL receives `?run=<run ID>` so reload restores the selected report and its own decision. **Return to original assessment** restores the original scope. Exports include the selected version and commit binding. A missing requested report disables that decision form instead of falling back to an old approval.

## Actual results and failure handling

The first successful run was `20261114T211117Z-0ab4e209`, collector exit 0:

- Base: the exact three regressions executed; 0 passed, 3 failed with AD0001, CS8785 and IndexOutOfRangeException.
- Head: the exact same three executed; 3 passed, 0 failed.
- All five probe cases completed on each side and matched prior observations, including missing MsgPack005 on the head positional record, the base InvalidCastException, and the ordinary-property MsgPack005 control.
- Identical test source, probe source/project and setup patch hashes verified across versions. No contradictory prior observation was found.
- All owned worktrees were removed successfully.

A real environment-failure invocation was also executed:

```sh
python3 trust-demo/collect_evidence.py --dotnet /missing-earned-trust-dotnet
```

Run `20261114T211107Z-43ec9dbc`, collector exit 2, records a failed attempt to start dotnet on each side, null process exit codes, explicit environment reasons and both checks `not_run`. No product test outcome is inferred. Its worktrees were removed. This is an intentional environment-failure exercise, not a finding against MessagePack.

A second real successful collection is recorded separately in `runs/`; see `VERIFICATION.md` for its ID and final verification results. A per-command timeout defaults to 600 seconds and can be set with `--timeout`.

## Focused validation

```sh
python3 trust-demo/test_report.py
python3 trust-demo/test_collector.py
python3 trust-demo/test_chrome.py --design-checks --collector-checks
```

The seven collector contract tests cover two actual successful runs with identical observations, shared-input/test identity provenance, the real blocked run, missing probe cases, missing test identities, skipped results and a simulated non-repeating diagnostic finding. The simulated discrepancy is test-only, not an actual product observation. Browser checks cover successful and blocked reports, all command-log links, isolated decision scopes and restore, explicit simulated contradiction display and missing-report handling, in addition to the previous demo assertions. Test data exists only in disposable browser profiles. The initial combined browser test exposed a test-isolation issue (an extra run storage key affected the old single-record fixture); the supplemental test now removes only its own temporary run key before the original assertions continue. See `initial-browser-test-isolation-error.txt` and final `browser-test-results.txt`.

This collection is deliberately limited: it does not repeat the full solution suite, runtime round-trip, Windows, NativeAOT, packaging or security review. Previous full-suite results remain historical evidence. Recorded names are not verified identities and no automatic acceptance is performed.
