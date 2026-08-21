import { useState } from "react";
import type { Finding, FindingSeverity, DimensionId } from "../types/report";

const SEVERITY_STYLES: Record<FindingSeverity, string> = {
  critical: "bg-bad/20 text-bad",
  high: "bg-orange-500/20 text-orange-400",
  medium: "bg-warn/20 text-warn",
  low: "bg-accent/20 text-accent",
  info: "bg-muted/20 text-muted",
};

const SEVERITY_ORDER: FindingSeverity[] = ["critical", "high", "medium", "low", "info"];

const DIMENSION_LABELS: Record<DimensionId, string> = {
  presence: "Presence",
  code_quality: "Code Quality",
  activity: "Activity",
  engagement: "Engagement",
  documentation: "Documentation",
  open_source: "Open Source",
  consistency: "Consistency",
  contribution: "Contribution",
  visibility: "Visibility",
};

interface FindingsListProps {
  findings: Finding[];
  title: string;
}

export function FindingsList({ findings, title }: FindingsListProps) {
  const [severityFilter, setSeverityFilter] = useState<Set<FindingSeverity>>(
    new Set(SEVERITY_ORDER)
  );
  const [dimensionFilter, setDimensionFilter] = useState<Set<DimensionId> | null>(null);
  const [sortBy, setSortBy] = useState<"severity" | "dimension" | "title">("severity");

  const dimensions = [...new Set(findings.map((f) => f.dimension).filter(Boolean))] as DimensionId[];

  const filtered = findings
    .filter((f) => severityFilter.has(f.severity))
    .filter((f) => !dimensionFilter || !f.dimension || dimensionFilter.has(f.dimension))
    .sort((a, b) => {
      if (sortBy === "severity")
        return SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity);
      if (sortBy === "dimension")
        return (a.dimension ?? "").localeCompare(b.dimension ?? "");
      return a.title.localeCompare(b.title);
    });

  const toggleSeverity = (sev: FindingSeverity) => {
    setSeverityFilter((prev) => {
      const next = new Set(prev);
      if (next.has(sev)) next.delete(sev);
      else next.add(sev);
      return next;
    });
  };

  return (
    <div className="bg-panel rounded-lg border border-border p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-text">
          {title}{" "}
          <span className="text-muted text-sm font-normal">({filtered.length})</span>
        </h3>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-4 text-sm">
        <div className="flex gap-1">
          {SEVERITY_ORDER.map((sev) => (
            <button
              key={sev}
              onClick={() => toggleSeverity(sev)}
              className={`px-2 py-1 rounded text-xs capitalize transition-colors ${
                severityFilter.has(sev)
                  ? SEVERITY_STYLES[sev]
                  : "bg-border/30 text-muted/50"
              }`}
            >
              {sev}
            </button>
          ))}
        </div>

        {dimensions.length > 0 && (
          <select
            className="bg-border/30 text-text text-xs rounded px-2 py-1 border border-border"
            onChange={(e) => {
              const val = e.target.value;
              setDimensionFilter(val ? new Set([val as DimensionId]) : null);
            }}
            value={dimensionFilter ? [...dimensionFilter][0] : ""}
          >
            <option value="">All dimensions</option>
            {dimensions.map((d) => (
              <option key={d} value={d}>
                {DIMENSION_LABELS[d]}
              </option>
            ))}
          </select>
        )}

        <select
          className="bg-border/30 text-text text-xs rounded px-2 py-1 border border-border"
          onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          value={sortBy}
        >
          <option value="severity">Sort by severity</option>
          <option value="dimension">Sort by dimension</option>
          <option value="title">Sort by title</option>
        </select>
      </div>

      {/* List */}
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {filtered.length === 0 && (
          <p className="text-muted text-sm">No findings match the current filters.</p>
        )}
        {filtered.map((f) => (
          <div key={f.id} className="border border-border rounded p-3">
            <div className="flex items-center gap-2 mb-1">
              <span
                className={`px-2 py-0.5 rounded text-xs capitalize ${SEVERITY_STYLES[f.severity]}`}
              >
                {f.severity}
              </span>
              <span className="font-medium text-text text-sm">{f.title}</span>
              {f.dimension && (
                <span className="text-xs text-muted ml-auto">
                  {DIMENSION_LABELS[f.dimension]}
                </span>
              )}
            </div>
            <p className="text-muted text-xs">{f.message}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
