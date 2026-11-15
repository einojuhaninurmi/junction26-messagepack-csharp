# Anthropic preflight connection failure diagnosis

2026-11-15. No API key, credential headers, environment values, raw requests or provider error bodies were printed or logged. No paid generation was requested. The user's existing server was not stopped or its environment/key extracted.

## Confirmed cause in the tested Python environment

- Python 3.12.5 / OpenSSL 3.0.13 had **zero default trusted CA certificates**; its default CA file/directory were absent.
- The initial sandbox DNS check failed. The authorized check outside the sandbox resolved `api.anthropic.com` successfully. This sandbox-only DNS failure was not mistaken for the user's app failure.
- A direct unauthenticated HTTPS request failed with `SSLCertVerificationError`, verification code **20**, before any HTTP response. The generic `URLError` branch had hidden that category.
- The existing macOS `/etc/ssl/cert.pem` contained **128 trusted CA certificates**. Loading it with a verifying SSL context produced **HTTP 401** from the same unauthenticated endpoint. This proves DNS/network/TLS reachability, not API-key validity or model entitlement.
- No proxy environment configuration was present in the diagnostic process (only presence was checked, never values). The adapter deliberately disables ambient/system proxy routing. The direct request succeeded after the CA correction, so a proxy was not needed on the tested path.
- The direct 15-second connectivity check returned an HTTP response without timing out. Request/preflight timeouts remain enabled; no timeout increase or retry was needed.

## Minimal scoped correction

`anthropic_direct.verified_tls_context()` starts from Python's verifying default context. **Only on macOS, only when it contains zero CA roots, only when no explicit SSL_CERT_FILE/SSL_CERT_DIR override exists**, it loads the pre-existing OS CA bundle. Existing trust roots and explicit CA choices are not replaced. No certificate verification or hostname checking is disabled, no certificates are downloaded, and no global Python installation or system trust configuration is modified.

The same adapter context was then checked live without authentication: 128 roots, `CERT_REQUIRED`, hostname checking on, HTTP 401. No authenticated model lookup or token-count call was made because the running server's credential is not available to the agent. The restart below lets the user perform the genuine preflight.

## Safe diagnostics added

The adapter now distinguishes:

- DNS (`dns_error`), certificate verification (`tls_certificate_error`), other TLS (`tls_error`), other network failures (`network_error`) and timeouts.
- HTTP 401 authentication, 402 billing, 403 permission, 404 unavailable resource/model, 429 rate/spend limit, 408/504 timeout and other service errors.
- HTTP 400 invalid requests versus specific billing/credit/spend-limit signals. A 400 without a recognizable signal is explicitly ambiguous; it is not asserted to prove insufficient balance.

For HTTP errors it reads at most 32 KiB of error JSON **in memory only**, classifies known error types/markers and returns fixed messages. Raw provider messages, bodies, credential headers and requests are never exposed. Safe metadata is limited to numeric HTTP/verification codes, fixed categories, allowlisted provider error types and a sanitized request ID. The pipeline also rejects metadata that echoes the key. The UI now shows the category and safe details instead of discarding them. No retry was added.

## Endpoint/model check

No endpoint, version or model change was indicated by the network evidence. These settings match current official documentation:

- Direct origin and Models/Token Counting endpoints: [API overview](https://platform.claude.com/docs/en/api/overview).
- API version `2026-10-21`: [versioning](https://platform.claude.com/docs/en/api/versioning).
- `claude-sonnet-5-5`: [model page](https://platform.claude.com/docs/en/models/sonnet-5-5/overview).
- Error categories and HTTP 400 spend-limit ambiguity: [official errors](https://platform.claude.com/docs/en/api/errors).
- Verifying CA context behavior: [Python ssl documentation](https://docs.python.org/3.12/library/ssl.html#ssl.create_default_context).

## Verification and limits

- `connection-fix-tests.txt`: **22 adapter/diagnostic tests passed**, all model/API responses are test doubles.
- `connection-fix-pipeline-tests.txt`: **19 existing AI pipeline tests passed**.
- `connection-fix-http-tests.txt`: **8 ephemeral-server HTTP tests passed**, including safe preflight metadata and absence of generation in the diagnostic case.
- `git diff --check` passed. No evaluated MessagePack code, SDK/dependency setting, commit or push was changed.

Still unknown: validity of the user's credential, workspace/model permissions, available credits, real token count and account-specific API acceptance. The test-process CA finding has not been read from the user's live server process; another interpreter or explicit CA override can differ. Safe post-restart diagnostics expose such differences without reading or printing environment values.

## Restart and perform only the token preflight

In the terminal running the existing demo, press **Ctrl-C**, then:

```sh
cd /Users/os/junction26-messagepack-csharp
python3 trust-demo/start_claude.py
```

Enter the key only at the hidden prompt. Open http://127.0.0.1:2283/, refresh, choose an evidence run, and press **Check tokens & cost (no generation)**. Do **not** press Run AI review for this diagnostic task. If the preflight still fails, the visible error category, numeric codes and request ID can be shared; do not share a key or headers.
