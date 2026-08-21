import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { Dashboard } from "../components/Dashboard";
import { MOCK_REPORT } from "../test-fixtures";

describe("Dashboard", () => {
  const defaultProps = {
    report: MOCK_REPORT,
    onBack: vi.fn(),
    onTabChange: vi.fn(),
  };

  it("renders the username", () => {
    render(<Dashboard {...defaultProps} />);
    const usernames = screen.getAllByText("@testuser");
    expect(usernames.length).toBeGreaterThanOrEqual(1);
  });

  it("renders all dimension tabs", () => {
    render(<Dashboard {...defaultProps} />);
    expect(screen.getByRole("button", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Code Quality" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Visibility" })).toBeInTheDocument();
  });

  it("renders the overall score", () => {
    render(<Dashboard {...defaultProps} />);
    expect(screen.getByText("65")).toBeInTheDocument();
  });

  it("renders findings on overview", () => {
    render(<Dashboard {...defaultProps} />);
    expect(screen.getByText("Missing README in main repo")).toBeInTheDocument();
    expect(screen.getByText("Low commit frequency")).toBeInTheDocument();
  });

  it("renders recommendations on overview", () => {
    render(<Dashboard {...defaultProps} />);
    expect(screen.getByText("Add a README to your main repository")).toBeInTheDocument();
  });

  it("switches to dimension detail when tab clicked", async () => {
    const user = userEvent.setup();
    render(<Dashboard {...defaultProps} />);
    await user.click(screen.getByRole("button", { name: "Documentation" }));
    expect(screen.getByText("Well documented.")).toBeInTheDocument();
  });

  it("calls onTabChange when switching tabs", async () => {
    const onTabChange = vi.fn();
    const user = userEvent.setup();
    render(<Dashboard {...defaultProps} onTabChange={onTabChange} />);
    await user.click(screen.getByRole("button", { name: "Activity" }));
    expect(onTabChange).toHaveBeenCalledWith("activity");
  });

  it("calls onBack when back button clicked", async () => {
    const onBack = vi.fn();
    const user = userEvent.setup();
    render(<Dashboard {...defaultProps} onBack={onBack} />);
    await user.click(screen.getByTitle("Back to search"));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it("opens to initial tab from props", () => {
    render(<Dashboard {...defaultProps} initialTab="code_quality" />);
    expect(screen.getByText("High quality code.")).toBeInTheDocument();
  });
});
