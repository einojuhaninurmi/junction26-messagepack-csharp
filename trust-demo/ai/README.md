# AI review for issue #2283 · direct Anthropic integration

**The first genuine Anthropic round is recorded:** `ai-20261115T003045Z-238263583d55`, followed by a human `request_changes` decision. Direct Anthropic was selected on 2026-11-15. The registered adapter is `anthropic`, using `claude-sonnet-5-5`. See [ANTHROPIC.md](ANTHROPIC.md) for official documentation, prices, token/cost preflight, test results and the safe first-run procedure.

From a Mac zsh terminal at the repository root:

```sh
python3 trust-demo/start_claude.py
```

The launcher asks for the key without echo and replaces itself with the server, passing the credential only through the server environment. The shell's environment/history and server arguments do not contain its value. Read-only Git children explicitly do not inherit the key. The launcher refuses noninteractive input and an occupied port before requesting any key. No model call occurs at startup.

Open http://127.0.0.1:2283/. Select an evidence run, choose **Check tokens & cost (no generation)**, read the result and then choose **Run AI review** once. This second action is paid. The first sends material to Anthropic's free token counter but requests no generation. Without settings, the action reports missing configuration, never a canned assessment.

## Adapter contract and configuration

`adapters.py` defines a Python `Adapter.review(ReviewRequest) -> ReviewReply` protocol. The interface assumes no universal HTTP API. The direct implementation is in `anthropic_direct.py` and is explicitly registered in `PROVIDERS`; an environment variable cannot import arbitrary code. Test doubles are injected only inside tests and are not in that map.

Server environment settings:

| Variable | Meaning |
| --- | --- |
| `TRUST_REVIEW_PROVIDER` | `anthropic` for the selected direct adapter |
| `TRUST_REVIEW_MODEL` | `claude-sonnet-5-5` (this demo deliberately does not silently switch models) |
| `TRUST_REVIEW_API_KEY` | Credential read by the server only; never accepted from the browser or included in material |
| `TRUST_REVIEW_WORKSPACE_ID` | Optional non-secret `wrkspc_…` ID for keys not scoped to one workspace |
| `TRUST_REVIEW_TIMEOUT_SECONDS` | Optional deadline, 300 seconds by default for Anthropic, greater than 0 and at most 300 |

Merely setting variables does **not** make an unsupported provider configured. The UI lists missing variables/adapter status without exposing their values. Put a real credential only in the server process environment, never in a repository file, URL, browser storage, command-line argument, screenshot or chat message.

A `ReviewRequest` holds trusted instructions, the response schema, separate untrusted material JSON, the requested model, server-only API key and timeout. There are no tools, callable file/command capabilities, subprocess hooks or write handles. A provider adapter must map those fields to the selected provider's **actual documented API**, preserve instruction/data separation, disable all tools/agents/computer or command execution, enforce transport timeouts, normalize the provider output, and return actual service/model identifiers. It must map its transport timeout to `TimeoutError` and must not log credentials, request headers or raw provider errors. It must not blindly assume that JSON-schema support or role semantics match another service.

The orchestration deadline discards late replies and records `timeout`. A single outstanding provider request is allowed; if a timed-out adapter thread has not stopped, another request is rejected as busy. Python cannot forcibly terminate an arbitrary trusted adapter thread: correct transport cancellation/timeouts must be part of the selected adapter. This limitation is explicit, not treated as evidence of a successful response.

## Exact model input and contamination boundaries

`pipeline.build_material(run_id)` creates a deterministic, allowlisted JSON bundle:

1. `requirement.json`: the original issue's expected-behavior excerpt, source URL, access date and a paraphrase of its reported trigger. The source issue was read directly, not inferred from the evaluated implementation or the old review. The full issue/attachment and later upstream discussions are not included.
2. The complete pinned Git diff from base `32258fdbee4bcd653c79f51b4376b5103c6f4d27` to head `9df83c38409c8bfad0517aebffe48211eda4a5b4`, including the documentation changes that are part of that evaluated commit.
3. Numbered base/head context from a fixed list: TypeCollector, generator, analyzer, the existing test verifier, CONTRIBUTING.md, SECURITY.md, .editorconfig, build/package settings and the source-generator project. These files are read with read-only Git operations. The model cannot choose commands or repository paths to execute.
4. Selected run's **actual** test outcomes, probe observations, tool versions, build/test/discovery/probe logs, the exact executed test source and probe source, and the same setup patch for both revisions. Harness-source hashes are verified against the run record.
5. Explicit scope/environment limits: conditional Roslyn correction, targeted checks only, original issue environment differs, no new whole-solution/runtime-roundtrip/Windows/NativeAOT execution by that collection.

Evidence IDs such as `observations`, `harness:Probe.cs` and `command:13-base-regressions` are part of the bundle. Actual command IDs come from the selected run; do not hard-code them when interpreting output. The local payload limit is 1.5 MB and there is no silent truncation. The tested successful-run bundle is approximately 465 KB. The Anthropic adapter uses account-specific Models API limits and the full token-count request before generation; bytes are not treated as tokens. It refuses overflow rather than shortening input.

**Excluded:** `evidence/review-2283.md`, `trust-demo/report.json`, the prepared MsgPack005 finding and narrative summaries, run `status` as a previous-observation verdict, `reason` prose, `comparisons`, `expected`, `matchesPreviousObservation`, `contradictions`, and the collector's comparison implementation. Projection also allowlists the fields inside test and probe observations. No entire prior run JSON or prior AI output is sent to a new model call.

**This is evidence-assisted review, not a blind test.** The executed tests and diagnostic probe source/output can themselves disclose an issue. Also, test names and comments inside the evaluated diff can reveal its intent. Those are legitimate supplied evidence, not an independent blind benchmark.

`instructions.txt` and `response.schema.json` are trusted server policy; every field of the material bundle is untrusted review data, including text claiming to be system instructions. The trusted instructions explicitly forbid obeying data instructions. No execution or write tools are exposed. This limits capabilities even if a model mishandles hostile text; it is not a guarantee against prompt-induced analytical bias. Humans must still inspect claims and references.

## Response validation and provenance

The strict response schema requires:

- Requirement assessments with status, rationale and evidence IDs.
- Findings with severity, explanation, base/head file/line references and evidence IDs.
- Uncertainties, unchecked matters and questions for human judgment.

There is no confidence score or approval field. Unknown fields, invalid JSON, invalid types (including booleans masquerading as line integers), unsupported severity/status, duplicate assessment IDs and oversized responses are rejected. Rejected raw provider output and raw provider exceptions are not persisted or logged. Keys accidentally echoed by a reply cause rejection.

Source/evidence references are checked after schema validation. Unknown evidence IDs, missing files, invalid revision names, out-of-range/reversed/zero/negative line ranges and unsafe paths are annotated **unverified** and retained visibly, rather than promoted to facts. Existing source ranges and IDs receive **exists**, with an explicit note that existence does not establish claim correctness. A completed review means a structurally accepted response was received; it does not mean all references or findings were proved, and it is never human approval.

Every persisted attempt has a unique `reviewId`/`reviewVersion`, timestamps, pinned base/head, evidence run ID and outcome. A submitted input additionally has input SHA-256, instruction SHA-256, schema SHA-256 and input/instruction snapshots. Requested and actual service/model identifiers are recorded when a provider was called. A missing-configuration attempt has null input/instruction hashes and null service/model because nothing was submitted. Local records are not signatures or a tamper-proof audit service.

Records live in `trust-demo/ai-reviews/<reviewId>/review.json`; input and instruction snapshots are beside submitted attempts. They are separate from collector runs and the saved example. Earlier records are not overwritten by failures. GET routes show history/provenance. The POST route requires same-origin JSON and a local Host, preventing browser cross-origin forms/DNS-rebinding hosts from triggering a future paid call.

## Human decision binding

A completed new review offers **Use AI review as decision scope**. It binds browser-local decisions to that unique AI review ID, the full base/head pair and the evidence run ID. Previous example/run/other-AI decisions are not reused. The URL uses `?aiReview=<ID>` to restore only that review's own saved decision; an unavailable/incomplete requested review cannot inherit an older approval. Exports include these identifiers. A typed name remains self-declared and unverified.

## Verification performed

```sh
python3 trust-demo/test_ai.py
python3 trust-demo/test_ai_http.py
python3 trust-demo/test_report.py
python3 trust-demo/test_collector.py
python3 trust-demo/test_chrome.py --design-checks --collector-checks --ai-checks
```

- `unit-test-results.txt`: 19 AI boundary/validation/provenance/error tests, **test doubles only**.
- `http-test-results.txt`: 7 tests on an ephemeral local server, **test doubles only** for provider responses. Includes cross-origin rejection and forbidden client overrides.
- `browser-test-results.txt`: original 10 browser groups, 5 design groups, 3 collector groups, plus 3 AI groups and one Anthropic preflight group. The real production endpoint was exercised only for missing configuration. Completed review displays, model errors and review-scoped decisions use explicit **TEST-DOUBLE ONLY** browser fixtures, never written as successful reviews on the production server.
- Existing 5 data tests and 7 collector contract tests pass; their logs are stored here.

These tests do not demonstrate model review quality, injection resistance of a real model, provider protocol compatibility or any new MessagePack behavior. The earlier adapter tests themselves performed no real model review. A later user-triggered genuine round and its human request for changes are now preserved separately; evaluated MessagePack code remains unchanged. The 17 dedicated adapter/preflight/launcher tests use injected transports only; see `anthropic-test-results.txt`. No commit or push was made.

## Recorded first round and future runs

The completed record is `ai-20261115T003045Z-238263583d55`; its exported human decision is `evidence/decisions/issue-2283-request-changes.json`. For presentation without a key or model call use the root `demo-script.md`. Older verification documents describe their historical pre-integration stage.


Direct Anthropic, the model, official API version, deadline and output cap are now selected. The remaining credential stays with you: enter it only at the launcher's hidden prompt. Verify the selected run and the real API token/cost quote in the UI before the single paid action. Account availability, token count, real transport, provider behavior and the resulting assessment remain unverified until then. See [ANTHROPIC.md](ANTHROPIC.md) for exact settings and limitations.
