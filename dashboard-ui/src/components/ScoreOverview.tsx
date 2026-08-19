import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Filler,
  Tooltip,
  Legend,
} from "chart.js";
import type { TooltipItem } from "chart.js";
import { Radar, Doughnut } from "react-chartjs-2";
import type { ReportResponse, DimensionId } from "../types/report";

ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Filler,
  Tooltip,
  Legend,
);

const DIMENSION_LABELS: Record<DimensionId, string> = {
  presence: "Presence",
  code_quality: "Code Quality",
  activity: "Activity",
  engagement: "Engagement",
  documentation: "Documentation",
  open_source: "Open Source",
  consistency: "Consistency",
  contribution: "Contribution",
  visibility: "Visibility",
};

const LANGUAGE_COLORS = [
  "#58a6ff", "#3fb950", "#d29922", "#f85149", "#bc8cff",
  "#79c0ff", "#56d364", "#e3b341", "#ffa198", "#d2a8ff",
  "#9ecbff", "#7ee787", "#f0cc53", "#ff9bce", "#e2c5ff",
];

interface ScoreOverviewProps {
  report: ReportResponse;
}

export function ScoreOverview({ report }: ScoreOverviewProps) {
  const { profile } = report;
  const overall = profile.overall?.overall ?? 0;

  const labels = profile.scores.map((s) => DIMENSION_LABELS[s.dimension]);
  const values = profile.scores.map((s) => s.score);

  const radarData = {
    labels,
    datasets: [
      {
        label: "Score",
        data: values,
        backgroundColor: "rgba(88, 166, 255, 0.2)",
        borderColor: "rgba(88, 166, 255, 0.8)",
        borderWidth: 2,
        pointBackgroundColor: "rgba(88, 166, 255, 1)",
        pointRadius: 4,
      },
    ],
  };

  const radarOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      r: {
        beginAtZero: true,
        max: 100,
        ticks: { display: false },
        grid: { color: "rgba(48, 54, 61, 0.6)" },
        angleLines: { color: "rgba(48, 54, 61, 0.6)" },
        pointLabels: { color: "#e6edf3", font: { size: 12 } },
      },
    },
    plugins: {
      tooltip: {
        callbacks: {
          label: (ctx: TooltipItem<"radar">) => `${(ctx.parsed.r ?? 0)}/100`,
        },
      },
    },
  };

  const languages = profile.analyses?.languages;
  const langDistribution = languages?.distribution?.slice(0, 8) ?? [];
  const hasLanguageChart = langDistribution.length > 0;

  const donutData = hasLanguageChart
    ? {
        labels: langDistribution.map((l) => l.language),
        datasets: [
          {
            data: langDistribution.map((l) => l.share * 100),
            backgroundColor: langDistribution.map(
              (_, i) => LANGUAGE_COLORS[i % LANGUAGE_COLORS.length],
            ),
            borderColor: "#161b22",
            borderWidth: 2,
          },
        ],
      }
    : null;

  const donutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "55%",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx: TooltipItem<"doughnut">) =>
            `${ctx.label}: ${(ctx.parsed ?? 0).toFixed(1)}%`,
        },
      },
    },
  };

  return (
    <div className="bg-panel rounded-lg border border-border p-6">
      <div className="flex items-center gap-6 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-text">
            @{profile.username}
          </h2>
          <p className="text-muted text-sm">
            Analyzed {new Date(profile.analyzed_at).toLocaleDateString()}
          </p>
        </div>
        <div className="ml-auto text-center">
          <div
            className={`text-5xl font-bold ${
              overall >= 70
                ? "text-good"
                : overall >= 40
                  ? "text-warn"
                  : "text-bad"
            }`}
          >
            {Math.round(overall)}
          </div>
          <div className="text-muted text-sm">/100</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Radar chart — 2 columns */}
        <div className="lg:col-span-2 h-80">
          <Radar data={radarData} options={radarOptions} />
        </div>

        {/* Language donut — 1 column */}
        {hasLanguageChart && donutData && (
          <div className="bg-bg/50 rounded-lg p-4 border border-border">
            <h3 className="text-sm font-medium text-muted mb-3">Languages</h3>
            <div className="h-52">
              <Doughnut data={donutData} options={donutOptions} />
            </div>
            <div className="mt-3 space-y-1">
              {langDistribution.slice(0, 5).map((l, i) => (
                <div key={l.language} className="flex items-center gap-2 text-xs">
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: LANGUAGE_COLORS[i % LANGUAGE_COLORS.length] }}
                  />
                  <span className="text-text truncate">{l.language}</span>
                  <span className="ml-auto text-muted">{(l.share * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {(profile.overall?.strengths?.length ?? 0) > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-4">
          <div>
            <h3 className="text-sm font-medium text-good mb-2">Strengths</h3>
            <ul className="space-y-1">
              {profile.overall!.strengths.map((s, i) => (
                <li key={i} className="text-sm text-muted">
                  {s}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="text-sm font-medium text-bad mb-2">Weaknesses</h3>
            <ul className="space-y-1">
              {profile.overall!.weaknesses.map((w, i) => (
                <li key={i} className="text-sm text-muted">
                  {w}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
