import { useState } from "react";
import type { Recommendation, RecommendationPriority, RecommendationEffort } from "../types/report";

const PRIORITY_STYLES: Record<RecommendationPriority, string> = {
  high: "bg-bad/20 text-bad",
  medium: "bg-warn/20 text-warn",
  low: "bg-accent/20 text-accent",
};

const EFFORT_STYLES: Record<RecommendationEffort, string> = {
  low: "bg-good/15 text-good",
  medium: "bg-warn/15 text-warn",
  high: "bg-bad/15 text-bad",
};

interface RecommendationsListProps {
  recommendations: Recommendation[];
  title: string;
}

export function RecommendationsList({ recommendations, title }: RecommendationsListProps) {
  const [priorityFilter, setPriorityFilter] = useState<Set<RecommendationPriority>>(
    new Set(["high", "medium", "low"])
  );
  const [sortBy, setSortBy] = useState<"priority" | "effort" | "action">("priority");

  const PRIORITY_ORDER: RecommendationPriority[] = ["high", "medium", "low"];
  const EFFORT_ORDER: RecommendationEffort[] = ["low", "medium", "high"];

  const filtered = recommendations
    .filter((r) => priorityFilter.has(r.priority))
    .sort((a, b) => {
      if (sortBy === "priority")
        return PRIORITY_ORDER.indexOf(a.priority) - PRIORITY_ORDER.indexOf(b.priority);
      if (sortBy === "effort")
        return EFFORT_ORDER.indexOf(a.effort) - EFFORT_ORDER.indexOf(b.effort);
      return a.action.localeCompare(b.action);
    });

  const togglePriority = (p: RecommendationPriority) => {
    setPriorityFilter((prev) => {
      const next = new Set(prev);
      if (next.has(p)) next.delete(p);
      else next.add(p);
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
          {PRIORITY_ORDER.map((p) => (
            <button
              key={p}
              onClick={() => togglePriority(p)}
              className={`px-2 py-1 rounded text-xs capitalize transition-colors ${
                priorityFilter.has(p) ? PRIORITY_STYLES[p] : "bg-border/30 text-muted/50"
              }`}
            >
              {p}
            </button>
          ))}
        </div>

        <select
          className="bg-border/30 text-text text-xs rounded px-2 py-1 border border-border"
          onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          value={sortBy}
        >
          <option value="priority">Sort by priority</option>
          <option value="effort">Sort by effort</option>
          <option value="action">Sort by action</option>
        </select>
      </div>

      {/* List */}
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {filtered.length === 0 && (
          <p className="text-muted text-sm">No recommendations match the current filters.</p>
        )}
        {filtered.map((r) => (
          <div key={r.id} className="border border-border rounded p-3">
            <div className="flex items-center gap-2 mb-1">
              <span
                className={`px-2 py-0.5 rounded text-xs capitalize ${PRIORITY_STYLES[r.priority]}`}
              >
                {r.priority}
              </span>
              <span
                className={`px-2 py-0.5 rounded text-xs capitalize ${EFFORT_STYLES[r.effort]}`}
              >
                effort: {r.effort}
              </span>
            </div>
            <p className="text-text text-sm font-medium mb-1">{r.action}</p>
            <p className="text-muted text-xs">{r.rationale}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
