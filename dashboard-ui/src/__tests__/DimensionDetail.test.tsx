import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { DimensionDetail } from "../components/DimensionDetail";
import { formatMetricValue } from "../lib/metrics";
import { MOCK_REPORT } from "../test-fixtures";
import type { MetricRecord, ProfileAnalyses } from "../types/report";

const COMMITS_METRICS: MetricRecord[] = [
  {
    id: "commits.total",
    label: "Total commits",
    value: 1243,
    sources: [],
    timestamp: "2025-08-18T12:00:00Z",
    confidence: 1,
    availability: "available",
  },
  {
    id: "commits.cadence",
    label: "Cadence",
    value: 4.5,
    sources: [],
    timestamp: "2025-08-18T12:00:00Z",
    confidence: 0.8,
    availability: "partial",
  },
  {
    id: "commits.active_days",
    label: "Active days",
    value: 21,
    sources: [],
    timestamp: "2025-08-18T12:00:00Z",
    confidence: 0.9,
    availability: "available",
  },
];

const ACTIVITY_ANALYSES: ProfileAnalyses = {
  ...MOCK_REPORT.profile.analyses!,
  commits: { metrics: COMMITS_METRICS, findings: [] },
};

describe("DimensionDetail", () => {
  it("shows a no-data fallback when the dimension has no score", () => {
    render(
      <DimensionDetail
        dimension="visibility"
        scores={[{ dimension: "presence", score: 50, weight: 0.2, rationale: "x", breakdown: [] }]}
        findings={MOCK_REPORT.profile.findings}
        recommendations={MOCK_REPORT.profile.recommendations}
        analyses={null}
      />,
    );
    expect(
      screen.getByText("Not scored independently; see the metrics below for this area."),
    ).toBeInTheDocument();
  });

  it("renders the score when the dimension has one", () => {
    render(
      <DimensionDetail
        dimension="presence"
        scores={[{ dimension: "presence", score: 50, weight: 0.2, rationale: "Presence rationale", breakdown: [] }]}
        findings={MOCK_REPORT.profile.findings}
        recommendations={MOCK_REPORT.profile.recommendations}
        analyses={null}
      />,
    );
    expect(screen.getByText("50")).toBeInTheDocument();
    expect(screen.getByText("Presence rationale")).toBeInTheDocument();
    expect(
      screen.queryByText("Not scored independently; see the metrics below for this area."),
    ).not.toBeInTheDocument();
  });

  it("renders the underlying analysis metrics for the dimension", () => {
    render(
      <DimensionDetail
        dimension="activity"
        scores={[{ dimension: "activity", score: 70, weight: 0.1, rationale: "Moderate activity.", breakdown: [] }]}
        findings={MOCK_REPORT.profile.findings}
        recommendations={MOCK_REPORT.profile.recommendations}
        analyses={ACTIVITY_ANALYSES}
      />,
    );
    expect(screen.getByText("Commits")).toBeInTheDocument();
    expect(screen.getByText("Total commits")).toBeInTheDocument();
    expect(screen.getByText("1,243")).toBeInTheDocument();
    expect(screen.getByText("Cadence")).toBeInTheDocument();
    expect(screen.getByText("4.50")).toBeInTheDocument();
    expect(screen.getByText("Active days")).toBeInTheDocument();
    expect(screen.getByText("21")).toBeInTheDocument();
  });
});

describe("formatMetricValue", () => {
  it("formats primitives into display strings", () => {
    expect(formatMetricValue(1243)).toBe("1,243");
    expect(formatMetricValue(4.5)).toBe("4.50");
    expect(formatMetricValue(true)).toBe("Yes");
    expect(formatMetricValue(false)).toBe("No");
    expect(formatMetricValue("octocat/octocat")).toBe("octocat/octocat");
    expect(formatMetricValue(null)).toBe("\u2014");
  });
});
