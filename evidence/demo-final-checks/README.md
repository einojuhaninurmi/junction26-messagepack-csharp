# Final demo verification before local commit

Run from the repository root on 2026-11-15. All listed commands exited 0. Logs accompany this file. No new model generation or MessagePack test collection was performed. Provider behavior in automated tests is explicitly simulated.

```sh
python3 trust-demo/test_report.py
python3 trust-demo/test_collector.py
python3 trust-demo/test_ai.py
python3 trust-demo/test_anthropic.py
python3 trust-demo/test_ai_http.py
env -u TRUST_REVIEW_API_KEY -u TRUST_REVIEW_PROVIDER -u TRUST_REVIEW_MODEL python3 trust-demo/server.py --port 2284
TRUST_DEMO_TEST_URL=http://127.0.0.1:2284 python3 trust-demo/test_chrome.py --design-checks --collector-checks --ai-checks --anthropic-checks
```

The last command uses the isolated server above; it does not use the user's live keyed server. The summary records exact decision/review/run/SHA matching and unchanged genuine input/instruction hashes. Browser tests verify storage, restoration, JSON export, evidence links, review/SHA decision binding and failure states. Existing historical MessagePack results are separate evidence, not rerun results from this step.
