"use client";

// Schema-aware-ish report renderer. Renders the structured equity-research JSON
// (reports/*.json) top-level sections in order. A generic recursive renderer
// handles primitives / arrays / objects; a few keys get light special-casing.
// (This is a faithful-but-compact port of app.py's renderReport; the richest
// chart sections degrade to readable cards.)

const TITLE_KEYS = ["name", "segment", "trend", "driver", "risk", "company", "scenario", "term"];
const SKIP_TOP = new Set(["company", "node_name", "ticker", "exchange", "website", "live"]);

const prettyKey = (k: string) =>
  k.replace(/_/g, " ").replace(/\banalyst view\b/i, "analyst view").replace(/^\w/, (c) => c.toUpperCase());

// Highlight money / % / multiples inside a string.
function emphasize(text: string) {
  const parts = text.split(
    /(\$[\d.,]+\s*(?:billion|million|bn|mn|B|M|K)?|[€£¥₩][\d.,]+|\d+(?:\.\d+)?%|\d+(?:\.\d+)?x)/gi
  );
  return parts.map((p, i) =>
    /^(\$|[€£¥₩]|\d)/.test(p) && /(%|x|\d)/.test(p) && i % 2 === 1 ? (
      <b key={i} className="rp-em">
        {p}
      </b>
    ) : (
      <span key={i}>{p}</span>
    )
  );
}

function Val({ v }: { v: any }): JSX.Element | null {
  if (v === null || v === undefined || v === "") return null;
  if (typeof v === "string") return <p className="rp-p">{emphasize(v)}</p>;
  if (typeof v === "number" || typeof v === "boolean") return <p className="rp-p">{String(v)}</p>;

  if (Array.isArray(v)) {
    if (v.length === 0) return null;
    if (v.every((x) => typeof x === "string" || typeof x === "number")) {
      return (
        <ul className="rp-ul">
          {v.map((x, i) => (
            <li key={i}>{emphasize(String(x))}</li>
          ))}
        </ul>
      );
    }
    return (
      <div className="rp-cards">
        {v.map((x, i) => (
          <div className="rp-card" key={i}>
            <Val v={x} />
          </div>
        ))}
      </div>
    );
  }

  // object
  const entries = Object.entries(v);
  const titleKey = TITLE_KEYS.find((k) => typeof (v as any)[k] === "string");
  return (
    <div>
      {titleKey && <div className="rp-card-title">{(v as any)[titleKey]}</div>}
      {entries.map(([k, val]) => {
        if (k === titleKey) return null;
        const child = <Val v={val} />;
        if (!child) return null;
        return (
          <div className="rp-field" key={k}>
            <div className="rp-key">{prettyKey(k)}</div>
            {child}
          </div>
        );
      })}
    </div>
  );
}

export default function ReportView({ report }: { report: any }) {
  if (!report) return null;
  if (typeof report === "string")
    return <pre className="rp-plain">{report}</pre>;

  const meta = report.report_meta || {};
  return (
    <div className="rp">
      <div className="rp-masthead">
        <div className="rp-eyebrow">Equity Research</div>
        <div className="rp-title">{report.company || report.node_name}</div>
        <div className="rp-sub">
          {[report.ticker, report.exchange, meta.report_date].filter(Boolean).join(" · ")}
        </div>
        {report.website && (
          <a className="rp-web" href={report.website} target="_blank" rel="noreferrer">
            {report.website}
          </a>
        )}
      </div>

      {Object.entries(report).map(([k, v]) => {
        if (SKIP_TOP.has(k) || k === "report_meta") return null;
        const body = <Val v={v} />;
        if (!body) return null;
        return (
          <section className="rp-section" key={k}>
            <h4 className="rp-h">{prettyKey(k)}</h4>
            {body}
          </section>
        );
      })}
    </div>
  );
}
