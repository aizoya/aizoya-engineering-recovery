# AIZOYA engineering recovery harness

Original event implementation begun October 11, 2026 after founder reported hacking started. No Grant-App, AWS or other project implementation reused. Track: Long Horizon Engineering. Internal build; not published or submitted.

## One task and acceptance contract

Implement `import_transactions(text)` in Python: convert fictional JSONL orders into
`{"records": [{"id": str, "amount_cents": int}], "errors": [1-based line numbers], "duplicates": int}`.
Ignore blank lines. Every nonblank line must contain a JSON object with a nonempty trimmed string `id` (max 80 characters) and `amount` as a string of nonnegative decimal dollars, up to two fractional digits, max 1,000,000.00. Trim amount whitespace. Reject exponents, NaN, Infinity, booleans, numeric amounts, signs, missing fields and malformed JSON. Keep the first valid occurrence of each normalized ID, in input order. Later valid repeats count as duplicates. Invalid rows remain errors even when their ID repeats. Return exact integer cents. Extra fields are ignored.

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

## Real demonstration requirements

Do not create a deliberately broken candidate. Let the assistant honestly attempt
the task. If it fails independent verification, preserve that actual outcome,
terminate the session, restore in a fresh process/conversation, use the evidence
to revise, and verify again. If it passes immediately, report that outcome; do not
manufacture a failure. Record elapsed verifier time and check count. Tool calls
inside Kiro/Codex are unknown unless instrumented independently.

## Readiness gates

Atlas Sandbox access BLOCKED: signed-in hello account has only personal org;
Invitations page shows no invitations (October 11, about 10:50 AM Pacific).
Atlas round trip NOT RUN. Fresh-session Atlas recovery NOT RUN.
Codex's first candidate was actually run: initial 9 checks passed, then an expanded
JSONL edge-case check found a real Unicode line separator defect; 9/10 checks pass.
The candidate remains unchanged for recovery. This is observed local evidence,
not evidence of an Atlas-backed run. Accessible public demo NOT READY.
Actual submission form fields NOT VERIFIED (cloud browser signed out).
License requirement NOT VERIFIED; no license selection or repository publication
has occurred. Sponsor offers/coverage need event-specific confirmation. No spend.

Founder: Franklyn Rosario, MBA-ITM, Founder & CEO of AIZOYA.
