import type { MetricRecord } from "../types/report";
import { formatMetricValue } from "../lib/metrics";

const AVAILABILITY_STYLES: Record<MetricRecord["availability"], string> = {
  available: "bg-good/15 text-good",
  partial: "bg-warn/15 text-warn",
  unavailable: "bg-bad/15 text-bad",
};

interface MetricsGridProps {
  metrics: MetricRecord[];
}

export function MetricsGrid({ metrics }: MetricsGridProps) {
  if (metrics.length === 0) return null;

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
      {metrics.map((m) => (
        <div key={m.id} className="bg-bg/50 border border-border rounded-lg p-3">
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className="text-xs text-muted truncate">{m.label}</span>
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] capitalize shrink-0 ${AVAILABILITY_STYLES[m.availability]}`}
            >
              {m.availability}
            </span>
          </div>
          <div className="text-base font-semibold text-text">
            {formatMetricValue(m.value)}
          </div>
          <div className="text-[10px] text-muted mt-1">
            confidence {Math.round(m.confidence * 100)}%
          </div>
        </div>
      ))}
    </div>
  );
}
