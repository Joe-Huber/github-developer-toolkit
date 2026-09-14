import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ContributionGraph } from "../components/ContributionGraph";
import { MOCK_REPORT } from "../test-fixtures";

describe("ContributionGraph", () => {
  const analysis = MOCK_REPORT.profile.analyses!.contribution_calendar!;

  it("renders the contribution grid with per-day counts", () => {
    render(<ContributionGraph analysis={analysis} />);
    const grid = screen.getByRole("grid", { name: "Daily contributions" });
    expect(grid).toBeInTheDocument();
    expect(screen.getByRole("gridcell", { name: /12 contributions on 2025-08-11/ })).toBeInTheDocument();
    expect(screen.getByRole("gridcell", { name: /0 contributions on 2025-08-12/ })).toBeInTheDocument();
  });

  it("renders the total contributions summary", () => {
    render(<ContributionGraph analysis={analysis} />);
    expect(screen.getByText("1,280 total")).toBeInTheDocument();
  });

  it("renders the hidden contributions disclosure", () => {
    render(<ContributionGraph analysis={analysis} />);
    expect(screen.getByText("3 contributions hidden (private repositories).")).toBeInTheDocument();
  });

  it("shows an unavailable state when the calendar was not collected", () => {
    render(<ContributionGraph analysis={{ ...analysis, weeks: [] }} />);
    expect(screen.getByText("Contribution calendar is unavailable.")).toBeInTheDocument();
  });

  it("renders nothing when the analysis is missing", () => {
    const { container } = render(<ContributionGraph analysis={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
