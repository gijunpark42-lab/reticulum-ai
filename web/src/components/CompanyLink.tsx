"use client";

import type { Resolver } from "@/lib/company";

// Renders a table cell's text as a button that opens the company's NodePanel —
// the same panel you get by clicking the company in the 3D graph — but only when
// the text actually names a company in the graph. Anything else renders as
// plain text, so a cell is never a dead link.
export default function CompanyLink({
  text,
  resolve,
  onOpen,
  className,
}: {
  text: string;
  resolve: Resolver;
  onOpen: (id: string) => void;
  className?: string;
}) {
  const id = resolve(text);
  if (!id) return <>{text}</>;
  return (
    <button
      type="button"
      className={"co-link" + (className ? " " + className : "")}
      title={id === text ? `Open ${id}` : `Open ${id} (${text})`}
      onClick={(e) => {
        e.stopPropagation();
        onOpen(id);
      }}
    >
      {text}
    </button>
  );
}
