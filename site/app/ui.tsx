"use client";

import type { ReactNode } from "react";

/** Small, reusable explanations keep the workspace useful without filling it with help text. */
export function HelpDot({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="help-dot-wrap">
      <button type="button" className="help-dot" aria-label={label}>
        ?
      </button>
      <span className="help-popover" role="tooltip">
        {children}
      </span>
    </span>
  );
}

export function InfoDisclosure({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="compact-disclosure">
      <summary>{title}</summary>
      <div className="compact-disclosure-body">{children}</div>
    </details>
  );
}
