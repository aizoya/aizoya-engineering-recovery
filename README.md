# AIZOYA engineering recovery harness

Original event implementation begun October 11, 2026 after founder reported hacking started. No Grant-App, AWS or other project implementation reused. Track: Long Horizon Engineering. Internal build; not published or submitted.

## One task and acceptance contract

Implement `import_transactions(text)` in Python: convert fictional JSONL orders into
`{"records": [{"id": str, "amount_cents": int}], "errors": [1-based line numbers], "duplicates": int}`.
Records are separated by physical LF characters (`\n`). Ignore blank lines. Every nonblank line must contain a JSON object with a nonempty trimmed string `id` (max 80 characters) and `amount` as a string of nonnegative decimal dollars, up to two fractional digits, max 1,000,000.00. Trim amount whitespace. Reject exponents, NaN, Infinity, booleans, numeric amounts, signs, missing fields and malformed JSON. Keep the first valid occurrence of each normalized ID, in input order. Later valid repeats count as duplicates. Invalid rows remain errors even when their ID repeats. Return exact integer cents. Extra fields are ignored.

Independent verifier checks boundaries and 100 seeded generated rows, exact values,
order, duplicate behavior and invalid-row reporting. Verification is a bounded local
code execution, not proof of general safety, arbitrary engineering competence or
long-term autonomous operation.

## Components

- Atlas is the only application persistence backend. No SQLite/file-memory fallback.
- Single mission document, optimistic revision check, atomic attempt + lesson write.
- `resume` starts a genuinely fresh Python process/session and reconstructs a prompt
  from the persisted goal, recent attempts, evidence and lessons. A failure changes
  the plan to inspect failing constraints before writing another candidate.
- A coding assistant (Codex or Kiro) produces the candidate. The harness does **not**
  pretend to contain a model when no model is connected. Current mode is an
  assistant-driven harness: read recovered context, write candidate, verify.
- Local read-only UI shows goal, history, evidence, plan changes and checks.
- No submit/deploy endpoint; no Atlas Agent Engine dependency.

## Setup in assigned organizer sandbox only

Python 3.11+, `python3 -m venv .venv`, then `.venv/bin/pip install -r requirements.txt`.
Set `MONGODB_URI` privately in your local environment. Never place it in chat,
source, shell history, screenshots or recordings. Set `MONGODB_DATABASE` to the
assigned project database and `SANDBOX_CONFIRMED=YES` only after verifying the
host belongs to the organizer sandbox and charges are covered. This acknowledgement
is an operator declaration, not independent proof of sponsor coverage.

Use a project-scoped database user and only permitted network access. Do not widen
access to 0.0.0.0/0. Do not run Atlas provisioning scripts.

```
.venv/bin/python harness.py init --mission importer
.venv/bin/python harness.py resume --mission importer
# Feed recovered context to your coding assistant; it writes candidate.py.
.venv/bin/python harness.py verify --mission importer --session SESSION_ID --candidate candidate.py
# End this session/process. New terminal or fresh Kiro conversation:
.venv/bin/python harness.py resume --mission importer
.venv/bin/python harness.py serve --mission importer
```

`resume` prints context and a session ID. No credentials are printed. `serve` binds
127.0.0.1:8765, read-only. Public demo URL requires separate deployment review.
Run `python3 -m unittest discover -s tests -v` for offline harness checks. These
checks do not establish Atlas connectivity or actual assistant recovery.

Use `.venv/bin/python private_run.py` in place of `harness.py` to enter your
assigned URI through a hidden terminal prompt without shell history or a saved
credential file. Re-enter it for each process. This wrapper never saves secrets.
To explicitly close a session: `private_run.py end --mission importer --session SESSION_ID`.
Then exit the old assistant conversation and start a new conversation. Merely
starting another Python process does not prove a fresh model conversation.
Persist the assistant's actual decision with `private_run.py plan --mission importer
--session SESSION_ID --decision "ACTUAL PLAN"`. Decisions reference the evidence
retrieved for that session. The UI reports measured verification calls/time and
repeated failures; model session freshness and model tool calls are not instrumented.

## Real demonstration requirements

Do not create a deliberately broken candidate. Let the assistant honestly attempt
the task. If it fails independent verification, preserve that actual outcome,
terminate the session, restore in a fresh process/conversation, use the evidence
to revise, and verify again. If it passes immediately, report that outcome; do not
manufacture a failure. Record elapsed verifier time and check count. Tool calls
inside Kiro/Codex are unknown unless instrumented independently.

## Observed recovery — October 11, 2026

This section records actual outcomes as they occurred. It replaces prior
"NOT RUN" / "BLOCKED" claims in the readiness gates below.

**Session-1 (first candidate):**
Codex produced the original candidate, which was verified in session-1. The initial 9-check suite passed.
An independent expanded check added a valid JSON string containing a Unicode line
separator (U+2028). The `unicode_inside_json_string` check failed: the candidate
used `text.splitlines()` which split on U+2028, breaking a single valid record into
two lines. 9/10 checks passed. Session-1 ended and its process was closed.

Original candidate SHA256:
`71fd7fc2417b96d06718c2fc7d80a1b55213ad1be9c3ecab9da5d0fc1f154a03`

**Session-2 (human-assisted Atlas recovery):**
The operator connected to the organizer Atlas sandbox and ran `private_run.py resume`
in a new Python process. The persisted failure evidence was read back from Atlas
and supplied to Kiro as operator-provided context — this is human-assisted recovery,
not an autonomous model API loop. Kiro inspected the failure, identified that
`text.splitlines()` treats U+2028 as a line terminator while `text.split('\n')`
does not, and replaced the call in `candidate.py`. The mission is `transaction-import`.

Repaired candidate SHA256:
`592b1b2854b360663fd708457d66a594ccfe3d808f28c22651f4b9913058f56a`

Session-2 ran one harness verification call. The expanded verifier passed 10/10
independent checks in 87 ms. Atlas readback reports VERIFIED at revision 6.
All 16 unit tests passed on macOS; the Linux-only `RLIMIT_AS` address-space limit
does not apply on macOS. The local read-only viewer was observed working at
`http://127.0.0.1:8765`. Code fixes were committed as `6eb8669`.

**What was and was not demonstrated:**
- Atlas sandbox connection: confirmed (organizer sandbox, not personal cluster).
- Persisted failure evidence read back across a process boundary: confirmed.
- Repair informed by retrieved evidence: confirmed.
- 10/10 independent checks and Atlas VERIFIED at revision 6: confirmed.
- Autonomous model API loop with no human relay: NOT demonstrated.
- Memory-disabled model comparison benchmark: NOT demonstrated.
- Model tool-call counts: not instrumented; unknown.
- Model conversation freshness (stateless vs. stateful): not independently verified.

## Readiness gates (updated October 11, 2026)

Atlas sandbox connection: CONFIRMED — organizer sandbox, October 11.
Mission: `transaction-import`. Atlas revision 6, status VERIFIED.
Fresh-session Atlas recovery (human-assisted): CONFIRMED.
10/10 independent checks: CONFIRMED. Verification: 87 ms, one call.
All 16 local unit tests: PASS (macOS; Linux RLIMIT_AS excluded by design).
Code committed: `6eb8669`. Credential-pattern scan of Git history: zero matches
(not a comprehensive security guarantee).
Local viewer at http://127.0.0.1:8765: OBSERVED WORKING.

Accessible public demo: NOT READY (local 127.0.0.1 is not a public URL).
Public repository: NOT PUBLISHED.
Video recording: NOT RECORDED.
Final submission: NOT MADE.
Modelence integration: NOT IMPLEMENTED.
License requirement: NOT VERIFIED; no license selected.
Sponsor credit discrepancy: UNRESOLVED.

Founder: Franklyn Rosario, MBA-ITM, Founder & CEO of AIZOYA.
