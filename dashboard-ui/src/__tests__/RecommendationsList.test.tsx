import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { RecommendationsList } from "../components/RecommendationsList";
import { MOCK_REPORT } from "../test-fixtures";

const recommendations = MOCK_REPORT.profile.recommendations;

describe("RecommendationsList", () => {
  it("renders all recommendations", () => {
    render(<RecommendationsList recommendations={recommendations} title="Recommendations" />);
    expect(screen.getByText("Add a README to your main repository")).toBeInTheDocument();
    expect(screen.getByText("Commit more regularly")).toBeInTheDocument();
  });

  it("shows correct count", () => {
    render(<RecommendationsList recommendations={recommendations} title="Recommendations" />);
    expect(screen.getByText("(2)")).toBeInTheDocument();
  });

  it("filters by priority when toggled off", async () => {
    const user = userEvent.setup();
    render(<RecommendationsList recommendations={recommendations} title="Recommendations" />);
    await user.click(screen.getByRole("button", { name: /high/i }));
    expect(screen.queryByText("Add a README to your main repository")).not.toBeInTheDocument();
    expect(screen.getByText("(1)")).toBeInTheDocument();
  });

  it("sorts by effort", async () => {
    const user = userEvent.setup();
    render(<RecommendationsList recommendations={recommendations} title="Recommendations" />);
    const sortSelect = screen.getByRole("combobox");
    await user.selectOptions(sortSelect, "effort");
    const items = screen.getAllByText(/effort:/);
    expect(items[0]).toHaveTextContent("effort: low");
  });

  it("shows empty message when no recommendations match", async () => {
    const user = userEvent.setup();
    render(<RecommendationsList recommendations={recommendations} title="Recommendations" />);
    await user.click(screen.getByRole("button", { name: /high/i }));
    await user.click(screen.getByRole("button", { name: /medium/i }));
    await user.click(screen.getByRole("button", { name: /low/i }));
    expect(screen.getByText("No recommendations match the current filters.")).toBeInTheDocument();
  });
});
