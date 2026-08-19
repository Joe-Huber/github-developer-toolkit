import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ScoreOverview } from "../components/ScoreOverview";
import { MOCK_REPORT } from "../test-fixtures";

describe("ScoreOverview", () => {
  it("renders the username", () => {
    render(<ScoreOverview report={MOCK_REPORT} />);
    expect(screen.getByText("@testuser")).toBeInTheDocument();
  });

  it("renders the overall score", () => {
    render(<ScoreOverview report={MOCK_REPORT} />);
    expect(screen.getByText("65")).toBeInTheDocument();
    expect(screen.getByText("/100")).toBeInTheDocument();
  });

  it("renders strengths", () => {
    render(<ScoreOverview report={MOCK_REPORT} />);
    expect(screen.getByText("Strong code quality")).toBeInTheDocument();
    expect(screen.getByText("Active contributor")).toBeInTheDocument();
  });

  it("renders weaknesses", () => {
    render(<ScoreOverview report={MOCK_REPORT} />);
    expect(screen.getByText("Low visibility")).toBeInTheDocument();
    expect(screen.getByText("Inconsistent activity")).toBeInTheDocument();
  });

  it("renders language distribution", () => {
    render(<ScoreOverview report={MOCK_REPORT} />);
    expect(screen.getByText("Languages")).toBeInTheDocument();
    expect(screen.getByText("TypeScript")).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
  });

  it("renders language percentages", () => {
    render(<ScoreOverview report={MOCK_REPORT} />);
    expect(screen.getByText("45.0%")).toBeInTheDocument();
    expect(screen.getByText("27.0%")).toBeInTheDocument();
  });

  it("renders analyzed date", () => {
    render(<ScoreOverview report={MOCK_REPORT} />);
    expect(screen.getByText(/Analyzed/)).toBeInTheDocument();
  });
});
