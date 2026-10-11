import React from 'react';

type ChipVariant = 'verified' | 'failed' | 'ready' | 'open' | 'ended';

const styles: Record<ChipVariant, string> = {
  verified: 'bg-emerald-950 text-emerald-300 border border-emerald-700',
  failed:   'bg-red-950   text-red-300   border border-red-700',
  ready:    'bg-sky-950   text-sky-300   border border-sky-700',
  open:     'bg-green-950 text-green-300 border border-green-700',
  ended:    'bg-slate-800 text-slate-400 border border-slate-600',
};

export function Chip({ label, variant }: { label: string; variant: ChipVariant }) {
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${styles[variant]}`}>
      {label}
    </span>
  );
}

export function statusChip(status: string): React.ReactElement {
  if (status === 'VERIFIED') return <Chip label="VERIFIED"     variant="verified" />;
  if (status === 'NEEDS_REPAIR' || status === 'FAILED')
                              return <Chip label={status}      variant="failed"   />;
  return                             <Chip label={status}      variant="ready"    />;
}
