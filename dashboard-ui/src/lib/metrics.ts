import type { MetricRecord } from "../types/report";

export function formatMetricValue(value: MetricRecord["value"]): string {
  if (value === null || value === undefined) return "\u2014";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    if (Number.isInteger(value)) return value.toLocaleString("en-US");
    return value.toFixed(2);
  }
  return value;
}
