import DOMPurify from "dompurify";
import { Marked } from "marked";
import type { ReadmeAssessment } from "../types/report";

const STATUS_MESSAGES: Record<string, string> = {
  present: "This profile README previews below.",
  no_profile_repo: "This profile has no `username/username` README repository, so there is no profile README to preview.",
  no_readme: "The profile repository exists but has no README file.",
  empty: "The profile README exists but is empty.",
  fetch_failed: "The profile README could not be retrieved right now.",
};

const marked = new Marked();

function renderMarkdown(source: string): string {
  const html = marked.parse(source, { async: false }) as string;
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true, svg: true, svgFilters: true },
  });
}

interface ProfileReadmeProps {
  readme: ReadmeAssessment | null;
}

export function ProfileReadme({ readme }: ProfileReadmeProps) {
  if (readme === null) return null;

  const contentPresent = readme.status === "present" && Boolean(readme.content?.trim());

  return (
    <section
      aria-label="Profile README"
      className="bg-panel border border-border rounded-lg p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <h3 className="text-sm font-semibold text-muted uppercase tracking-wide">
          Profile README
        </h3>
        {readme.repository && (
          <a
            href={`https://github.com/${readme.repository}`}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-accent hover:underline"
          >
            {readme.repository}
          </a>
        )}
      </div>

      {contentPresent ? (
        <div
          className="markdown-body"
          /* eslint-disable-next-line react/no-danger */
          dangerouslySetInnerHTML={{ __html: renderMarkdown(readme.content ?? "") }}
        />
      ) : (
        <p className="text-sm text-muted">
          {STATUS_MESSAGES[readme.status] ?? "No profile README available."}
        </p>
      )}
    </section>
  );
}
