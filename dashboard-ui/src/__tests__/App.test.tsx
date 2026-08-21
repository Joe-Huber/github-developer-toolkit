import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import App from "../App";

vi.mock("../hooks/useReport", () => ({
  useReport: vi.fn(() => ({
    data: null,
    loading: false,
    error: null,
  })),
}));

describe("App", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
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
});
