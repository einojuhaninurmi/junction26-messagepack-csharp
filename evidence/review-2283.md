# Issue 2283: first Earned Trust in AI Code review

Review date: 2026-11-14, Europe/Helsinki.

Responsible person:

Human approval:

## Requirement and scope

Primary requirement: [MessagePack-CSharp issue #2283](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2283), accessed successfully during this review. The issue reports generator and analyzer exceptions when a consumer references a closed generic value type from another assembly. It expects a clean consumer build with a generated resolver. The supplied example uses a generic record struct. The reported environment is MessagePack 3.1.8, SDK 10.0.204, Windows 11; this review tests the supplied repository snapshot on Mac instead.

The requirement was read from the issue, independently of the implementation. The attached ZIP was not downloaded; the inline example was exercised. Later upstream fixes and linked PRs were not used as an implementation oracle.

### Frozen comparison

| Role | Commit |
| --- | --- |
| Base | `32258fdbee4bcd653c79f51b4376b5103c6f4d27` |
| Head | `9df83c38409c8bfad0517aebffe48211eda4a5b4` |

`git show --format=raw` establishes that head has exactly one parent, the base above. Head's subject is `implementation for #2283`. Its parent is the PolySharp update commit, also pointed to by the local and remote PolySharp dependency branch. This is a one-commit change, not a comparison against current master. The commit message and user context identify the evaluated AI change; Git metadata alone does not establish authorship by a model.

Exact comparison: `git diff 32258fdbee4bcd653c79f51b4376b5103c6f4d27 9df83c38409c8bfad0517aebffe48211eda4a5b4`.
Saved as [evaluated.patch](review-2283/evaluated.patch), with [head metadata](review-2283/head-commit.txt).
It changes four files: README.md, doc/analyzers/MsgPack004.md, TypeCollector.cs and GenericsFormatterTests.cs (225 insertions, 3 deletions).

The working branch is `junction/trust-demo`. Its HEAD and `ju26-issue-2283` still point to the frozen head. The uncommitted conditional Roslyn 4.11.0 change in Directory.Packages.props is a separate setup correction, excluded from this commit-to-commit diff. Setup evidence is retained in [setup/README.md](setup/README.md). No evaluated source or tests were edited during review. Only evidence was added; no commit or push was made.

## Acceptance criteria and implementation

1. Metadata-only generic struct and record struct members must not produce AD0001/CS8785 crashes.
2. The consumer must receive a generated resolver, including with the inline example's implicit resolver configuration.
3. Generated consumer output must compile, not merely have an expected filename.
4. Existing source diagnostics and supported behavior must remain usable (review-derived regression criterion).

The code replaces two unsafe syntax-reference lookups with nullable lookups. It also wraps TypeCollector's diagnostic callback so only diagnostics located in the active compilation are forwarded. The new helper returns a property identifier location when a PropertyDeclarationSyntax exists. Three tests compile a defining assembly to a metadata image, exercise consumer analysis/generation, and check resolver presence. Documentation explains metadata generic support and assigns referenced-member diagnostics to the defining project.

For criteria 1–3, evidence supports the concrete inline example and the three added cases. Criterion 4 has the confirmed edge-case gap below. Passing tests alone are not treated as proof of the whole requirement or of all serialization behavior.

## Findings

### F1 — Confirmed diagnostic gap: positional record null keys become silent (medium)

Locations at frozen head: [TypeCollector.cs:985](../src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs#L985), [TypeCollector.cs:1434](../src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs#L1434), [TypeCollector.cs:1446](../src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs#L1446).

For a source declaration `public partial record struct Sample([property: Key((string)null)] int Value)`, the property symbol points to ParameterSyntax. The new helper accepts only PropertyDeclarationSyntax, returns null, and the global source-location filter drops MsgPack005. The same invalid key on an ordinary property reports MsgPack005. The independent probe reproduces both cases, plus an unkeyed-property control that still reports MsgPack004.

This is not evidence that head introduced a regression from previously correct record behavior: the same base probe throws AD0001/InvalidCastException for the positional-record case. Head removes that crash but leaves an invalid source contract without its intended diagnostic. Existing tests all pass, so they do not cover this gap. No serialization data-loss claim is made from this probe.

Suggested follow-up, not applied: handle ParameterSyntax identifiers as well as property declarations, and add a targeted source-diagnostic test. A human should decide whether this incomplete diagnostic handling must be resolved before accepting the patch.

### C1 — Unverified documentation guarantee and broad diagnostic filtering

Locations: [README.md:1639](../README.md#L1639), [MsgPack004.md:49](../doc/analyzers/MsgPack004.md#L49), [TypeCollector.cs:239](../src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs#L239), [TypeCollector.cs:1444](../src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs#L1444).

The callback wrapper affects every TypeCollector diagnostic, not only MsgPack004. Dropping metadata locations prevents invalid reports into the consumer's compilation. However, saying such problems are reported by the defining assembly assumes that assembly was built with the relevant analyzers enabled. A precompiled package need not satisfy that assumption. The unkeyed metadata test deliberately emits its defining assembly without running an analyzer, then expects no consumer diagnostic.

This is a documentation/design concern, not a demonstrated new runtime vulnerability. Existing source-diagnostic tests and the explicit unkeyed-property control pass. Coverage of every diagnostic affected by the broad filter is not established. Consider qualifying the documentation and explicitly agreeing on metadata diagnostic policy.

### C2 — Runtime correctness remains outside the added regressions

Locations: [GenericsFormatterTests.cs:634](../tests/MessagePack.SourceGenerator.Tests/GenericsFormatterTests.cs#L634), [GenericsFormatterTests.cs:651](../tests/MessagePack.SourceGenerator.Tests/GenericsFormatterTests.cs#L651), [GenericsFormatterTests.cs:664](../tests/MessagePack.SourceGenerator.Tests/GenericsFormatterTests.cs#L664).

The tests intentionally skip generated-source snapshots, but still run compiler/analyzer checks through the repository verifier; the second driver checks resolver hint names. The defining assembly is emitted without its generator, so the tests are not an end-to-end generated-library serialization test. The independent probe strengthens this by generating the library first and compiling generated consumer output without an explicit resolver attribute. Neither exercise serializes/deserializes the issue's Cmd instance or publishes NativeAOT output. This is a validation limit, not a proven failure.

## Test evidence and controls

All successful head results below use SDK 8.0.428 **with the separate conditional Roslyn 4.11.0 setup correction**. They do not establish that the original branch builds unchanged.

| Run | Result | Evidence |
| --- | --- | --- |
| Earlier original-head build, without setup correction | Exit 1; 15 errors, 5 warnings, including CS9057 | [original build](setup/original/build.log) |
| Clean + full Debug solution build, corrected environment | Exit 0; 0 errors, 2 NU1901 warnings | [clean](setup/new/clean.log), [build](setup/new/build.log) |
| Full Mac-supported solution tests, corrected environment | Exit 0; 1592 passed, 6 skipped, 0 failed across 8 projects; includes 170 generator/code-fix tests | [test log](setup/new/test.log), [TRX files](setup/new/test-results) |
| Head's three ClosedGeneric regression tests, corrected environment | Exit 0; 3 passed | [targeted head log](review-2283/head-targeted.log), [TRX](review-2283/head-results) |
| Base production code + identical head regression test file + same setup correction, isolated temporary tree | Exit 1; all 3 failed with AD0001 and CS8785 / IndexOutOfRangeException, at base TypeCollector.cs:1075 | [targeted base log](review-2283/base-targeted.log), [TRX](review-2283/base-results) |
| Independent head probe | Exit 0; generated library and implicit-resolver consumer both emit successfully; source diagnostic controls expose F1 | [probe log](review-2283/probe.log) |
| Identical probe with base generator binary | Exit 0 for harness; issue example reports AD0001/CS8785 and no generated consumer resolver; positional null-key case reports AD0001/InvalidCastException | [base probe log](review-2283/base-probe.log) |

The probe is observational: exit 0 means the harness completed, not that every observed case is correct. Base consumer compilation can emit successfully despite generator failure, which demonstrates why compiler success alone is insufficient.

Commands executed from repository root unless otherwise stated:

```sh
dotnet test tests/MessagePack.SourceGenerator.Tests/MessagePack.SourceGenerator.Tests.csproj -c Debug --no-build --no-restore --filter 'FullyQualifiedName~ClosedGeneric' --logger trx --results-directory evidence/review-2283/head-results
git archive 32258fdbee4bcd653c79f51b4376b5103c6f4d27 | tar -x -C /tmp/ju26-review-2283-base
cp tests/MessagePack.SourceGenerator.Tests/GenericsFormatterTests.cs /tmp/ju26-review-2283-base/tests/MessagePack.SourceGenerator.Tests/GenericsFormatterTests.cs
# In the temporary base tree only: apply the same conditional 4.12.0 -> 4.11.0 setup change.
# From /tmp/ju26-review-2283-base:
dotnet test tests/MessagePack.SourceGenerator.Tests/MessagePack.SourceGenerator.Tests.csproj -c Debug --filter 'FullyQualifiedName~ClosedGeneric' --logger trx --results-directory /Users/os/junction26-messagepack-csharp/evidence/review-2283/base-results
# Copy Probe.cs and the saved head project to /tmp/ju26-review-2283-probe/Program.cs and Probe.csproj:
dotnet run --project /tmp/ju26-review-2283-probe/Probe.csproj
# Repeat with Probe.base.csproj.txt as Probe.csproj for the base-generator observation.
```

Probe artifacts: [source](review-2283/Probe.cs), [head project](review-2283/Probe.csproj.txt), [base project](review-2283/Probe.base.csproj.txt). These reference already-built binaries using explicit local paths. The base production files came from the archive; only the head test file and environment correction were overlaid. This is a regression control, not an untouched-base build. No complete base solution test run was performed.

Two preliminary probe attempts failed due to harness-only syntax and parser-option mistakes; their logs are retained as `probe-initial-compile-error.log` and `probe-initial-language-options-error.log`. These are not findings about the evaluated code. The final source fixes the harness syntax and uses consistent C# 12 parser options.

## Repository practices, security and compatibility

CONTRIBUTING.md, SECURITY.md, project configuration and the existing verifier were inspected. The change follows the existing nullable syntax-location helper pattern, adds tests in the existing generic formatter suite, and documents behavior. It adds no production dependencies, public API, network access, file access, executable payload or runtime deserialization path. Static inspection found no new direct security vulnerability; this is not a security certification.

The diagnostic filter changes compile-time observability and can hide problems if location handling is incomplete (F1). Missing generated artifacts are particularly consequential in AOT deployments, so the explicit artifact and emit checks matter. No wire-format compatibility claim follows merely from unchanged runtime code: generated code can affect runtime behavior. No wire-format, cross-version or hostile-input runtime comparison was executed. The existing NuGet.Protocol warning is outside this evaluated diff and remains recorded, not suppressed.

The issue's original SDK/OS/package combination, Windows/net472, Linux, Unity/IL2CPP, Release, trimming, NativeAOT publishing, runtime round-trip of the exact example, cancellation/performance and packaged analyzer loading remain unverified. Six pre-existing skips and duplicate-ID omissions in the full run are described in setup evidence. The original user-reported seven-warning build log remains unavailable; no replacement result is invented.

## Human decision required

- Decide whether F1 must be fixed before acceptance, and assign any follow-up separately.
- Agree on the referenced-assembly diagnostic policy and whether C1 documentation needs qualification.
- Decide whether runtime round-trip/AOT and original-environment validation are required for this release.
- Review the separate setup correction independently of this AI change.

No approval decision or numerical trust score is assigned by this review. Responsible person and human approval are intentionally blank above.
