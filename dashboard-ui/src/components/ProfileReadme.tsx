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
marked.use({ gfm: true, breaks: false });

const FORBIDDEN_TAGS = [
  "applet",
  "base",
  "button",
  "embed",
  "form",
  "frame",
  "frameset",
  "iframe",
  "link",
  "meta",
  "object",
  "script",
  "select",
  "style",
  "textarea",
  "title",
];
const FORBIDDEN_ATTRIBUTES = ["action", "formaction", "style", "srcdoc"];

function hasUrlScheme(value: string): boolean {
  return /^[a-zA-Z][a-zA-Z\d+.-]*:/.test(value);
}

function isExternalHttpUrl(value: string): boolean {
  return value.startsWith("//") || /^https?:\/\//i.test(value);
}

function isRelativeReadmeUrl(value: string | null): value is string {
  if (!value) return false;
  const trimmed = value.trim();
  if (!trimmed) return false;
  if (trimmed.startsWith("#") || trimmed.startsWith("/") || trimmed.startsWith("//")) {
    return false;
  }
  return !hasUrlScheme(trimmed);
}

function splitUrlSuffix(url: string): { path: string; suffix: string } {
  const query = url.indexOf("?");
  const hash = url.indexOf("#");
  let cut = url.length;
  if (query !== -1) cut = Math.min(cut, query);
  if (hash !== -1) cut = Math.min(cut, hash);
  return { path: url.slice(0, cut), suffix: url.slice(cut) };
}

function cleanRelativePath(path: string): string | null {
  let clean = path.trim();
  while (clean.startsWith("./")) {
    clean = clean.slice(2);
  }
  clean = clean.replace(/^\/+/, "");
  if (!clean || clean === "." || clean.startsWith("../") || clean.includes("/../")) {
    return null;
  }
  return clean;
}

function splitRepository(repository: string | null | undefined): [string, string] | null {
  if (!repository) return null;
  const [owner, repo] = repository.split("/");
  if (!owner || !repo) return null;
  return [owner, repo];
}

function resolveReadmeAssetUrl(
  url: string,
  repository: string | null | undefined,
): string | null {
  const parts = splitRepository(repository);
  if (!parts) return null;
  const { path, suffix } = splitUrlSuffix(url);
  const clean = cleanRelativePath(path);
  if (!clean) return null;
  return `https://raw.githubusercontent.com/${parts[0]}/${parts[1]}/HEAD/${clean}${suffix}`;
}

function resolveReadmeLinkUrl(
  url: string,
  repository: string | null | undefined,
): string | null {
  const parts = splitRepository(repository);
  if (!parts) return null;
  const { path, suffix } = splitUrlSuffix(url);
  const clean = cleanRelativePath(path);
  if (!clean) return null;
  return `https://github.com/${parts[0]}/${parts[1]}/blob/HEAD/${clean}${suffix}`;
}

function rewriteSrcset(
  value: string,
  repository: string | null | undefined,
): string | null {
  const rewritten = value
    .split(",")
    .map((candidate) => {
      const token = candidate.trim();
      if (!token) return null;
      const [url, ...descriptors] = token.split(/\s+/);
      if (isRelativeReadmeUrl(url)) {
        const resolved = resolveReadmeAssetUrl(url, repository);
        if (!resolved) return null;
        return [resolved, ...descriptors].join(" ");
      }
      return token;
    })
    .filter((candidate): candidate is string => candidate !== null);
  return rewritten.length > 0 ? rewritten.join(", ") : null;
}

function toCssSize(value: string | null): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (/^\d+$/.test(trimmed)) return `${trimmed}px`;
  if (/^\d+%$/.test(trimmed)) return trimmed;
  return null;
}

function rewriteMediaElement(
  element: HTMLImageElement | HTMLSourceElement,
  repository: string | null | undefined,
): void {
  const src = element.getAttribute("src");
  if (src && isRelativeReadmeUrl(src)) {
    const resolved = resolveReadmeAssetUrl(src, repository);
    if (resolved) {
      element.setAttribute("src", resolved);
    } else {
      element.removeAttribute("src");
    }
  }

  const srcset = element.getAttribute("srcset");
  if (srcset) {
    const rewritten = rewriteSrcset(srcset, repository);
    if (rewritten) {
      element.setAttribute("srcset", rewritten);
    } else {
      element.removeAttribute("srcset");
    }
  }

  // Tailwind's preflight (`img { height: auto }`) overrides presentational
  // width/height attributes, which blows viewBox-only SVGs up to full width.
  // Mirror GitHub by promoting valid dimensions to inline styles.
  if (element instanceof HTMLImageElement) {
    const width = toCssSize(element.getAttribute("width"));
    if (width) element.style.width = width;
    const height = toCssSize(element.getAttribute("height"));
    if (height) element.style.height = height;
  }
}

function rewriteAnchor(
  element: HTMLAnchorElement,
  repository: string | null | undefined,
): void {
  const href = element.getAttribute("href");
  if (!href) return;
  if (isRelativeReadmeUrl(href)) {
    const resolved = resolveReadmeLinkUrl(href, repository);
    if (resolved) {
      element.setAttribute("href", resolved);
    } else {
      element.removeAttribute("href");
      return;
    }
  }

  const finalHref = element.getAttribute("href") ?? "";
  if (isExternalHttpUrl(finalHref)) {
    element.setAttribute("target", "_blank");
    const rel = new Set(
      (element.getAttribute("rel") ?? "").split(/\s+/).filter((token) => token !== ""),
    );
    rel.add("noopener");
    rel.add("noreferrer");
    element.setAttribute("rel", [...rel].join(" "));
  }
}

function renderMarkdown(source: string, repository: string | null | undefined): string {
  const html = marked.parse(source, { async: false }) as string;
  const rewriteReadmeUrls = (node: Element): void => {
    if (node instanceof HTMLImageElement || node instanceof HTMLSourceElement) {
      rewriteMediaElement(node, repository);
    }
    if (node instanceof HTMLAnchorElement) {
      rewriteAnchor(node, repository);
    }
    node.querySelectorAll("img, source, a").forEach((child) => {
      if (child instanceof HTMLImageElement || child instanceof HTMLSourceElement) {
        rewriteMediaElement(child, repository);
      } else if (child instanceof HTMLAnchorElement) {
        rewriteAnchor(child, repository);
      }
    });
  };

  DOMPurify.addHook("afterSanitizeAttributes", rewriteReadmeUrls);
  try {
    return DOMPurify.sanitize(html, {
      USE_PROFILES: { html: true, svg: true, svgFilters: true },
      ADD_ATTR: ["target"],
      FORBID_TAGS: FORBIDDEN_TAGS,
      FORBID_ATTR: FORBIDDEN_ATTRIBUTES,
    });
  } finally {
    DOMPurify.removeHook("afterSanitizeAttributes");
  }
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
          dangerouslySetInnerHTML={{ __html: renderMarkdown(readme.content ?? "", readme.repository) }}
        />
      ) : (
        <p className="text-sm text-muted">
          {STATUS_MESSAGES[readme.status] ?? "No profile README available."}
        </p>
      )}
    </section>
  );
}
