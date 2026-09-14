import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ProfileReadme } from "../components/ProfileReadme";
import { MOCK_REPORT } from "../test-fixtures";

describe("ProfileReadme", () => {
  const readme = MOCK_REPORT.profile.analyses!.readme!;

  it("renders markdown content when present", () => {
    render(<ProfileReadme readme={readme} />);
    expect(screen.getByRole("heading", { name: "Hi there" })).toBeInTheDocument();
    expect(screen.getByText("developer tools", { exact: false })).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Website" });
    expect(link).toHaveAttribute("href", "https://testuser.dev");
  });

  it("links to the source repository", () => {
    render(<ProfileReadme readme={readme} />);
    const repoLink = screen.getByRole("link", { name: "testuser/testuser" });
    expect(repoLink).toHaveAttribute("href", "https://github.com/testuser/testuser");
  });

  it("shows a status message when there is no profile README", () => {
    render(
      <ProfileReadme
        readme={{ ...readme, status: "no_readme", content: null }}
      />,
    );
    expect(screen.queryByRole("heading", { name: "Hi there" })).not.toBeInTheDocument();
    expect(
      screen.getByText("The profile repository exists but has no README file."),
    ).toBeInTheDocument();
  });

  it("shows a message for an empty README", () => {
    render(
      <ProfileReadme
        readme={{ ...readme, status: "empty", content: "" }}
      />,
    );
    expect(
      screen.getByText("The profile README exists but is empty."),
    ).toBeInTheDocument();
  });

  it("renders nothing when the analysis is missing", () => {
    const { container } = render(<ProfileReadme readme={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("does not render dangerous HTML from markdown", () => {
    render(
      <ProfileReadme
        readme={{
          ...readme,
          content: `# Safe\n\n<script>window.pwned = true</script>\n\n<img src="x" onerror="window.pwned=true">`,
        }}
      />,
    );
    expect(window).not.toHaveProperty("pwned");
    expect(document.querySelector("script")).not.toBeInTheDocument();
  });
});
