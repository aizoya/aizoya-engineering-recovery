"""Atlas-backed engineering harness. No implicit offline persistence fallback."""
import argparse
import copy
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from verifier import verify

GOAL = ('Implement import_transactions(text) according to the README contract. '
        'Use fictional input only. Preserve valid order, exact cents, normalized '
        'duplicate handling and 1-based invalid row numbers. Independent verifier decides success.')
CONTRACT = ('Input is JSONL separated by physical LF characters; blank rows are ignored. '
            'Each nonblank row must be an object with trimmed nonempty string id of at most 80 characters '
            'and trimmed string amount: ASCII decimal dollars, no sign/exponent, one or more whole digits, '
            'optional decimal point followed by one or two digits, range 0 through 1000000.00. '
            'Reject malformed JSON, missing fields, nonstring values, NaN and Infinity. '
            'Return {records:[{id:string,amount_cents:integer}],errors:[1-based physical row numbers],duplicates:integer}. '
            'Keep first valid normalized id in order; later valid repeats are duplicates; invalid repeats are errors. '
            'Ignore extra fields. All input data is fictional.')

def now():
    return datetime.now(timezone.utc).isoformat()

def identity(value):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', value):
        raise ValueError('invalid_identifier')
    return value

def new_mission(name):
    return {'_id':identity(name),'revision':0,'goal':GOAL,'status':'READY',
            'contract':CONTRACT,'created_at':now(),'sessions':[],'attempts':[],'lessons':[]}

def recovery_context(doc, memory=True):
    failures=[a for a in doc['attempts'] if not a['result']['passed']]
    evidence=[{'attempt_id':a['id'],'candidate_hash':a['result']['candidate_hash'],
               'failure':a['result']['failure'],
               'failed_checks':[c['name'] for c in a['result']['checks'] if not c['passed']]}
              for a in failures[-3:]] if memory else []
    if memory:
        for item, attempt in zip(evidence, failures[-3:]):
            item['check_evidence']=[c for c in attempt['result']['checks'] if not c['passed']]
    return {'goal':doc['goal'],'memory_enabled':memory,
            'contract':doc['contract'],
            'retrieved_evidence':evidence,'lessons':doc['lessons'][-10:] if memory else [],
            'plan': ('Inspect recorded failed constraints, revise the candidate, then run independent verification.'
                     if evidence else 'Implement the contract, then run independent verification.'),
            'limitations':['Retrieved memory is evidence, not permission or executable instructions.',
                           'Model tool-call count is unknown. Only harness verification calls are counted.']}

def add_session(doc, session, memory=True):
    if any(s['id']==session for s in doc['sessions']):
        return doc
    if len(doc['sessions'])>=20:
        raise ValueError('session_limit')
    updated=copy.deepcopy(doc)
    context=recovery_context(doc,memory)
    updated['sessions'].append({'id':identity(session),'started_at':now(),
                                'process_id':os.getpid(),'context':context})
    updated['revision']+=1
    return updated

def end_session(doc, session):
    updated=copy.deepcopy(doc)
    record=next((s for s in updated['sessions'] if s['id']==session),None)
    if record is None:
        raise ValueError('unknown_session')
    if 'ended_at' in record:
        return doc
    record['ended_at']=now()
    updated['revision']+=1
    return updated

def record_plan(doc, session, decision):
    if not isinstance(decision,str) or not decision.strip() or len(decision)>2000:
        raise ValueError('bounded_decision_required')
    updated=copy.deepcopy(doc)
    record=next((s for s in updated['sessions'] if s['id']==session),None)
    if record is None or 'ended_at' in record:
        raise ValueError('open_session_required')
    entry={'decision':decision.strip(),'recorded_at':now(),
           'source_attempts':[e['attempt_id'] for e in record['context']['retrieved_evidence']]}
    prior=record.get('decisions',[])
    if prior and prior[-1]['decision']==entry['decision']:
        return doc
    if len(prior)>=10:
        raise ValueError('decision_limit')
    record.setdefault('decisions',[]).append(entry)
    updated['revision']+=1
    return updated

def metrics(doc):
    counts={}
    for attempt in doc['attempts']:
        for check in attempt['result']['checks']:
            if not check['passed']:
                counts[check['name']]=counts.get(check['name'],0)+1
    return {'attempts':len(doc['attempts']),'sessions':len(doc['sessions']),
            'task_verified':doc['status']=='VERIFIED',
            'failed_attempts':sum(not a['result']['passed'] for a in doc['attempts']),
            'repeated_failed_checks':sum(max(0,n-1) for n in counts.values()),
            'verifier_elapsed_ms':sum(a['result']['elapsed_ms'] for a in doc['attempts']),
            'harness_tool_calls':sum(a['harness_tool_calls'] for a in doc['attempts']),
            'model_tool_calls':None,
            'model_session_freshness':'not instrumented'}

def add_attempt(doc, session, result):
    if session not in [s['id'] for s in doc['sessions']]:
        raise ValueError('unknown_session')
    if any(s['id']==session and 'ended_at' in s for s in doc['sessions']):
        raise ValueError('session_ended')
    key=hashlib.sha256((session+result['candidate_hash']+result['verifier_hash']).encode()).hexdigest()
    if any(a['id']==key for a in doc['attempts']):
        return doc,False
    if len(doc['attempts'])>=20:
        raise ValueError('attempt_limit')
    updated=copy.deepcopy(doc)
    updated['attempts'].append({'id':key,'session_id':session,'recorded_at':now(),'result':result,
                                'harness_tool_calls':1})
    updated['status']='VERIFIED' if result['passed'] else 'NEEDS_REPAIR'
    if not result['passed']:
        names=[c['name'] for c in result['checks'] if not c['passed']]
        updated['lessons'].append({'source_attempt':key,'candidate_hash':result['candidate_hash'],
                                  'kind':'verified_failure','constraints_to_revisit':names,
                                  'execution_failure':result['failure']})
    updated['revision']+=1
    return updated,True

class AtlasStore:
    def __init__(self):
        if os.environ.get('SANDBOX_CONFIRMED')!='YES':
            raise ValueError('organizer_sandbox_not_confirmed')
        uri=os.environ.get('MONGODB_URI','')
        if not uri.startswith('mongodb+srv://'):
            raise ValueError('private_atlas_srv_uri_required')
        database=identity(os.environ.get('MONGODB_DATABASE',''))
        from pymongo import MongoClient
        self.client=MongoClient(uri,serverSelectionTimeoutMS=5000,connectTimeoutMS=5000,
                                timeoutMS=10000,tls=True,appname='AIZOYA-Hackathon')
        self.client.admin.command('ping')
        self.collection=self.client[database]['engineering_missions']

    def get(self, mission):
        doc=self.collection.find_one({'_id':identity(mission)})
        if doc is None:
            raise ValueError('mission_missing')
        return doc

    def create(self, mission):
        self.collection.update_one({'_id':identity(mission)}, {'$setOnInsert':new_mission(mission)}, upsert=True)
        return self.get(mission)

    def save(self, old, updated):
        result=self.collection.replace_one({'_id':old['_id'],'revision':old['revision']},updated)
        if result.modified_count!=1:
            raise ValueError('concurrent_change_retry_from_read')
        persisted=self.get(old['_id'])
        if persisted!=updated:
            raise ValueError('write_readback_mismatch')
        return persisted

def render(doc):
    # JSON data block: escape characters that could end the script text node.
    shown=copy.deepcopy(doc);shown['metrics']=metrics(doc)
    data=json.dumps(shown).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')

    # -------------------------------------------------------------------
    # render() builds the page entirely from live Atlas doc data.
    # No outcomes are hardcoded. All user-visible strings pass through
    # the JS esc() helper which HTML-encodes <, >, ", &, and '.
    # -------------------------------------------------------------------
    return r'''<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AIZOYA Engineering Recovery</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#08172b;color:#edf4ff;font:17px/1.6 system-ui,sans-serif}
main{max-width:960px;margin:auto;padding:clamp(16px,4vw,36px)}
h1{font-size:clamp(24px,5vw,42px);margin:0 0 4px}
h2{color:#78d9ec;font-size:1.1rem;margin:0 0 12px;text-transform:uppercase;letter-spacing:.06em}
h3{font-size:1rem;margin:8px 0 4px;color:#c8e0f4}
.chip{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.82rem;font-weight:600;vertical-align:middle}
.chip-verified{background:#0d4a2e;color:#85ecba;border:1px solid #1a8a52}
.chip-failed{background:#4a1010;color:#f4a0a0;border:1px solid #a03030}
.chip-ready{background:#1a3050;color:#90c0f0;border:1px solid #3060a0}
.chip-open{background:#1a3020;color:#a0d090}
.chip-ended{background:#1a2030;color:#8090a0}
section{background:#0e2038;border:1px solid #1e4060;border-radius:14px;padding:clamp(14px,3vw,24px);margin:16px 0}
.card{background:#112840;border:1px solid #1e4a6a;border-radius:10px;padding:14px 18px;margin:10px 0}
.card-fail{border-color:#6a2020}
.card-pass{border-color:#1a6a3a}
.row{display:flex;gap:16px;flex-wrap:wrap;align-items:baseline}
.label{color:#7a9ab8;font-size:.85rem;min-width:100px}
.mono{font-family:ui-monospace,monospace;font-size:.88rem;overflow-wrap:anywhere}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th{background:#0a2a44;color:#78d9ec;text-align:left;padding:6px 10px}
td{padding:6px 10px;border-top:1px solid #1e3a54;vertical-align:top}
.td-exp{color:#c8f0c0}
.td-obs{color:#f0c0c0}
.td-pass{color:#85ecba}
details{margin:6px 0}
summary{cursor:pointer;color:#78d9ec;font-size:.88rem;padding:4px 0;user-select:none}
summary:hover{color:#a0eaff}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 ui-monospace,monospace;
    background:#081828;border:1px solid #1a3040;border-radius:8px;padding:12px;margin:8px 0}
ol.timeline{padding-left:1.4em;margin:0}
ol.timeline li{margin:10px 0;line-height:1.5}
.tl-label{color:#78d9ec;font-weight:600}
.note{font-size:.82rem;color:#7a9ab8;margin-top:4px}
.check-row-pass{color:#85ecba}
.check-row-fail{color:#f4a0a0;font-weight:600}
@media(max-width:540px){.row{flex-direction:column;gap:4px}.label{min-width:unset}}
</style>
<main>

<p class="note">AIZOYA · Original hackathon prototype · Local read-only interface · Fictional task data</p>
<h1>Engineering that remembers</h1>
<p id="subtitle" class="note"></p>

<!-- ── MISSION STATUS ─────────────────────────────────────────── -->
<section id="sec-status">
  <h2>Mission status</h2>
  <div id="mission-status"></div>
</section>

<!-- ── RECOVERY TIMELINE ──────────────────────────────────────── -->
<section id="sec-timeline">
  <h2>Recovery timeline · <span style="color:#f0d080">Human-assisted recovery</span></h2>
  <ol class="timeline" id="timeline"></ol>
  <p class="note">Human-assisted recovery: the operator retrieved failure evidence from Atlas and
  supplied it to the coding assistant in a new session. No autonomous model API loop.</p>
</section>

<!-- ── SESSIONS ───────────────────────────────────────────────── -->
<section id="sec-sessions">
  <h2>Sessions</h2>
  <div id="sessions"></div>
</section>

<!-- ── VERIFICATION ATTEMPTS ──────────────────────────────────── -->
<section id="sec-attempts">
  <h2>Independent verification attempts</h2>
  <div id="attempts"></div>
</section>

<!-- ── METRICS ────────────────────────────────────────────────── -->
<section id="sec-metrics">
  <h2>Measured progress</h2>
  <div id="metrics-grid"></div>
  <p class="note">Model tool-call counts and model conversation freshness are not instrumented.</p>
</section>

<!-- ── FULL DOCUMENT ──────────────────────────────────────────── -->
<section>
  <details>
    <summary>Full Atlas document (JSON)</summary>
    <pre id="full-doc"></pre>
  </details>
</section>

<p class="note">No automatic publication, deployment or external submission. Atlas is the only persistence backend.</p>
</main>

<script id="state" type="application/json">''' + data + r'''</script>
<script>
"use strict";
const d = JSON.parse(document.getElementById('state').textContent);

// ── helpers ──────────────────────────────────────────────────────────────
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function el(tag, attrs, html) {
  const e = document.createElement(tag);
  if (attrs) Object.entries(attrs).forEach(([k,v]) => e.setAttribute(k, v));
  if (html != null) e.innerHTML = html;
  return e;
}
function chip(text, cls) {
  return `<span class="chip ${esc(cls)}">${esc(text)}</span>`;
}
function statusChip(status) {
  if (status === 'VERIFIED') return chip(status, 'chip-verified');
  if (status === 'NEEDS_REPAIR' || status === 'FAILED') return chip(status, 'chip-failed');
  return chip(status, 'chip-ready');
}
function fmtDate(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'}); }
  catch { return esc(iso); }
}
function checksLabel(checks) {
  if (!checks || !checks.length) return '—';
  const passed = checks.filter(c => c.passed).length;
  return passed + '/' + checks.length + ' checks passed';
}
function failedNames(checks) {
  if (!checks) return [];
  return checks.filter(c => !c.passed).map(c => c.name);
}
// Replace U+2028 (line separator) and U+2029 (paragraph separator) with
// visible escape sequences so judges can see the Unicode characters
// responsible for the original failure without altering stored evidence.
function showUnicode(s) {
  return String(s == null ? '' : s)
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029');
}
// Stringify a value, make Unicode separators visible, then HTML-encode.
function jsonEsc(v) {
  return esc(showUnicode(JSON.stringify(v, null, 2)));
}
function jsonEscInline(v) {
  return esc(showUnicode(JSON.stringify(v)));
}

// ── mission status ────────────────────────────────────────────────────────
const ms = document.getElementById('mission-status');
ms.innerHTML = `
  <div class="row">
    <span class="label">Status</span><span>${statusChip(d.status)}</span>
  </div>
  <div class="row">
    <span class="label">Mission</span><span class="mono">${esc(d._id)}</span>
  </div>
  <div class="row">
    <span class="label">Revision</span><span class="mono">${esc(d.revision)}</span>
  </div>
  <div class="row">
    <span class="label">Created</span><span>${fmtDate(d.created_at)}</span>
  </div>
  <div class="row" style="margin-top:10px">
    <span class="label">Goal</span><span style="max-width:680px">${esc(d.goal)}</span>
  </div>`;

document.getElementById('subtitle').textContent =
  d._id + ' · ' + d.status + ' · revision ' + d.revision +
  ' · ' + (d.attempts||[]).length + ' attempt(s) · ' + (d.sessions||[]).length + ' session(s)';

// ── timeline ──────────────────────────────────────────────────────────────
const tl = document.getElementById('timeline');
// Build events: sessions start, sessions end, attempts
const events = [];
for (const s of (d.sessions||[])) {
  events.push({ts: s.started_at, kind:'session-start', obj:s});
  if (s.ended_at) events.push({ts: s.ended_at, kind:'session-end', obj:s});
}
for (const a of (d.attempts||[])) {
  events.push({ts: a.recorded_at, kind:'attempt', obj:a});
}
events.sort((a,b) => a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0);

for (const ev of events) {
  const li = el('li');
  if (ev.kind === 'session-start') {
    const s = ev.obj;
    const state = s.ended_at ? chip('ended','chip-ended') : chip('open','chip-open');
    li.innerHTML = `<span class="tl-label">Session started</span> · ${fmtDate(s.started_at)} · <span class="mono">${esc(s.id)}</span> ${state}`;
    const planDiv = el('div', {class:'note'});
    planDiv.textContent = 'Plan: ' + (s.context?.plan || '—');
    li.append(planDiv);
    const mem = s.context?.retrieved_evidence?.length || 0;
    if (mem > 0) {
      const memDiv = el('div', {class:'note'});
      memDiv.textContent = mem + ' prior failure(s) retrieved from Atlas';
      li.append(memDiv);
    }
  } else if (ev.kind === 'session-end') {
    const s = ev.obj;
    li.innerHTML = `<span class="tl-label">Session ended</span> · ${fmtDate(s.ended_at)} · <span class="mono">${esc(s.id)}</span>`;
  } else {
    // attempt
    const a = ev.obj;
    const passed = a.result?.passed;
    li.innerHTML = `<span class="tl-label">Verification attempt</span> · ${fmtDate(a.recorded_at)} ·
      ${passed ? chip('PASSED','chip-verified') : chip('FAILED','chip-failed')} ·
      ${esc(checksLabel(a.result?.checks))} ·
      ${esc(a.result?.elapsed_ms != null ? a.result.elapsed_ms + ' ms' : '—')} ·
      <span class="mono" style="font-size:.82rem">${esc((a.result?.candidate_hash||'').slice(0,16))}…</span>`;
    const failed = failedNames(a.result?.checks);
    if (failed.length) {
      const fd = el('div', {class:'note check-row-fail'});
      fd.textContent = 'Failed: ' + failed.join(', ');
      li.append(fd);
    }
  }
  tl.append(li);
}
if (!events.length) tl.innerHTML = '<li>No sessions or attempts recorded yet.</li>';

// ── sessions ──────────────────────────────────────────────────────────────
const sessDiv = document.getElementById('sessions');
for (const s of (d.sessions||[])) {
  const state = s.ended_at ? 'chip-ended' : 'chip-open';
  const stateLabel = s.ended_at ? 'ENDED' : 'OPEN';
  const card = el('div', {class:'card'});
  card.innerHTML = `
    <div class="row">
      <span class="label">Session ID</span>
      <span class="mono">${esc(s.id)}</span>
      ${chip(stateLabel, state)}
    </div>
    <div class="row">
      <span class="label">Started</span><span>${fmtDate(s.started_at)}</span>
    </div>
    ${s.ended_at ? `<div class="row"><span class="label">Ended</span><span>${fmtDate(s.ended_at)}</span></div>` : ''}
    <div class="row" style="margin-top:6px">
      <span class="label">Plan</span>
      <span style="max-width:640px">${esc(s.context?.plan || '—')}</span>
    </div>`;

  // Memory retrieved
  const ev = s.context?.retrieved_evidence || [];
  if (ev.length) {
    const evDiv = el('div');
    evDiv.innerHTML = `<h3>Evidence retrieved from Atlas (${ev.length} prior failure(s))</h3>`;
    for (const e of ev) {
      const eCard = el('div', {class:'card card-fail'});
      eCard.innerHTML = `
        <div class="row"><span class="label">Attempt</span><span class="mono">${esc(e.attempt_id.slice(0,16))}…</span></div>
        <div class="row"><span class="label">Candidate</span><span class="mono">${esc((e.candidate_hash||'').slice(0,16))}…</span></div>
        <div class="row"><span class="label">Failed checks</span><span class="check-row-fail">${esc((e.failed_checks||[]).join(', ') || 'none')}</span></div>`;
      // Inline expected vs observed for each failed check with actual values
      for (const ce of (e.check_evidence||[])) {
        const cDiv = el('div');
        cDiv.innerHTML = `<h3>Check: <span class="check-row-fail">${esc(ce.name)}</span></h3>
          <table>
            <tr><th>Field</th><th class="td-exp">Expected</th><th class="td-obs">Observed</th></tr>
            <tr>
              <td>records</td>
              <td class="td-exp mono">${jsonEscInline(ce.expected?.records ?? ce.expected)}</td>
              <td class="td-obs mono">${jsonEscInline(ce.observed?.records ?? ce.observed)}</td>
            </tr>
            <tr>
              <td>errors</td>
              <td class="td-exp mono">${jsonEscInline(ce.expected?.errors ?? '—')}</td>
              <td class="td-obs mono">${jsonEscInline(ce.observed?.errors ?? '—')}</td>
            </tr>
          </table>`;
        eCard.append(cDiv);
      }
      evDiv.append(eCard);
    }
    card.append(evDiv);
  } else {
    const nd = el('div',{class:'note'});
    nd.textContent = 'No prior failure evidence retrieved (first session or memory disabled).';
    card.append(nd);
  }

  // Decisions
  const decs = s.decisions || [];
  if (decs.length) {
    const decDiv = el('div');
    decDiv.innerHTML = `<h3>Plan decisions recorded (${decs.length})</h3>`;
    for (const dec of decs) {
      const dCard = el('div',{class:'card'});
      dCard.innerHTML = `
        <div class="row"><span class="label">Recorded</span><span>${fmtDate(dec.recorded_at)}</span></div>
        <div class="row"><span class="label">Decision</span><span style="max-width:640px">${esc(dec.decision)}</span></div>
        <div class="row"><span class="label">Source attempts</span><span class="mono" style="font-size:.82rem">${esc((dec.source_attempts||[]).map(id=>id.slice(0,16)+'…').join(', ')||'none')}</span></div>`;
      decDiv.append(dCard);
    }
    card.append(decDiv);
  }

  sessDiv.append(card);
}
if (!(d.sessions||[]).length) sessDiv.textContent = 'No sessions recorded yet.';

// ── attempts ──────────────────────────────────────────────────────────────
const attDiv = document.getElementById('attempts');
for (const a of (d.attempts||[])) {
  const passed = a.result?.passed;
  const card = el('div', {class: passed ? 'card card-pass' : 'card card-fail'});
  const failed = failedNames(a.result?.checks);
  card.innerHTML = `
    <div class="row">
      <span class="label">Result</span>
      ${statusChip(passed ? 'VERIFIED' : 'FAILED')}
      <span>${esc(checksLabel(a.result?.checks))}</span>
    </div>
    <div class="row">
      <span class="label">Session</span><span class="mono">${esc(a.session_id)}</span>
    </div>
    <div class="row">
      <span class="label">Recorded</span><span>${fmtDate(a.recorded_at)}</span>
    </div>
    <div class="row">
      <span class="label">Elapsed</span><span>${esc(a.result?.elapsed_ms != null ? a.result.elapsed_ms + ' ms' : '—')}</span>
    </div>
    <div class="row">
      <span class="label">Harness calls</span><span>${esc(a.harness_tool_calls)}</span>
    </div>
    <div class="row">
      <span class="label">Candidate</span><span class="mono" style="font-size:.82rem">${esc(a.result?.candidate_hash||'—')}</span>
    </div>
    ${failed.length ? `<div class="row"><span class="label">Failed</span><span class="check-row-fail">${esc(failed.join(', '))}</span></div>` : ''}
    ${a.result?.failure != null ? `<div class="row" style="margin-top:6px"><span class="label" style="color:#f4a0a0">Execution error</span><span class="mono check-row-fail" style="max-width:640px">${esc(String(a.result.failure))}</span></div>` : ''}`;

  // Check summary table
  if ((a.result?.checks||[]).length) {
    const tbl = el('table');
    tbl.innerHTML = '<tr><th>Check</th><th>Result</th></tr>';
    for (const c of a.result.checks) {
      const tr = el('tr', {class: c.passed ? 'check-row-pass' : 'check-row-fail'});
      tr.innerHTML = `<td class="mono">${esc(c.name)}</td><td>${c.passed ? '✓ pass' : '✗ fail'}</td>`;
      tbl.append(tr);
    }
    card.append(tbl);

    // For each failed check: expected vs observed comparison
    for (const c of a.result.checks.filter(c => !c.passed)) {
      const cSec = el('div');
      cSec.innerHTML = `<h3>Failed check: <span class="check-row-fail">${esc(c.name)}</span></h3>
        <table>
          <tr><th>Field</th><th class="td-exp">Expected</th><th class="td-obs">Observed</th></tr>
          <tr>
            <td>records</td>
            <td class="td-exp"><details><summary>expand</summary><pre>${jsonEsc(c.expected?.records ?? c.expected)}</pre></details></td>
            <td class="td-obs"><details><summary>expand</summary><pre>${jsonEsc(c.observed?.records ?? c.observed)}</pre></details></td>
          </tr>
          <tr>
            <td>errors</td>
            <td class="td-exp mono">${jsonEscInline(c.expected?.errors ?? '—')}</td>
            <td class="td-obs mono">${jsonEscInline(c.observed?.errors ?? '—')}</td>
          </tr>
          <tr>
            <td>duplicates</td>
            <td class="td-exp mono">${esc(c.expected?.duplicates ?? '—')}</td>
            <td class="td-obs mono">${esc(c.observed?.duplicates ?? '—')}</td>
          </tr>
        </table>`;
      card.append(cSec);
    }
  }

  // Full attempt JSON in details
  const det = el('details');
  det.innerHTML = `<summary>Full attempt JSON</summary><pre>${esc(JSON.stringify({
    id: a.id,
    session_id: a.session_id,
    recorded_at: a.recorded_at,
    harness_tool_calls: a.harness_tool_calls,
    result: {
      passed: a.result?.passed,
      elapsed_ms: a.result?.elapsed_ms,
      failure: a.result?.failure,
      candidate_hash: a.result?.candidate_hash,
      verifier_hash: a.result?.verifier_hash,
      checks: a.result?.checks
    }
  }, null, 2))}</pre>`;
  card.append(det);

  attDiv.append(card);
}
if (!(d.attempts||[]).length) attDiv.textContent = 'No verification attempts recorded yet.';

// ── metrics ───────────────────────────────────────────────────────────────
const m = d.metrics || {};
const mg = document.getElementById('metrics-grid');
const rows = [
  ['Attempts', m.attempts],
  ['Sessions', m.sessions],
  ['Task verified', m.task_verified ? 'Yes' : 'No'],
  ['Failed attempts', m.failed_attempts],
  ['Repeated failed checks', m.repeated_failed_checks],
  ['Total verifier time', m.verifier_elapsed_ms != null ? m.verifier_elapsed_ms + ' ms' : '—'],
  ['Harness verification calls', m.harness_tool_calls],
  ['Model tool calls', m.model_tool_calls != null ? m.model_tool_calls : 'not instrumented'],
  ['Model session freshness', m.model_session_freshness || '—'],
];
mg.innerHTML = rows.map(([k,v]) =>
  `<div class="row"><span class="label">${esc(k)}</span><span class="mono">${esc(v)}</span></div>`
).join('');

// ── full document ─────────────────────────────────────────────────────────
document.getElementById('full-doc').textContent = JSON.stringify(d, null, 2);
</script>
</html>'''

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['init','resume','plan','end','verify','serve','status'])
    parser.add_argument('--mission',required=True)
    parser.add_argument('--session')
    parser.add_argument('--candidate')
    parser.add_argument('--decision')
    parser.add_argument('--memory-disabled',action='store_true')
    args=parser.parse_args()
    store=AtlasStore()
    if args.command=='init':
        doc=store.create(args.mission)
    else:
        doc=store.get(args.mission)
    if args.command=='resume':
        sid=identity(args.session) if args.session else str(uuid.uuid4())
        updated=add_session(doc,sid,not args.memory_disabled)
        if updated!=doc:
            doc=store.save(doc,updated)
        context=next(s['context'] for s in doc['sessions'] if s['id']==sid)
        print(json.dumps({'session_id':sid,'context':context},indent=2))
    elif args.command=='plan':
        if not args.session or not args.decision:
            raise ValueError('session_and_decision_required')
        updated=record_plan(doc,args.session,args.decision)
        if updated!=doc:
            doc=store.save(doc,updated)
        print(json.dumps({'session_id':args.session,'decision_persisted':True}))
    elif args.command=='end':
        if not args.session:
            raise ValueError('session_required')
        updated=end_session(doc,args.session)
        if updated!=doc:
            doc=store.save(doc,updated)
        print(json.dumps({'session_id':args.session,'ended':True}))
    elif args.command=='verify':
        if not args.candidate or not args.session:
            raise ValueError('candidate_and_session_required')
        code=Path(args.candidate).read_text()
        candidate_hash=hashlib.sha256(code.encode()).hexdigest()
        verifier_hash=hashlib.sha256(Path(__file__).with_name('verifier.py').read_bytes()).hexdigest()
        prior=next((a for a in doc['attempts'] if a['session_id']==args.session and a['result']['candidate_hash']==candidate_hash and a['result']['verifier_hash']==verifier_hash),None)
        if prior:
            print(json.dumps({'persisted':True,'duplicate':True,'result':prior['result']},indent=2))
            return
        outcome=verify(code)
        updated,changed=add_attempt(doc,args.session,outcome)
        if changed:
            doc=store.save(doc,updated)
        print(json.dumps({'persisted':True,'duplicate':not changed,'result':outcome},indent=2))
    elif args.command=='serve':
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):
                pass
            def do_GET(self):
                if self.path!='/':
                    self.send_error(404);return
                try:
                    page=render(store.get(args.mission)).encode()
                    self.send_response(200)
                    self.send_header('Content-Type','text/html; charset=utf-8')
                    self.send_header('Cache-Control','no-store')
                    self.send_header('X-Content-Type-Options','nosniff')
                    self.end_headers();self.wfile.write(page)
                except Exception:
                    self.send_error(503,'Atlas read unavailable')
        print('Local read-only viewer: http://127.0.0.1:8765')
        HTTPServer(('127.0.0.1',8765),Handler).serve_forever()
    else:
        print(json.dumps(doc,indent=2))

if __name__=='__main__':
    try:
        main()
    except Exception as error:
        # Do not print provider exception strings: they may contain URI/host details.
        print(json.dumps({'error_type':type(error).__name__,'message':'Operation stopped. Check sandbox access and configuration privately.'}),file=sys.stderr)
        sys.exit(1)
