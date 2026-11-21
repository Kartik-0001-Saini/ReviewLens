import { Fragment, useMemo, useState } from "react";
import { suggestReply } from "../api";
import { FLAG_LABELS, SENTIMENTS, SENTIMENT_LABELS, TOPIC_LABELS, plural } from "../format";
import type { ReviewResult, Sentiment, Topic } from "../types";

export interface Filters {
  product: string;
  sentiment: Sentiment | "";
  topic: Topic | "";
  needsReplyOnly: boolean;
}

export const NO_FILTERS: Filters = { product: "", sentiment: "", topic: "", needsReplyOnly: false };

type ReplyState =
  | { status: "loading" }
  | { status: "done"; reply: string; cached: boolean }
  | { status: "error"; message: string };

interface Props {
  reviews: ReviewResult[];
  filters: Filters;
  onFiltersChange: (filters: Filters) => void;
  showProduct?: boolean;
}

export default function ReviewTable({ reviews, filters, onFiltersChange, showProduct = true }: Props) {
  const [replies, setReplies] = useState<Record<string, ReplyState>>({});
  const products = useMemo(() => [...new Set(reviews.map((review) => review.product))], [reviews]);
  const visible = reviews.filter((review) => matchesFilters(review, filters));
  // Duplicates are listed (so they are visible) but not counted in the summary cards.
  const visibleDuplicates = visible.filter((review) => review.status === "duplicate").length;
  const isFiltered = JSON.stringify(filters) !== JSON.stringify(NO_FILTERS);
  const columnCount = showProduct ? 7 : 6;

  const update = (patch: Partial<Filters>) => onFiltersChange({ ...filters, ...patch });
  const setReply = (reviewId: string, state: ReplyState | null) =>
    setReplies((current) => {
      const next = { ...current };
      if (state) next[reviewId] = state;
      else delete next[reviewId];
      return next;
    });

  // Generated on click only, never upfront. The server looks the review up by its hash.
  async function requestReply(review: ReviewResult) {
    setReply(review.review_id, { status: "loading" });
    try {
      const result = await suggestReply(review.text_hash);
      setReply(review.review_id, { status: "done", ...result });
    } catch (err) {
      setReply(review.review_id, { status: "error", message: err instanceof Error ? err.message : "Failed." });
    }
  }

  return (
    <>
      <div className="filters">
        {showProduct && (
          <label>
            Product
            <select value={filters.product} onChange={(event) => update({ product: event.target.value })}>
              <option value="">All products</option>
              {products.map((product) => (
                <option key={product} value={product}>
                  {product}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Sentiment
          <select
            value={filters.sentiment}
            onChange={(event) => update({ sentiment: event.target.value as Filters["sentiment"] })}
          >
            <option value="">All</option>
            {SENTIMENTS.map((sentiment) => (
              <option key={sentiment} value={sentiment}>
                {SENTIMENT_LABELS[sentiment]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Topic
          <select value={filters.topic} onChange={(event) => update({ topic: event.target.value as Filters["topic"] })}>
            <option value="">All</option>
            {Object.entries(TOPIC_LABELS).map(([topic, label]) => (
              <option key={topic} value={topic}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <input
            type="checkbox"
            checked={filters.needsReplyOnly}
            onChange={(event) => update({ needsReplyOnly: event.target.checked })}
          />
          Needs reply only
        </label>
        {isFiltered && (
          <button type="button" className="btn btn-small" onClick={() => onFiltersChange(NO_FILTERS)}>
            Clear filters
          </button>
        )}
        <span className="count">
          Showing {visible.length} of {reviews.length}
          {visibleDuplicates > 0 && ` · includes ${plural(visibleDuplicates, "duplicate")}`}
        </span>
      </div>

      <div className="card table-wrap">
        <table className="reviews">
          <thead>
            <tr>
              <th>ID</th>
              {showProduct && <th>Product</th>}
              <th>Rating</th>
              <th>Review</th>
              <th>Sentiment</th>
              <th>Topics</th>
              <th>Reply</th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 && (
              <tr>
                <td colSpan={columnCount} className="no-results">
                  No reviews match these filters.
                </td>
              </tr>
            )}
            {visible.map((review) => {
              const reply = replies[review.review_id];
              return (
                <Fragment key={review.review_id}>
                  <tr className={review.analysis ? undefined : "dimmed"}>
                    <td className="col-id">{review.review_id}</td>
                    {showProduct && <td className="col-product">{review.product}</td>}
                    <td className="col-rating">
                      <Rating review={review} />
                    </td>
                    <td className="col-review">
                      <ReviewCell review={review} />
                    </td>
                    <td>
                      {review.analysis ? (
                        <span className={`pill pill-${review.analysis.sentiment}`}>
                          {SENTIMENT_LABELS[review.analysis.sentiment]}
                        </span>
                      ) : (
                        <span className="muted">–</span>
                      )}
                    </td>
                    <td>
                      <div className="chips">
                        {review.analysis?.topics.map((topic) => (
                          <span key={topic} className="chip">
                            {TOPIC_LABELS[topic]}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>
                      {review.analysis?.needs_reply && (
                        <ReplyButton
                          state={reply}
                          onRequest={() => requestReply(review)}
                          onHide={() => setReply(review.review_id, null)}
                        />
                      )}
                    </td>
                  </tr>
                  {reply && reply.status !== "loading" && (
                    <tr className="reply-row">
                      <td colSpan={columnCount}>
                        <ReplyBox state={reply} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

function matchesFilters(review: ReviewResult, filters: Filters): boolean {
  const analysis = review.analysis;
  if (filters.product && review.product !== filters.product) return false;
  if (filters.sentiment && analysis?.sentiment !== filters.sentiment) return false;
  if (filters.topic && !analysis?.topics.includes(filters.topic)) return false;
  if (filters.needsReplyOnly && !analysis?.needs_reply) return false;
  return true;
}

function Rating({ review }: { review: ReviewResult }) {
  if (review.rating !== null) {
    return (
      <span className="stars" title={`${review.rating} out of 5`} aria-label={`${review.rating} out of 5`}>
        {"★".repeat(review.rating)}
        <span className="stars-off">{"★".repeat(5 - review.rating)}</span>
      </span>
    );
  }
  return (
    <span className="badge badge-warn" title="Missing or invalid ratings are treated as unknown">
      {review.rating_raw ? `Unknown ("${review.rating_raw}")` : "Unknown"}
    </span>
  );
}

function ReviewCell({ review }: { review: ReviewResult }) {
  const badges: { label: string; tone: string; title?: string }[] = [];
  if (review.status === "skipped_empty") badges.push({ label: "Skipped: empty review", tone: "" });
  if (review.status === "duplicate") {
    badges.push({ label: `Duplicate of ${review.duplicate_of}`, tone: "badge-info", title: "Same text: analysed once" });
  }
  if (review.status === "analysis_failed") badges.push({ label: "Analysis failed", tone: "badge-danger" });
  if (review.rating_mismatch) {
    badges.push({ label: "Rating mismatch", tone: "badge-warn", title: "Stars and text point in opposite directions" });
  }
  for (const flag of review.flags) {
    if (flag === "rating_missing" || flag === "rating_invalid") continue; // shown in the rating column
    badges.push({ label: FLAG_LABELS[flag] ?? flag, tone: flag === "possible_injection" ? "badge-danger" : "" });
  }

  return (
    <>
      {review.text ? <p className="review-text">{review.text}</p> : <p className="review-text empty">(no text)</p>}
      {review.analysis && (
        <p className="ai-summary">
          <b>AI summary:</b> {review.analysis.summary}
        </p>
      )}
      {review.failure_reason && <p className="ai-summary">Reason: {review.failure_reason}</p>}
      {badges.length > 0 && (
        <div className="badges">
          {badges.map((badge) => (
            <span key={badge.label} className={`badge ${badge.tone}`} title={badge.title}>
              {badge.label}
            </span>
          ))}
        </div>
      )}
    </>
  );
}

interface ReplyButtonProps {
  state: ReplyState | undefined;
  onRequest: () => void;
  onHide: () => void;
}

function ReplyButton({ state, onRequest, onHide }: ReplyButtonProps) {
  if (state?.status === "loading") {
    return (
      <button type="button" className="btn btn-small" disabled>
        Writing…
      </button>
    );
  }
  if (state?.status === "done") {
    return (
      <button type="button" className="btn btn-small" onClick={onHide}>
        Hide reply
      </button>
    );
  }
  return (
    <button type="button" className="btn btn-small btn-primary" onClick={onRequest}>
      {state?.status === "error" ? "Try again" : "Suggest reply"}
    </button>
  );
}

function ReplyBox({ state }: { state: Exclude<ReplyState, { status: "loading" }> }) {
  const [copied, setCopied] = useState(false);

  if (state.status === "error") {
    return <p className="error">{state.message}</p>;
  }

  async function copy() {
    if (state.status !== "done") return;
    try {
      await navigator.clipboard.writeText(state.reply);
      setCopied(true);
    } catch {
      setCopied(false); // clipboard blocked: the text is still visible to copy by hand
    }
  }

  return (
    <div className="reply-box">
      <div>
        <div className="reply-label">Suggested reply{state.cached && " · from cache"}</div>
        <p>{state.reply}</p>
      </div>
      <button type="button" className="btn btn-small" onClick={copy}>
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
