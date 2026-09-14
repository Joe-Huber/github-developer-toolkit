export interface ReportResponse {
  tool_version: string;
  generated_at: string;
  profile: ProfileAnalysis;
}

export interface ProfileAnalysis {
  username: string;
  analyzed_at: string;
  schema_version: number;
  identity: ProfileIdentity | null;
  top_stats: ProfileTopStats | null;
  analyses: ProfileAnalyses | null;
  metrics: MetricRecord[];
  scores: DimensionScore[];
  overall: OverallScore | null;
  findings: Finding[];
  recommendations: Recommendation[];
  synthesis: Synthesis | null;
}

export interface ProfileIdentity {
  username: string;
  name: string | null;
  avatar_url: string | null;
  html_url: string | null;
  bio: string | null;
  company: string | null;
  blog: string | null;
  location: string | null;
  email: string | null;
  twitter_username: string | null;
  hireable: boolean | null;
  public_repos: number | null;
  public_gists: number | null;
  followers: number | null;
  following: number | null;
  created_at: string | null;
  updated_at: string | null;
  availability: MetricAvailability;
}

export interface ProfileTopStats {
  username: string;
  metrics: MetricRecord[];
  top_repositories: TopRepository[];
  top_languages: TopLanguage[];
  sources: SourceReference[];
  availability: MetricAvailability;
}

export interface TopRepository {
  name: string;
  full_name: string;
  stargazers_count: number;
  description: string | null;
  html_url: string | null;
  language: string | null;
}

export interface TopLanguage {
  language: string;
  bytes: number;
  share: number;
}

export interface ProfileAnalyses {
  presence: ProfilePresence | null;
  readme: ReadmeAssessment | null;
  repository_quality: RepositoryQuality | null;
  repository_activity: RepositoryActivity | null;
  portfolio: PortfolioComposition | null;
  stars: StarsAnalysis | null;
  star_growth: StarGrowthAnalysis | null;
  network: FollowerNetwork | null;
  commits: CommitActivity | null;
  contribution_calendar: ContributionCalendarAnalysis | null;
  pull_requests: PullRequestAnalysis | null;
  issues: IssueParticipationAnalysis | null;
  languages: LanguageDistributionAnalysis | null;
  technology: TechnologyDiversityAnalysis | null;
}

export type DimensionId =
  | "presence"
  | "code_quality"
  | "activity"
  | "engagement"
  | "documentation"
  | "open_source"
  | "consistency"
  | "contribution"
  | "visibility";

export interface OverallScore {
  overall: number;
  contributions: DimensionContribution[];
  strengths: string[];
  weaknesses: string[];
}

export interface DimensionContribution {
  dimension: DimensionId;
  score: number;
  weight: number;
  contribution: number;
}

export interface DimensionScore {
  dimension: DimensionId;
  score: number;
  weight: number;
  rationale: string | null;
  breakdown: ScoreBreakdown[];
}

export interface ScoreBreakdown {
  component_id: string;
  label: string;
  weight: number;
  contribution: number;
  metric_id: string | null;
  sources: SourceReference[];
}

export type FindingSeverity = "info" | "low" | "medium" | "high" | "critical";

export interface Finding {
  id: string;
  type: string;
  severity: FindingSeverity;
  title: string;
  message: string;
  dimension: DimensionId | null;
  evidence: SourceReference[];
  recommendation_ids: string[];
}

export type RecommendationPriority = "high" | "medium" | "low";
export type RecommendationEffort = "low" | "medium" | "high";

export interface Recommendation {
  id: string;
  priority: RecommendationPriority;
  action: string;
  rationale: string;
  template_id: string;
  severity: FindingSeverity | null;
  effort: RecommendationEffort;
  finding_ids: string[];
  metric_ids: string[];
  sources: SourceReference[];
}

export interface MetricRecord {
  id: string;
  label: string;
  value: MetricValue;
  sources: SourceReference[];
  timestamp: string;
  confidence: number;
  availability: MetricAvailability;
}

export type MetricValue = number | string | boolean | null;
export type MetricAvailability = "available" | "partial" | "unavailable";

export interface Synthesis {
  strengths: string[];
  weaknesses: string[];
  red_flags: string[];
  plan: Recommendation[];
}

export interface SourceReference {
  entity: string;
  identifier: string;
  field: string | null;
}

// Placeholder types for individual analyses (subset of fields shown)
export interface ProfilePresence {
  metrics: MetricRecord[];
  findings: Finding[];
}

export interface ReadmeAssessment {
  username: string;
  status: string;
  metrics: MetricRecord[];
  findings: Finding[];
  content: string | null;
  repository: string | null;
}

export interface RepositoryQuality {
  metrics: MetricRecord[];
  findings: Finding[];
}

export interface RepositoryActivity {
  metrics: MetricRecord[];
  findings: Finding[];
}

export interface PortfolioComposition {
  metrics: MetricRecord[];
  findings: Finding[];
}

export interface StarsAnalysis {
  metrics: MetricRecord[];
  findings: Finding[];
}

export interface StarGrowthAnalysis {
  metrics: MetricRecord[];
  findings: Finding[];
}

export interface FollowerNetwork {
  metrics: MetricRecord[];
  findings: Finding[];
}

export interface CommitActivity {
  metrics: MetricRecord[];
  findings: Finding[];
}

export interface ContributionCalendarAnalysis {
  metrics: MetricRecord[];
  findings: Finding[];
}

export interface PullRequestAnalysis {
  metrics: MetricRecord[];
  findings: Finding[];
}

export interface IssueParticipationAnalysis {
  metrics: MetricRecord[];
  findings: Finding[];
}

export interface LanguageDistributionAnalysis {
  metrics: MetricRecord[];
  findings: Finding[];
  distribution: LanguageShare[];
  dominant_language: string | null;
  dominant_share: number | null;
  distinct_languages: number;
  total_bytes: number;
}

export interface LanguageShare {
  language: string;
  bytes: number;
  share: number;
}

export interface TechnologyDiversityAnalysis {
  metrics: MetricRecord[];
  findings: Finding[];
}
