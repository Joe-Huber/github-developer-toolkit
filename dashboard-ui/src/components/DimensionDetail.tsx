import type {
  DimensionId,
  DimensionScore,
  Finding,
  ProfileAnalyses,
  Recommendation,
} from "../types/report";
import { Charts } from "./Charts";
import { FindingsList } from "./FindingsList";
import { MetricsGrid } from "./MetricsGrid";
import { RecommendationsList } from "./RecommendationsList";
import { ScoreGauge } from "./ScoreGauge";
import { ANALYSIS_LABELS, DIMENSION_ANALYSES, DIMENSION_LABELS } from "../lib/dimensions";

interface DimensionDetailProps {
  dimension: DimensionId;
  scores: DimensionScore[];
  findings: Finding[];
  recommendations: Recommendation[];
  analyses: ProfileAnalyses | null;
}

export function DimensionDetail({
  dimension,
  scores,
  findings,
  recommendations,
  analyses,
}: DimensionDetailProps) {
  const score = scores.find((s) => s.dimension === dimension);

  const analysisKeys = analyses ? DIMENSION_ANALYSES[dimension] : [];
  const metricSections = analysisKeys.flatMap((key) => {
    const analysis = analyses?.[key];
    if (!analysis || analysis.metrics.length === 0) return [];
    return [{ key, metrics: analysis.metrics }];
  });

  return (
    <div className="space-y-6">
      <div className="bg-panel rounded-lg border border-border p-6">
        <div className="flex items-center justify-between gap-4 mb-4">
          <h2 className="text-xl font-semibold text-text">
            {DIMENSION_LABELS[dimension] ?? dimension}
          </h2>
          {score && <ScoreGauge value={score.score} size={72} />}
        </div>

        {!score && (
          <p className="text-muted text-sm">
            Not scored independently; see the metrics below for this area.
          </p>
        )}

        {score?.rationale && (
          <p className="text-muted text-sm mb-4">{score.rationale}</p>
        )}

        {score?.breakdown && score.breakdown.length > 0 && (
          <Charts breakdown={score.breakdown} />
        )}

        {metricSections.map(({ key, metrics }) => (
          <div key={key} className="mt-6">
            <h3 className="text-sm font-medium text-muted mb-3">
              {ANALYSIS_LABELS[key]}
            </h3>
            <MetricsGrid metrics={metrics} />
          </div>
        ))}
      </div>

      <FindingsList findings={findings} title="Findings" />
      <RecommendationsList recommendations={recommendations} title="Recommendations" />
    </div>
  );
}
