import type { ProfileTopStats } from "../types/report";
import { formatMetricValue } from "../lib/metrics";
import { StarIcon } from "./icons";

const AVAILABILITY_STYLES: Record<string, string> = {
  available: "bg-good/15 text-good",
  partial: "bg-warn/15 text-warn",
  unavailable: "bg-bad/15 text-bad",
};

interface ProfileStatsProps {
  stats: ProfileTopStats | null;
}

function StatTile({ label, value, availability }: {
  label: string;
  value: number | string | boolean | null;
  availability: string;
}) {
  return (
    <div className="bg-bg/50 border border-border rounded-lg p-3">
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="text-xs text-muted truncate">{label}</span>
        <span
          className={`px-1.5 py-0.5 rounded text-[10px] capitalize shrink-0 ${AVAILABILITY_STYLES[availability] ?? ""}`}
        >
          {availability}
        </span>
      </div>
      <div className="text-base font-semibold text-text">
        {formatMetricValue(value)}
      </div>
    </div>
  );
}

export function ProfileStats({ stats }: ProfileStatsProps) {
  if (stats === null) return null;
  const metrics = stats.metrics ?? [];
  const topRepositories = stats.top_repositories ?? [];
  const topLanguages = stats.top_languages ?? [];

  return (
    <div className="space-y-6">
      <section aria-label="Top statistics" className="bg-panel border border-border rounded-lg p-6">
        <h3 className="text-sm font-semibold text-muted uppercase tracking-wide mb-4">
          Top statistics
        </h3>
        {metrics.length === 0 ? (
          <p className="text-sm text-muted">No statistics collected for this profile.</p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {metrics.map((metric) => (
              <StatTile
                key={metric.id}
                label={metric.label}
                value={metric.value}
                availability={metric.availability}
              />
            ))}
          </div>
        )}
      </section>

      {topRepositories.length > 0 && (
        <section aria-label="Top repositories" className="bg-panel border border-border rounded-lg p-6">
          <h3 className="text-sm font-semibold text-muted uppercase tracking-wide mb-4">
            Top repositories
          </h3>
          <ol className="space-y-3">
            {topRepositories.map((repo) => (
              <li key={repo.full_name} className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <a
                    href={repo.html_url ?? `https://github.com/${repo.full_name}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-medium text-accent hover:underline truncate block"
                  >
                    {repo.full_name}
                  </a>
                  {repo.description && (
                    <p className="text-xs text-muted mt-0.5 line-clamp-2">{repo.description}</p>
                  )}
                  {repo.language && (
                    <span className="inline-block mt-1.5 px-1.5 py-0.5 rounded bg-border/40 text-muted text-[10px]">
                      {repo.language}
                    </span>
                  )}
                </div>
                <span className="inline-flex items-center gap-1 text-xs text-muted shrink-0">
                  <StarIcon className="h-3.5 w-3.5" />
                  {repo.stargazers_count.toLocaleString("en-US")}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {topLanguages.length > 0 && (
        <section aria-label="Languages" className="bg-panel border border-border rounded-lg p-6">
          <h3 className="text-sm font-semibold text-muted uppercase tracking-wide mb-4">
            Languages
          </h3>
          <ul className="space-y-2">
            {topLanguages.map((entry) => (
              <li key={entry.language} className="flex items-center gap-3">
                <span className="text-sm text-text w-24 shrink-0 truncate">{entry.language}</span>
                <div className="relative h-2 flex-1 rounded-full bg-border/40" role="presentation">
                  <div
                    className="absolute inset-y-0 left-0 rounded-full bg-accent/70"
                    style={{ width: `${Math.min(100, entry.share * 100)}%` }}
                  />
                </div>
                <span className="text-xs text-muted w-12 text-right shrink-0">
                  {(entry.share * 100).toFixed(1)}%
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {topRepositories.length === 0 && topLanguages.length === 0 && (
        <p className="sr-only">No repository or language statistics available.</p>
      )}
    </div>
  );
}
