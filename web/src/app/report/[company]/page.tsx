"use client";

import { useEffect, useState } from "react";
import ReportView from "@/components/ReportView";
import { fetchJson } from "@/lib/data";

// Print-friendly, standalone report page. Opened in a new tab by the panel's
// "Download PDF" button; the user prints / saves as PDF from here.
export default function ReportPrintPage({ params }: { params: { company: string } }) {
  const company = decodeURIComponent(params.company);
  const [report, setReport] = useState<any>(undefined);

  useEffect(() => {
    document.title = `${company} — Equity Research`;
    fetchJson<Record<string, any>>("/data/reports.bundle.json")
      .then((rb) => setReport(rb[company] ?? null))
      .catch(() => setReport(null));
  }, [company]);

  return (
    <div className="print-scope">
      <div className="print-bar">
        <button className="btn" onClick={() => window.print()}>
          Print / Save as PDF
        </button>
      </div>
      {report === undefined && <p>Loading…</p>}
      {report === null && <p>No report found for {company}.</p>}
      {report && (
        <div className="print-body">
          <ReportView report={report} />
        </div>
      )}
    </div>
  );
}
