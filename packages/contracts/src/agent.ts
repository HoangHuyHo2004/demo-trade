export interface SourceCitation {
  title: string;
  publisher: string;
  url?: string | null;
  published_at?: string | null;
  retrieved_at?: string | null;
  kind: "system" | "filing" | "disclosure" | "news" | "project" | "quantitative";
  asset_canonical_id?: string | null;
}

export interface ResearchResponse {
  asset_canonical_id: string | null;
  executive_summary: string;
  current_trend: string;
  signal_summary: string;
  bull_case: string[];
  bear_case: string[];
  key_risks: string[];
  upcoming_catalysts: string[];
  data_quality_warnings: string[];
  verified_facts: string[];
  interpretation: string[];
  assumptions: string[];
  unknowns: string[];
  suggested_questions: string[];
  citations: SourceCitation[];
  abstained: boolean;
  abstention_reason: string;
}

export interface AgentChatResponse {
  run_id: number;
  status: "ok" | "abstained" | "budget_exceeded" | "error";
  response: ResearchResponse;
}
