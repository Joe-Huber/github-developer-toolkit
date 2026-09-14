import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ProfileHeader } from "../components/ProfileHeader";
import { MOCK_REPORT } from "../test-fixtures";

describe("ProfileHeader", () => {
  const identity = MOCK_REPORT.profile.identity!;

  it("renders name, handle, and bio", () => {
    render(<ProfileHeader identity={identity} username="testuser" />);
    expect(screen.getByRole("heading", { name: "Test User" })).toBeInTheDocument();
    expect(screen.getAllByText("@testuser").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Building developer tools in the open.")).toBeInTheDocument();
  });

  it("renders the hireable badge when hireable", () => {
    render(<ProfileHeader identity={identity} username="testuser" />);
    expect(screen.getByText("Open to opportunities")).toBeInTheDocument();
  });

  it("does not render the hireable badge when not hireable", () => {
    render(
      <ProfileHeader
        identity={{ ...identity, hireable: null }}
        username="testuser"
      />,
    );
    expect(screen.queryByText("Open to opportunities")).not.toBeInTheDocument();
  });

  it("renders location, company, website, email, and twitter links", () => {
    render(<ProfileHeader identity={identity} username="testuser" />);
    expect(screen.getByText("San Francisco")).toBeInTheDocument();
    expect(screen.getByText("Acme")).toBeInTheDocument();
    const website = screen.getByText("https://testuser.dev");
    expect(website.closest("a")).toHaveAttribute("href", "https://testuser.dev");
    const email = screen.getByText("test@example.com");
    expect(email.closest("a")).toHaveAttribute("href", "mailto:test@example.com");
    const twitter = screen
      .getAllByRole("link")
      .find((link) => link.getAttribute("href") === "https://x.com/testuser");
    expect(twitter).toBeDefined();
  });

  it("shows account age from created_at", () => {
    render(<ProfileHeader identity={identity} username="testuser" />);
    expect(screen.getByText("On GitHub since 2015")).toBeInTheDocument();
  });

  it("falls back to initials when avatar_url is missing", () => {
    render(<ProfileHeader identity={identity} username="testuser" />);
    expect(screen.getByRole("img", { name: "Avatar placeholder for testuser" })).toHaveTextContent(
      "TU",
    );
  });

  it("renders an avatar image when avatar_url is present", () => {
    render(
      <ProfileHeader
        identity={{ ...identity, avatar_url: "https://example.com/avatar.png" }}
        username="testuser"
      />,
    );
    const image = screen.getByAltText("Test User (testuser)");
    expect(image).toHaveAttribute("src", "https://example.com/avatar.png");
  });

  it("falls back to the handle when identity is null", () => {
    render(<ProfileHeader identity={null} username="ghost" />);
    expect(screen.getByRole("heading", { name: "@ghost" })).toBeInTheDocument();
    expect(screen.getByText("Profile details are unavailable.")).toBeInTheDocument();
  });

  it("omits optional rows that are missing", () => {
    render(
      <ProfileHeader
        identity={{ ...identity, location: null, company: null, blog: null, email: null, twitter_username: null, created_at: null }}
        username="testuser"
      />,
    );
    expect(screen.queryByText("San Francisco")).not.toBeInTheDocument();
    expect(screen.queryByText("On GitHub since")).not.toBeInTheDocument();
  });
});
