// Mirrors backend/app/api_models.py and backend/app/schemas.py.

export type Sentiment = "positive" | "neutral" | "negative";
export type Topic = "quality" | "delivery" | "price" | "packaging" | "support" | "size_fit" | "other";
export type ReviewStatus = "analysed" | "analysis_failed" | "skipped_empty" | "duplicate";

export interface ReviewAnalysis {
  sentiment: Sentiment;
  topics: Topic[];
  summary: string;
  needs_reply: boolean;
}

export interface ReviewResult {
  review_id: string;
  product: string;
  rating: number | null;
  rating_raw: string;
  date: string | null;
  text: string;
  text_hash: string;
  status: ReviewStatus;
  duplicate_of: string | null;
  flags: string[];
  analysis: ReviewAnalysis | null;
  failure_reason: string | null;
  rating_mismatch: boolean;
}

export type SentimentCounts = Record<Sentiment, number>;

export interface Summary {
  total_rows: number;
  analysed: number;
  skipped_empty: number;
  duplicates: number;
  failed: number;
  needs_reply: number;
  sentiment: SentimentCounts;
  sentiment_percent: SentimentCounts;
}

export interface InsightTheme {
  title: string;
  count: number;
  review_ids: string[];
}

export interface Insights {
  complaints: InsightTheme[];
  praises: InsightTheme[];
  source: "ai" | "topic_counts" | "none";
}

export interface RatingCheck {
  compared: number;
  agreeing: number;
  agreement_percent: number | null;
  mismatched_ids: string[];
}

export interface ProductStats {
  product: string;
  total_rows: number;
  analysed: number;
  needs_reply: number;
  sentiment: SentimentCounts;
  top_issues: { topic: Topic; count: number }[];
}

export interface RunLog {
  model: string;
  unique_reviews: number;
  cache_hits: number;
  sent_to_ai: number;
  ai_calls: number;
  rate_limit_retries: number;
  validation_retries: number;
  failed: number;
  elapsed_ms: number;
}

export interface AnalyzeResponse {
  reviews: ReviewResult[];
  summary: Summary;
  insights: Insights;
  rating_check: RatingCheck;
  products: ProductStats[];
  run: RunLog;
}

export interface ReplyResult {
  reply: string;
  cached: boolean;
}
