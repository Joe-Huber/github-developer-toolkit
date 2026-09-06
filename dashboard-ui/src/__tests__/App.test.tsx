import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import App from "../App";
import { MOCK_REPORT } from "../test-fixtures";

vi.mock("../hooks/useReport", () => ({
  useReport: vi.fn(() => ({
    data: null,
    loading: false,
    error: null,
  })),
}));

import { useReport } from "../hooks/useReport";

const mockedUseReport = vi.mocked(useReport);

describe("App", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
    mockedUseReport.mockReset();
    mockedUseReport.mockReturnValue({ data: null, loading: false, error: null });
  });

  it("renders search form with username input", () => {
    render(<App />);
    expect(screen.getByPlaceholderText("e.g. octocat")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /analyze/i })).toBeInTheDocument();
  });

  it("renders title", () => {
    render(<App />);
    expect(screen.getByText("ghdtk dashboard")).toBeInTheDocument();
  });

  it("renders demo profile quick-select chips", () => {
    render(<App />);
    expect(screen.getAllByRole("button", { name: "octocat" }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: "torvalds" })).toBeInTheDocument();
  });

  it("loads a demo profile when its chip is clicked", async () => {
    const user = userEvent.setup();
    mockedUseReport
      .mockReturnValueOnce({ data: null, loading: false, error: null })
      .mockReturnValue({ data: MOCK_REPORT, loading: false, error: null });
    render(<App />);
    await user.click(screen.getByRole("button", { name: "octocat" }));
    expect(screen.getAllByText("@testuser").length).toBeGreaterThanOrEqual(1);
  });

  it("shows cards for the scored dimensions", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "Presence" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Code Quality" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Visibility" })).toBeInTheDocument();
    expect(screen.getAllByText(/Contribution Calendar/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Profile")).toBeInTheDocument();
  });

  it("links to the project repository", () => {
    render(<App />);
    const link = screen.getByRole("link", { name: /Learn more/ });
    expect(link).toHaveAttribute("href", "https://github.com/Joe-Huber/github-developer-toolkit");
  });

  it("disables button when input is empty", () => {
    render(<App />);
    expect(screen.getByRole("button", { name: /analyze/i })).toBeDisabled();
  });

  it("enables button when input has text", async () => {
    const user = userEvent.setup();
    render(<App />);
    const input = screen.getByPlaceholderText("e.g. octocat");
    await user.type(input, "octocat");
    expect(screen.getByRole("button", { name: /analyze/i })).toBeEnabled();
  });

  it("reads initial user from URL params", () => {
    window.history.replaceState(null, "", "/?user=octocat");
    render(<App />);
    expect(screen.getByPlaceholderText("e.g. octocat")).toHaveValue("octocat");
  });

  it("shows a loading spinner while loading", () => {
    mockedUseReport.mockReturnValue({ data: null, loading: true, error: null });
    render(<App />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByText("Fetching profile data...")).toBeInTheDocument();
  });

  it("shows an error banner when the fetch fails", () => {
    mockedUseReport.mockReturnValue({ data: null, loading: false, error: "Profile not found" });
    render(<App />);
    expect(screen.getByText("Profile not found")).toBeInTheDocument();
  });

  it("renders the dashboard when report data is present", () => {
    mockedUseReport.mockReturnValue({ data: MOCK_REPORT, loading: false, error: null });
    render(<App />);
    expect(screen.getAllByText("@testuser").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: "Overview" })).toBeInTheDocument();
  });
});
