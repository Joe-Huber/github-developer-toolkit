import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { DimensionDetail } from "../components/DimensionDetail";
import { MOCK_REPORT } from "../test-fixtures";

describe("DimensionDetail", () => {
  it("shows a no-data fallback when the dimension has no score", () => {
    render(
      <DimensionDetail
        dimension="visibility"
        scores={[{ dimension: "presence", score: 50, weight: 0.2, rationale: "x", breakdown: [] }]}
        findings={MOCK_REPORT.profile.findings}
        recommendations={MOCK_REPORT.profile.recommendations}
      />,
    );
    expect(
      screen.getByText("No score data available for this dimension."),
    ).toBeInTheDocument();
  });

  it("renders the score when the dimension has one", () => {
    render(
      <DimensionDetail
        dimension="presence"
        scores={[{ dimension: "presence", score: 50, weight: 0.2, rationale: "Presence rationale", breakdown: [] }]}
        findings={MOCK_REPORT.profile.findings}
        recommendations={MOCK_REPORT.profile.recommendations}
      />,
    );
    expect(screen.getByText("50")).toBeInTheDocument();
    expect(screen.getByText("Presence rationale")).toBeInTheDocument();
    expect(
      screen.queryByText("No score data available for this dimension."),
    ).not.toBeInTheDocument();
  });
});
