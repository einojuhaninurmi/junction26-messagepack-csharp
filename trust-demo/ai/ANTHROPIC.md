# Direct Anthropic integration · first genuine run preparation

Prepared 2026-11-15. **Update:** a subsequent user-triggered genuine review is now recorded as `ai-20261115T003045Z-238263583d55`, with a human request for changes. The preparation/test statements below describe the earlier implementation stage, not the later user-run result. The user confirmed the key is directly from Anthropic, not a gateway. **No genuine model review, authenticated model lookup or token-count request was made by the agent.** Network behavior was tested with injected transports; the first authenticated requests will occur when the user launches with their key and uses the UI.

## Selected model and official documentation

Selected model: **Claude Sonnet 5.5**, API ID `claude-sonnet-5-5`, suitable for everyday coding work. Published limits are 1M context tokens and 128K maximum output; the demo deliberately reserves only **8,192 output tokens including thinking** and uses adaptive thinking at medium effort. Account access is checked before any generation; an unavailable model is an error, never a silent fallback. [Official model page](https://platform.claude.com/docs/en/models/sonnet-5-5/overview).

The direct API origin is fixed to `https://api.anthropic.com`, with `anthropic-version: 2026-10-21` and server-only Bearer authentication. An optional workspace header supports unscoped keys. No custom base URL, ambient proxy or redirect is accepted. The client makes one attempt per operation, without SDK retry behavior. [API overview](https://platform.claude.com/docs/en/api/overview), [versioning](https://platform.claude.com/docs/en/api/versioning).

Trusted review instructions are the top-level `system` value. The complete untrusted material JSON is a separate user text block. No tools, MCP, agent, container or context-compaction configuration is sent. Adaptive thinking text is neither exposed nor persisted. [Messages API](https://platform.claude.com/docs/en/api/messages/create).

JSON output uses documented `output_config.format = {type: "json_schema", schema: ...}`. Unsupported length/range/maximum-array constraints are moved into descriptions in the sent schema, and the **unchanged original local schema** still validates all constraints. Required fields, enums, closed objects and supported minItems 0/1 are retained. [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).

## Tokens and context: no byte-to-token guess

The approximately 465 KB material bundle is not a measured token count. It has not been sent to a real token counter yet.

**Check tokens & cost** performs only:

1. `GET /v1/models/claude-sonnet-5-5`: verify account access, resolve the model ID and read its token limits and structured-output capability.
2. `POST /v1/messages/count_tokens`: count the full system/user/schema/thinking input that will be used for generation.

The counted request and generated request have identical input-bearing fields. Only generation controls (`max_tokens`, `stream`, `service_tier`) are omitted from counting. No source is trimmed. Counting is free according to the [official token-counting guide](https://platform.claude.com/docs/en/build-with-claude/token-counting), but does transmit the supplied material to Anthropic. Counter values are estimates and may differ slightly from generation usage.

The adapter requires:

```text
counted input + 8,192 reserved output + 4,096 safety margin
    <= min(account-reported input capacity, 1,000,000)
```

Missing/invalid limits or count, missing structured-output support, context overflow or an excessive price estimate blocks generation. No fallback or compaction occurs. A safe public quote is returned to the browser, valid for 10 minutes and one generation. Its memory-only server binding covers the exact input, instructions, original schema, model, timeout, workspace and credential fingerprint. Changed input/key/settings, restart, expiration or prior use invalidates it. The fingerprint itself is not written to files or sent to the browser.

## Price before generation

Current standard global list rates, checked 2026-11-15:

- Input: **$2 / million tokens**.
- Output, including thinking: **$10 / million tokens**.

[Official pricing](https://platform.claude.com/docs/en/about-claude/pricing).

With counted input `N`, the UI shows this estimate using the **maximum** output reservation:

```text
USD estimate = N × 2 / 1,000,000 + 8,192 × 10 / 1,000,000
```

For illustration only, **150,000 input tokens** would cost at most about **$0.38192** at that output reservation, or **$0.390112** when pricing the extra input safety margin. **150,000 is a test/scenario value, not the measured count of this repository.** The actual first-run estimate cannot be stated honestly until the user's authenticated counter returns it.

The demo refuses quotes whose safety-margin estimate exceeds **$1.00**. This is an estimate gate, not a guaranteed invoice/spend limit: token-count differences, account terms, geography, taxes, credits or rate changes can affect billing. No cache-write, batch, fast mode or priority-capacity request is made (`standard_only`). Actual `usage` counters are recorded when returned; their price calculation is labelled an estimate, not an invoice. A failed/timed-out generation may still have incurred cost; missing usage is unknown, never zero, and there is no automatic retry.

## Safe Mac zsh launch

From a new terminal:

```sh
cd /Users/os/junction26-messagepack-csharp
python3 trust-demo/start_claude.py
```

The Python launcher uses hidden `getpass` entry, not a shell variable or command argument. It refuses noninteractive input rather than falling back to echo. It replaces its own process with the server and sets:

```text
TRUST_REVIEW_PROVIDER=anthropic
TRUST_REVIEW_MODEL=claude-sonnet-5-5
TRUST_REVIEW_TIMEOUT_SECONDS=300
TRUST_REVIEW_API_KEY=<only the hidden runtime input>
```

Do **not** paste a key into this document, a terminal command, browser, `.env` file or chat. The shell history stores only the launcher command. The parent zsh environment is unchanged, and the server's read-only Git children explicitly strip `TRUST_REVIEW_API_KEY`. The key is absent from request URLs, arguments, snapshots, logs and UI. Ctrl-C ends the server process.

If port 2283 is occupied, the launcher reports it **before requesting the key**: stop the earlier demo in its terminal first. For an unscoped API key only, a non-secret workspace ID can be supplied to the launcher process:

```sh
TRUST_REVIEW_WORKSPACE_ID=wrkspc_YOUR_WORKSPACE_ID python3 trust-demo/start_claude.py
```

Open **http://127.0.0.1:2283/**. Select evidence run `20261114T211745Z-9e9c520a` (or a later actual run of the same pinned comparison). Read the quote from **Check tokens & cost (no generation)**. Then click **Run AI review** once. No model/network call occurs at startup. Refreshing the page does not replay a paid request. The quote is consumed before the generation attempt, so double-click/reuse cannot create another paid call. The result needs its own explicitly recorded human decision.

## Usage, failures and honest missing findings

Review records preserve requested and returned model IDs, the count/model lookup request IDs, generation `request-id`, response message `id`, stop reason and available usage counters. Only safe identifiers and allowlisted counters are stored; no raw authorization headers, error bodies, thinking text or keys are logged.

Output truncation, refusal, context stop or invalid JSON/schema is a failed review, even if a text block exists. Returned usage and IDs remain available in the failed record where possible. HTTP and transport failures are explicit and not retried. If the network fails before a usage response, exact usage is unavailable. The existing pipeline timeout also rejects late replies.

The previous assessment and prepared MsgPack005 summary remain excluded from input. Probe and test source/results can themselves disclose the defect: this remains evidence-assisted, not blind. A valid response with **no findings** is accepted and displayed as such; it is not changed, retried or supplemented to force the known diagnostic finding. File/line and evidence references remain existence checks, not proof of claims. A successful API response is not a human approval.

## Test-double verification versus the genuine run

Commands from repository root:

```sh
python3 trust-demo/test_anthropic.py
python3 trust-demo/test_ai.py
python3 trust-demo/test_ai_http.py
python3 trust-demo/test_report.py
python3 trust-demo/test_collector.py
python3 trust-demo/test_chrome.py --design-checks --collector-checks --ai-checks --anthropic-checks
```

Actual results:

- **17 dedicated adapter/preflight/launcher tests passed**, using injected transport or mocked opener/exec only: `anthropic-test-results.txt`.
- **19 AI boundary tests passed**: `unit-test-results.txt`; includes stripping the API key from Git subprocess environments.
- **7 local HTTP tests passed**: `http-test-results.txt`; includes a test-double quote and exactly one test-double generation.
- **5 existing data tests and 7 collector tests passed**: `data-test-results.txt`, `collector-test-results.txt`.
- **22 browser check groups passed**: all previous groups plus a marked Anthropic test-double flow showing the price before one generation, usage/IDs, and an honest no-findings result. `browser-test-results.txt`.

All model responses in these tests are test doubles, not genuine inference. Completed test records live only in temporary directories or disposable browser mocks. Production history contains only missing-configuration attempts so far. No real credential was accessed. No authenticated model availability, real count, actual cost, real model response or finding quality has yet been measured.

The first refactoring test run caught a removed timeout variable, retained in `initial-anthropic-refactor-errors.txt`. It was corrected; no assertion was removed. The original report/schema and evidence hashes remain unchanged. No evaluated MessagePack code, full-solution result, commit or push was changed or created.

## Connection troubleshooting

See [CONNECTION-FIX.md](CONNECTION-FIX.md) for the verified macOS Python empty-CA-store correction, safe network/HTTP error classification and restart procedure. TLS verification remains mandatory.
