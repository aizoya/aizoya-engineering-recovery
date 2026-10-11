/**
 * Dashboard — port of the Python harness render() function.
 *
 * Fetches /api/mission (server-side Atlas read) and renders:
 *  - Mission status & revision
 *  - Recovery timeline (Human-assisted recovery)
 *  - Session cards with retrieved evidence and decisions
 *  - Verification attempt cards with check-by-check results
 *  - Unicode failure evidence (U+2028 shown as \u2028)
 *  - Technology view
 *  - Metrics
 *
 * Read-only. No writes, no candidate execution.
 */
import { useEffect, useState } from 'react';
import type { MissionDoc, Attempt, Session, CheckResult } from '../types';
import {
  fmtDate,
  checksLabel,
  failedNames,
  jsonShowUnicode,
} from '../utils';
import { statusChip, Chip } from '../components/Chip';
import {
  Card,
  Row,
  Section,
  SectionHeading,
  SubHeading,
  Disclosure,
  CodeBlock,
} from '../components/Card';

// ── data fetching ────────────────────────────────────────────────────────────

async function fetchMission(): Promise<MissionDoc> {
  const res = await fetch('/api/mission');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const body = (await res.json()) as { doc?: MissionDoc; error?: string };
  if (body.error || !body.doc) throw new Error(body.error ?? 'no_doc');
  return body.doc;
}

// ── sub-components ───────────────────────────────────────────────────────────

function CheckTable({ check }: { check: CheckResult }) {
  return (
    <div className="my-2">
      <SubHeading>
        Failed check:{' '}
        <span className="text-red-400 font-mono">{check.name}</span>
      </SubHeading>
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-slate-950">
              <th className="text-left px-2 py-1.5 text-cyan-400 font-semibold">Field</th>
              <th className="text-left px-2 py-1.5 text-emerald-400 font-semibold">Expected</th>
              <th className="text-left px-2 py-1.5 text-red-400 font-semibold">Observed</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-t border-slate-800">
              <td className="px-2 py-1 align-top text-slate-300">records</td>
              <td className="px-2 py-1 align-top">
                <Disclosure summary="expand">
                  <CodeBlock>
                    {jsonShowUnicode(
                      (check.expected as Record<string, unknown>)?.['records'] ?? check.expected,
                      2
                    )}
                  </CodeBlock>
                </Disclosure>
              </td>
              <td className="px-2 py-1 align-top">
                <Disclosure summary="expand">
                  <CodeBlock>
                    {jsonShowUnicode(
                      (check.observed as Record<string, unknown>)?.['records'] ?? check.observed,
                      2
                    )}
                  </CodeBlock>
                </Disclosure>
              </td>
            </tr>
            <tr className="border-t border-slate-800">
              <td className="px-2 py-1 align-top text-slate-300">errors</td>
              <td className="px-2 py-1 text-emerald-300 font-mono">
                {jsonShowUnicode((check.expected as Record<string, unknown>)?.['errors'] ?? '—')}
              </td>
              <td className="px-2 py-1 text-red-300 font-mono">
                {jsonShowUnicode((check.observed as Record<string, unknown>)?.['errors'] ?? '—')}
              </td>
            </tr>
            <tr className="border-t border-slate-800">
              <td className="px-2 py-1 align-top text-slate-300">duplicates</td>
              <td className="px-2 py-1 text-emerald-300 font-mono">
                {String((check.expected as Record<string, unknown>)?.['duplicates'] ?? '—')}
              </td>
              <td className="px-2 py-1 text-red-300 font-mono">
                {String((check.observed as Record<string, unknown>)?.['duplicates'] ?? '—')}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AttemptCard({ attempt, index }: { attempt: Attempt; index: number }) {
  const passed = attempt.result.passed;
  const failed = failedNames(attempt.result.checks);
  return (
    <Card variant={passed ? 'pass' : 'fail'}>
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <span className="text-slate-300 font-semibold text-sm">
          Attempt {index + 1}
        </span>
        {statusChip(passed ? 'VERIFIED' : 'FAILED')}
        <span className="text-slate-400 text-sm">
          {checksLabel(attempt.result.checks)}
        </span>
      </div>

      <Row label="Session">{attempt.session_id}</Row>
      <Row label="Recorded">{fmtDate(attempt.recorded_at)}</Row>
      <Row label="Elapsed">
        {attempt.result.elapsed_ms != null ? `${attempt.result.elapsed_ms} ms` : '—'}
      </Row>
      <Row label="Harness calls">{String(attempt.harness_tool_calls)}</Row>
      <Row label="Candidate">
        <span className="text-xs">{attempt.result.candidate_hash}</span>
      </Row>

      {failed.length > 0 && (
        <Row label="Failed">
          <span className="text-red-400">{failed.join(', ')}</span>
        </Row>
      )}

      {attempt.result.failure != null && (
        <Row label="Execution error">
          <span className="text-red-400">{String(attempt.result.failure)}</span>
        </Row>
      )}

      {attempt.result.checks.length > 0 && (
        <div className="mt-3">
          <SubHeading>Checks</SubHeading>
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="bg-slate-950">
                  <th className="text-left px-2 py-1.5 text-cyan-400">Check</th>
                  <th className="text-left px-2 py-1.5 text-cyan-400">Result</th>
                </tr>
              </thead>
              <tbody>
                {attempt.result.checks.map(c => (
                  <tr
                    key={c.name}
                    className={`border-t border-slate-800 ${c.passed ? 'text-emerald-300' : 'text-red-400 font-semibold'}`}
                  >
                    <td className="px-2 py-1 font-mono">{c.name}</td>
                    <td className="px-2 py-1">{c.passed ? '✓ pass' : '✗ fail'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {attempt.result.checks.filter(c => !c.passed).map(c => (
        <CheckTable key={c.name} check={c} />
      ))}

      <Disclosure summary="Full attempt JSON">
        <CodeBlock>
          {jsonShowUnicode(
            {
              id: attempt.id,
              session_id: attempt.session_id,
              recorded_at: attempt.recorded_at,
              harness_tool_calls: attempt.harness_tool_calls,
              result: {
                passed: attempt.result.passed,
                elapsed_ms: attempt.result.elapsed_ms,
                failure: attempt.result.failure,
                candidate_hash: attempt.result.candidate_hash,
                verifier_hash: attempt.result.verifier_hash,
                checks: attempt.result.checks,
              },
            },
            2
          )}
        </CodeBlock>
      </Disclosure>
    </Card>
  );
}

function SessionCard({ session, index }: { session: Session; index: number }) {
  const ended = !!session.ended_at;
  const evidence = session.context.retrieved_evidence ?? [];
  const decisions = session.decisions ?? [];

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <span className="text-slate-300 font-semibold text-sm">
          Session {index + 1}
        </span>
        <Chip label={ended ? 'ENDED' : 'OPEN'} variant={ended ? 'ended' : 'open'} />
        <span className="font-mono text-xs text-slate-400">{session.id}</span>
      </div>

      <Row label="Started">{fmtDate(session.started_at)}</Row>
      {ended && <Row label="Ended">{fmtDate(session.ended_at)}</Row>}
      <Row label="Plan">
        <span className="font-sans break-words">{session.context.plan ?? '—'}</span>
      </Row>

      {evidence.length > 0 ? (
        <div className="mt-3">
          <SubHeading>
            Evidence retrieved from Atlas ({evidence.length} prior failure
            {evidence.length !== 1 ? 's' : ''})
          </SubHeading>
          {evidence.map((ev, i) => (
            <Card key={i} variant="fail">
              <Row label="Attempt">
                <span className="text-xs">{ev.attempt_id.slice(0, 16)}…</span>
              </Row>
              <Row label="Candidate">
                <span className="text-xs">{(ev.candidate_hash ?? '').slice(0, 16)}…</span>
              </Row>
              <Row label="Failed checks">
                <span className="text-red-400">
                  {(ev.failed_checks ?? []).join(', ') || 'none'}
                </span>
              </Row>
              {(ev.check_evidence ?? []).map(ce => (
                <CheckTable key={ce.name} check={ce} />
              ))}
            </Card>
          ))}
        </div>
      ) : (
        <p className="text-slate-500 text-xs mt-2">
          No prior failure evidence retrieved (first session or memory disabled).
        </p>
      )}

      {decisions.length > 0 && (
        <div className="mt-3">
          <SubHeading>Plan decisions recorded ({decisions.length})</SubHeading>
          {decisions.map((dec, i) => (
            <Card key={i}>
              <Row label="Recorded">{fmtDate(dec.recorded_at)}</Row>
              <Row label="Decision">
                <span className="font-sans break-words">{dec.decision}</span>
              </Row>
              <Row label="Source attempts">
                <span className="text-xs">
                  {(dec.source_attempts ?? [])
                    .map(id => id.slice(0, 16) + '…')
                    .join(', ') || 'none'}
                </span>
              </Row>
            </Card>
          ))}
        </div>
      )}
    </Card>
  );
}

function Timeline({ doc }: { doc: MissionDoc }) {
  type Event =
    | { ts: string; kind: 'session-start'; obj: Session }
    | { ts: string; kind: 'session-end'; obj: Session }
    | { ts: string; kind: 'attempt'; obj: Attempt };

  const events: Event[] = [];
  for (const s of doc.sessions) {
    events.push({ ts: s.started_at, kind: 'session-start', obj: s });
    if (s.ended_at) events.push({ ts: s.ended_at, kind: 'session-end', obj: s });
  }
  for (const a of doc.attempts) {
    events.push({ ts: a.recorded_at, kind: 'attempt', obj: a });
  }
  events.sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0));

  if (events.length === 0) {
    return (
      <p className="text-slate-500 text-sm">No sessions or attempts recorded yet.</p>
    );
  }

  return (
    <ol className="list-decimal list-inside space-y-3 pl-0">
      {events.map((ev, i) => {
        if (ev.kind === 'session-start') {
          const s = ev.obj as Session;
          const ended = !!s.ended_at;
          const mem = (s.context.retrieved_evidence ?? []).length;
          return (
            <li key={i} className="text-sm leading-relaxed">
              <span className="text-cyan-400 font-semibold">Session started</span>
              {' · '}
              {fmtDate(s.started_at)}
              {' · '}
              <span className="font-mono text-xs text-slate-400">{s.id}</span>
              {' '}
              <Chip label={ended ? 'ended' : 'open'} variant={ended ? 'ended' : 'open'} />
              <div className="ml-4 text-slate-500 text-xs mt-0.5">
                Plan: {s.context.plan ?? '—'}
              </div>
              {mem > 0 && (
                <div className="ml-4 text-amber-400 text-xs">
                  {mem} prior failure{mem !== 1 ? 's' : ''} retrieved from Atlas
                </div>
              )}
            </li>
          );
        } else if (ev.kind === 'session-end') {
          const s = ev.obj as Session;
          return (
            <li key={i} className="text-sm leading-relaxed">
              <span className="text-cyan-400 font-semibold">Session ended</span>
              {' · '}
              {fmtDate(s.ended_at)}
              {' · '}
              <span className="font-mono text-xs text-slate-400">{s.id}</span>
            </li>
          );
        } else {
          const a = ev.obj as Attempt;
          const passed = a.result.passed;
          const failed = failedNames(a.result.checks);
          return (
            <li key={i} className="text-sm leading-relaxed">
              <span className="text-cyan-400 font-semibold">Verification attempt</span>
              {' · '}
              {fmtDate(a.recorded_at)}
              {' · '}
              {statusChip(passed ? 'VERIFIED' : 'FAILED')}
              {' · '}
              {checksLabel(a.result.checks)}
              {' · '}
              {a.result.elapsed_ms != null ? `${a.result.elapsed_ms} ms` : '—'}
              {' · '}
              <span className="font-mono text-xs text-slate-500">
                {(a.result.candidate_hash ?? '').slice(0, 16)}…
              </span>
              {failed.length > 0 && (
                <div className="ml-4 text-red-400 text-xs mt-0.5">
                  Failed: {failed.join(', ')}
                </div>
              )}
            </li>
          );
        }
      })}
    </ol>
  );
}

function TechView() {
  const rows = [
    {
      component: 'Python harness (harness.py)',
      role: 'Engineering workflow — init, resume, verify, serve commands. Writes to Atlas. Runs on operator machine only.',
      public: false,
    },
    {
      component: 'Python verifier (verifier.py)',
      role: 'Independent check engine. Sandboxed subprocess execution. Produces check results stored in Atlas.',
      public: false,
    },
    {
      component: 'Python candidate (candidate.py)',
      role: 'The import_transactions() implementation under evaluation. Never executed by this presenter.',
      public: false,
    },
    {
      component: 'MongoDB Atlas (organizer sandbox)',
      role: 'Single source of truth. Stores mission, sessions, attempts, evidence, lessons. All reads go through the Node.js server; credentials never reach the browser.',
      public: false,
    },
    {
      component: 'Node.js server (Modelence module)',
      role: 'Read-only presenter. Reads one document from Atlas (transaction-import mission). Exposes GET /api/mission. No writes.',
      public: false,
    },
    {
      component: 'React dashboard (this page)',
      role: 'Presents live Atlas evidence. Fetches from /api/mission. No Atlas credentials, no write operations, no candidate execution.',
      public: true,
    },
    {
      component: 'Human-assisted recovery',
      role: 'Session-2 recovery: operator retrieved Atlas failure evidence, supplied it to Kiro in a new conversation. No autonomous model API loop was demonstrated.',
      public: true,
    },
  ];

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="bg-slate-950">
            <th className="text-left px-3 py-2 text-cyan-400">Component</th>
            <th className="text-left px-3 py-2 text-cyan-400">Actual role</th>
            <th className="text-left px-3 py-2 text-cyan-400">Browser-exposed</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.component} className="border-t border-slate-800 align-top">
              <td className="px-3 py-2 font-mono text-slate-300 whitespace-nowrap">
                {r.component}
              </td>
              <td className="px-3 py-2 text-slate-400 leading-relaxed">{r.role}</td>
              <td className="px-3 py-2">
                {r.public ? (
                  <Chip label="yes" variant="open" />
                ) : (
                  <Chip label="no"  variant="ended" />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [doc, setDoc] = useState<MissionDoc | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMission()
      .then(d => { setDoc(d); setLoading(false); })
      .catch(e => { setError(String(e?.message ?? e)); setLoading(false); });
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-slate-400 text-sm">
        Reading from Atlas…
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-red-400 text-sm max-w-md text-center">
          <p className="font-semibold mb-2">Atlas read failed</p>
          <p className="text-slate-500">{error}</p>
          <p className="text-slate-600 text-xs mt-3">
            Check that MONGODB_URI is set in the Modelence environment and the
            organizer sandbox allows this host.
          </p>
        </div>
      </div>
    );
  }

  // Derived metrics (matches Python metrics() function)
  const counts: Record<string, number> = {};
  for (const a of doc.attempts) {
    for (const c of a.result.checks) {
      if (!c.passed) counts[c.name] = (counts[c.name] ?? 0) + 1;
    }
  }
  const totalMs   = doc.attempts.reduce((s, a) => s + (a.result.elapsed_ms ?? 0), 0);
  const totalCalls = doc.attempts.reduce((s, a) => s + (a.harness_tool_calls ?? 0), 0);
  const failedAttempts = doc.attempts.filter(a => !a.result.passed).length;
  const repeatedFailed = Object.values(counts).reduce((s, n) => s + Math.max(0, n - 1), 0);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">

        {/* ── header ───────────────────────────────────────────────── */}
        <p className="text-slate-500 text-xs mb-1">
          AIZOYA · Original hackathon prototype · Live Atlas readback · Fictional task data
        </p>
        <h1 className="text-3xl sm:text-4xl font-bold mb-1">
          Engineering that remembers
        </h1>
        <p className="text-slate-400 text-sm mb-6">
          {doc._id} · {doc.status} · revision {doc.revision} ·{' '}
          {doc.attempts.length} attempt(s) · {doc.sessions.length} session(s)
        </p>

        {/* ── mission status ────────────────────────────────────────── */}
        <Section>
          <SectionHeading>Mission status</SectionHeading>
          <Row label="Status">{statusChip(doc.status)}</Row>
          <Row label="Mission"><span className="font-mono">{doc._id}</span></Row>
          <Row label="Revision">{String(doc.revision)}</Row>
          <Row label="Created">{fmtDate(doc.created_at)}</Row>
          <Row label="Goal">
            <span className="font-sans break-words">{doc.goal}</span>
          </Row>
        </Section>

        {/* ── recovery timeline ─────────────────────────────────────── */}
        <Section>
          <SectionHeading>
            Recovery timeline ·{' '}
            <span className="text-amber-400 normal-case">Human-assisted recovery</span>
          </SectionHeading>
          <Timeline doc={doc} />
          <p className="text-slate-500 text-xs mt-4">
            Human-assisted recovery: the operator retrieved failure evidence from
            Atlas and supplied it to the coding assistant in a new session. No
            autonomous model API loop was demonstrated. Model tool-call counts
            and conversation freshness are not instrumented.
          </p>
        </Section>

        {/* ── sessions ─────────────────────────────────────────────── */}
        <Section>
          <SectionHeading>Sessions</SectionHeading>
          {doc.sessions.length === 0 ? (
            <p className="text-slate-500 text-sm">No sessions recorded yet.</p>
          ) : (
            doc.sessions.map((s, i) => (
              <SessionCard key={s.id} session={s} index={i} />
            ))
          )}
        </Section>

        {/* ── verification attempts ────────────────────────────────── */}
        <Section>
          <SectionHeading>Independent verification attempts</SectionHeading>
          {doc.attempts.length === 0 ? (
            <p className="text-slate-500 text-sm">No verification attempts recorded yet.</p>
          ) : (
            doc.attempts.map((a, i) => (
              <AttemptCard key={a.id} attempt={a} index={i} />
            ))
          )}
        </Section>

        {/* ── metrics ──────────────────────────────────────────────── */}
        <Section>
          <SectionHeading>Measured progress</SectionHeading>
          <Row label="Attempts">{String(doc.attempts.length)}</Row>
          <Row label="Sessions">{String(doc.sessions.length)}</Row>
          <Row label="Task verified">{doc.status === 'VERIFIED' ? 'Yes' : 'No'}</Row>
          <Row label="Failed attempts">{String(failedAttempts)}</Row>
          <Row label="Repeated failed checks">{String(repeatedFailed)}</Row>
          <Row label="Total verifier time">{totalMs > 0 ? `${totalMs} ms` : '—'}</Row>
          <Row label="Harness calls">{String(totalCalls)}</Row>
          <Row label="Model tool calls">not instrumented</Row>
          <Row label="Model session freshness">not instrumented</Row>
        </Section>

        {/* ── technology view ──────────────────────────────────────── */}
        <Section>
          <SectionHeading>Technology view</SectionHeading>
          <TechView />
        </Section>

        {/* ── full document ─────────────────────────────────────────── */}
        <Section>
          <Disclosure summary="Full Atlas document (JSON)">
            <CodeBlock>{jsonShowUnicode(doc, 2)}</CodeBlock>
          </Disclosure>
        </Section>

        <p className="text-slate-600 text-xs text-center mt-6 pb-4">
          No automatic publication, deployment or external submission. Atlas is
          the only persistence backend. Presented on Modelence Cloud.
        </p>
      </div>
    </div>
  );
}
