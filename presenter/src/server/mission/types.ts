/**
 * TypeScript types matching the Python harness document shape.
 * These are read-only from the presenter's perspective.
 */

export interface CheckResult {
  name: string;
  passed: boolean;
  expected?: unknown;
  observed?: unknown;
}

export interface AttemptResult {
  candidate_hash: string;
  verifier_hash?: string;
  passed: boolean;
  checks: CheckResult[];
  failure: string | null;
  elapsed_ms: number;
}

export interface Attempt {
  id: string;
  session_id: string;
  recorded_at: string;
  harness_tool_calls: number;
  result: AttemptResult;
}

export interface PlanDecision {
  decision: string;
  recorded_at: string;
  source_attempts: string[];
}

export interface RecoveryContext {
  goal: string;
  memory_enabled: boolean;
  contract: string;
  retrieved_evidence: Array<{
    attempt_id: string;
    candidate_hash: string;
    failure: string | null;
    failed_checks: string[];
    check_evidence?: CheckResult[];
  }>;
  lessons: unknown[];
  plan: string;
  limitations: string[];
}

export interface Session {
  id: string;
  started_at: string;
  ended_at?: string;
  process_id?: number;
  context: RecoveryContext;
  decisions?: PlanDecision[];
}

export interface Lesson {
  source_attempt: string;
  candidate_hash: string;
  kind: string;
  constraints_to_revisit: string[];
  execution_failure: string | null;
}

export interface MissionDoc {
  _id: string;
  revision: number;
  goal: string;
  status: string;
  contract: string;
  created_at: string;
  sessions: Session[];
  attempts: Attempt[];
  lessons: Lesson[];
}
