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

  it("keeps GitHub presentation attributes while stripping inline styles and scripts", () => {
    const { container } = render(
      <ProfileReadme
        readme={{
          ...readme,
          content: `<div align="center">\n<img src="docs/divider.gif" alt="divider" width="100%" height="16" style="border:5px solid red;" />\n<table align="center"><tr><td align="center" width="140">x</td></tr></table>\n<hr style="border:none;" />\n<script>window.pwned = true</script>\n</div>`,
        }}
      />,
    );
    const image = screen.getByAltText("divider");
    expect(image).toHaveAttribute(
      "src",
      "https://raw.githubusercontent.com/testuser/testuser/HEAD/docs/divider.gif",
    );
    expect(image).toHaveAttribute("width", "100%");
    expect(image).toHaveAttribute("height", "16");
    // Valid dimensions are promoted to inline styles (to beat the Tailwind
    // preflight reset), but the author's own inline style must be gone.
    expect(image).toHaveStyle({ width: "100%", height: "16px" });
    expect(image.getAttribute("style")).not.toContain("border");
    expect(container.querySelector("div[align='center']")).toBeInTheDocument();
    expect(container.querySelector("table")?.getAttribute("align")).toBe("center");
    expect(container.querySelector("td")?.getAttribute("align")).toBe("center");
    expect(container.querySelector("hr")).toBeInTheDocument();
    expect(container.querySelector("hr")).not.toHaveAttribute("style");
    expect(container.querySelector("script")).not.toBeInTheDocument();
    expect(window).not.toHaveProperty("pwned");
  });

  it("resolves repo-relative assets and links like GitHub", () => {
    render(
      <ProfileReadme
        readme={{
          ...readme,
          content: `![local](docs/a.png)\n\n[docs](docs/b.md)\n\n[frag](#about)\n\n[abs](https://example.com/x)\n\n<picture><source media="(prefers-color-scheme: dark)" srcset="docs/dark.svg" /><img src="docs/light.svg" alt="theme" /></picture>`,
        }}
      />,
    );
    expect(screen.getByAltText("local")).toHaveAttribute(
      "src",
      "https://raw.githubusercontent.com/testuser/testuser/HEAD/docs/a.png",
    );
    const docs = screen.getByRole("link", { name: "docs" });
    expect(docs).toHaveAttribute(
      "href",
      "https://github.com/testuser/testuser/blob/HEAD/docs/b.md",
    );
    expect(docs).toHaveAttribute("target", "_blank");
    expect(docs.getAttribute("rel")).toContain("noopener");
    const fragment = screen.getByRole("link", { name: "frag" });
    expect(fragment).toHaveAttribute("href", "#about");
    expect(fragment).not.toHaveAttribute("target");
    const absolute = screen.getByRole("link", { name: "abs" });
    expect(absolute).toHaveAttribute("target", "_blank");
    expect(absolute.getAttribute("rel")).toContain("noreferrer");
    expect(document.querySelector("picture source")?.getAttribute("srcset")).toBe(
      "https://raw.githubusercontent.com/testuser/testuser/HEAD/docs/dark.svg",
    );
    expect(screen.getByAltText("theme")).toHaveAttribute(
      "src",
      "https://raw.githubusercontent.com/testuser/testuser/HEAD/docs/light.svg",
    );
  });

  it("promotes valid image dimensions to inline styles over the CSS reset", () => {
    render(
      <ProfileReadme
        readme={{
          ...readme,
          content: `<img src="https://example.com/icon.svg" alt="icon" height="36" />\n\n<img src="https://example.com/banner.png" alt="banner" width="100%" />\n\n<img src="https://example.com/wat.png" alt="wat" width="junk" />`,
        }}
      />,
    );
    // Tailwind preflight sets `img { height: auto }`, which would otherwise
    // override the presentational attributes and blow up viewBox-only SVGs.
    expect(screen.getByAltText("icon")).toHaveStyle({ height: "36px" });
    expect(screen.getByAltText("banner")).toHaveStyle({ width: "100%" });
    expect(screen.getByAltText("wat")).not.toHaveAttribute("style");
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
