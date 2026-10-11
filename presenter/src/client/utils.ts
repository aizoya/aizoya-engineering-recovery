/**
 * Shared display helpers — no side effects, pure functions.
 */

/** Format an ISO timestamp for display. */
export function fmtDate(iso: string | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  } catch {
    return iso;
  }
}

/** Count pass/total from a checks array. */
export function checksLabel(checks: Array<{ passed: boolean }>): string {
  if (!checks || checks.length === 0) return '—';
  const passed = checks.filter(c => c.passed).length;
  return `${passed}/${checks.length} checks passed`;
}

/** Names of failed checks. */
export function failedNames(checks: Array<{ passed: boolean; name: string }>): string[] {
  return checks.filter(c => !c.passed).map(c => c.name);
}

/**
 * Stringify a value, then replace U+2028 (line separator) and U+2029
 * (paragraph separator) with visible escape sequences so judges can see
 * the Unicode character responsible for the original failure without
 * altering the stored evidence.
 */
export function jsonShowUnicode(v: unknown, indent?: number): string {
  return JSON.stringify(v, null, indent)
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029');
}
