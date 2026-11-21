import type { Sentiment, Topic } from "./types";

export const SENTIMENTS: Sentiment[] = ["positive", "neutral", "negative"];

export const TOPIC_LABELS: Record<Topic, string> = {
  quality: "Quality",
  delivery: "Delivery",
  price: "Price",
  packaging: "Packaging",
  support: "Support",
  size_fit: "Size & fit",
  other: "Other",
};

export const SENTIMENT_LABELS: Record<Sentiment, string> = {
  positive: "Positive",
  neutral: "Neutral",
  negative: "Negative",
};

// Flags set by the CSV cleaner (backend/app/csv_cleaner.py).
export const FLAG_LABELS: Record<string, string> = {
  rating_missing: "No rating",
  rating_invalid: "Invalid rating",
  date_missing: "No date",
  date_invalid: "Invalid date",
  html_removed: "HTML removed",
  possible_injection: "Injection attempt",
  extra_columns_merged: "Broken row repaired",
  missing_id: "No review ID",
};

export function productPath(product: string): string {
  return `/products/${encodeURIComponent(product)}`;
}

export function formatSeconds(ms: number): string {
  return `${(ms / 1000).toFixed(1)}s`;
}

export function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}
