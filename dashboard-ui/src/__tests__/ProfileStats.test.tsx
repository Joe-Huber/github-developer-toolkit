import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ProfileStats } from "../components/ProfileStats";
import { MOCK_REPORT } from "../test-fixtures";

describe("ProfileStats", () => {
  const stats = MOCK_REPORT.profile.top_stats!;

  it("renders stat tiles with formatted values", () => {
    render(<ProfileStats stats={stats} />);
    expect(screen.getByText("Total stars")).toBeInTheDocument();
    expect(screen.getByText("1,530")).toBeInTheDocument();
    expect(screen.getByText("Followers")).toBeInTheDocument();
    expect(screen.getByText("1,200")).toBeInTheDocument();
  });

  it("marks partial metrics", () => {
    render(<ProfileStats stats={stats} />);
    expect(screen.getAllByText("partial").length).toBeGreaterThanOrEqual(1);
  });

  it("renders top repositories with star counts", () => {
    render(<ProfileStats stats={stats} />);
    const link = screen.getByRole("link", { name: "testuser/toolkit" });
    expect(link).toHaveAttribute("href", "https://github.com/testuser/toolkit");
    expect(screen.getByText("1,000")).toBeInTheDocument();
    expect(screen.getByText("A developer toolkit")).toBeInTheDocument();
    expect(screen.getAllByText("TypeScript").length).toBeGreaterThanOrEqual(1);
  });

  it("renders language shares", () => {
    render(<ProfileStats stats={stats} />);
    expect(screen.getByText("45.0%")).toBeInTheDocument();
    expect(screen.getByText("27.0%")).toBeInTheDocument();
  });

  it("renders nothing when stats are null", () => {
    const { container } = render(<ProfileStats stats={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows an empty state when no metrics collected", () => {
    render(<ProfileStats stats={{ ...stats, metrics: [], top_repositories: [], top_languages: [] }} />);
    expect(screen.getByText("No statistics collected for this profile.")).toBeInTheDocument();
  });
});
