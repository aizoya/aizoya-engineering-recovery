/**
 * Modelence server module: read-only mission presenter.
 *
 * Exposes exactly one route:
 *   GET /api/mission  →  the transaction-import document (sanitised for browser)
 *
 * No writes, no candidate execution, no credential values in the response.
 */
import { Module, RouteParams, RouteResponse } from 'modelence/server';
import { getAizoyadb } from './mongoClient';
import type { MissionDoc } from './types';

const MISSION_ID = 'transaction-import';

// Fields that must never reach the browser
const REDACT_TOP = new Set(['contract']); // contract is verbose; goal is fine

async function getMission(
  _params: RouteParams
): Promise<RouteResponse<{ doc: MissionDoc } | { error: string }>> {
  try {
    const db = await getAizoyadb();
    const raw = await db
      .collection('engineering_missions')
      .findOne({ _id: MISSION_ID } as Record<string, unknown>);

    if (!raw) {
      return { data: { error: 'mission_not_found' } };
    }

    // Shallow-copy and drop fields we don't want in the browser bundle
    const doc = { ...raw } as Record<string, unknown>;
    for (const k of REDACT_TOP) delete doc[k];

    // Drop process_id from sessions (not useful in the UI)
    if (Array.isArray(doc['sessions'])) {
      doc['sessions'] = (doc['sessions'] as Array<Record<string, unknown>>).map(s => {
        const { process_id: _pid, ...rest } = s;
        return rest;
      });
    }

    return { data: { doc: doc as unknown as MissionDoc } };
  } catch (err) {
    // Do not surface Atlas URI or internal details
    const msg = err instanceof Error ? err.message : 'atlas_read_failed';
    const safe = msg.replace(/mongodb\+srv:\/\/[^@]+@/g, 'mongodb+srv://***@');
    console.error('[presenter] atlas read error:', safe);
    return { data: { error: 'atlas_read_failed' } };
  }
}

export default new Module('mission', {
  stores: [],
  queries: {},
  mutations: {},
  configSchema: {},
  routes: [
    {
      path: '/api/mission',
      handlers: { get: getMission },
    },
  ],
});
