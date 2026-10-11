import React from 'react';

type CardVariant = 'default' | 'pass' | 'fail';

const border: Record<CardVariant, string> = {
  default: 'border-slate-700',
  pass:    'border-emerald-800',
  fail:    'border-red-800',
};

export function Card({
  children,
  variant = 'default',
  className = '',
}: {
  children: React.ReactNode;
  variant?: CardVariant;
  className?: string;
}) {
  return (
    <div
      className={`bg-slate-800 border rounded-xl p-4 my-2 ${border[variant]} ${className}`}
    >
      {children}
    </div>
  );
}

export function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap gap-3 items-baseline py-0.5">
      <span className="text-slate-400 text-sm min-w-[110px] shrink-0">{label}</span>
      <span className="font-mono text-sm break-all">{children}</span>
    </div>
  );
}

export function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-cyan-400 text-xs font-semibold uppercase tracking-widest mb-3">
      {children}
    </h2>
  );
}

export function SubHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-slate-300 text-sm font-semibold mt-3 mb-1">{children}</h3>
  );
}

export function Section({ children }: { children: React.ReactNode }) {
  return (
    <section className="bg-slate-900 border border-slate-700 rounded-2xl p-5 my-4">
      {children}
    </section>
  );
}

export function Disclosure({
  summary,
  children,
}: {
  summary: string;
  children: React.ReactNode;
}) {
  return (
    <details className="my-1">
      <summary className="cursor-pointer text-cyan-400 text-sm py-1 hover:text-cyan-300 select-none">
        {summary}
      </summary>
      {children}
    </details>
  );
}

export function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="whitespace-pre-wrap break-all font-mono text-xs bg-slate-950 border border-slate-800 rounded-lg p-3 mt-1 overflow-auto leading-relaxed">
      {children}
    </pre>
  );
}
