import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { FindingsList } from "../components/FindingsList";
import { MOCK_REPORT } from "../test-fixtures";
import type { Finding } from "../types/report";

const findings = MOCK_REPORT.profile.findings;

const EVIDENCE_FINDING: Finding = {
  id: "f4",
  type: "stale_repo",
  severity: "info",
  title: "Stale repository",
  message: "No recent commits.",
  dimension: "activity",
  evidence: [
    { entity: "repository", identifier: "octocat/hello-world", field: "pushed_at" },
  ],
  recommendation_ids: [],
};

describe("FindingsList", () => {
  it("renders all findings", () => {
    render(<FindingsList findings={findings} title="Findings" />);
    expect(screen.getByText("Missing README in main repo")).toBeInTheDocument();
    expect(screen.getByText("Low commit frequency")).toBeInTheDocument();
    expect(screen.getByText("Default avatar")).toBeInTheDocument();
  });

  it("shows correct count", () => {
    render(<FindingsList findings={findings} title="Findings" />);
    expect(screen.getByText("(3)")).toBeInTheDocument();
  });

  it("filters by severity when toggled off", async () => {
    const user = userEvent.setup();
    render(<FindingsList findings={findings} title="Findings" />);
    await user.click(screen.getByRole("button", { name: /high/i }));
    expect(screen.queryByText("Missing README in main repo")).not.toBeInTheDocument();
    expect(screen.getByText("(2)")).toBeInTheDocument();
  });

  it("filters by dimension dropdown", async () => {
    const user = userEvent.setup();
    render(<FindingsList findings={findings} title="Findings" />);
    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "activity");
    expect(screen.getByText("Low commit frequency")).toBeInTheDocument();
    expect(screen.queryByText("Missing README in main repo")).not.toBeInTheDocument();
  });

  it("sorts by title", async () => {
    const user = userEvent.setup();
    render(<FindingsList findings={findings} title="Findings" />);
    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[1], "title");
    const items = screen.getAllByText(/(?:Missing README|Low commit|Default avatar)/);
    expect(items[0]).toHaveTextContent("Default avatar");
  });

  it("renders clickable evidence links to GitHub", () => {
    render(<FindingsList findings={[EVIDENCE_FINDING]} title="Findings" />);
    const link = screen.getByRole("link", { name: /octocat\/hello-world/ });
    expect(link).toHaveAttribute("href", "https://github.com/octocat/hello-world");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
  });

  it("shows empty message when no findings match", async () => {
    const user = userEvent.setup();
    render(<FindingsList findings={findings} title="Findings" />);
    await user.click(screen.getByRole("button", { name: /high/i }));
    await user.click(screen.getByRole("button", { name: /medium/i }));
    await user.click(screen.getByRole("button", { name: /low/i }));
    await user.click(screen.getByRole("button", { name: /info/i }));
    expect(screen.getByText("No findings match the current filters.")).toBeInTheDocument();
  });
});
