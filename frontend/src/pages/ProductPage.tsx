import { useState } from "react";
import { Link, useParams } from "react-router";
import ReviewTable, { NO_FILTERS } from "../components/ReviewTable";
import type { Filters } from "../components/ReviewTable";
import SentimentBar from "../components/SentimentBar";
import { SENTIMENTS, SENTIMENT_LABELS, TOPIC_LABELS, plural } from "../format";
import type { AnalyzeResponse, ReviewResult, Topic } from "../types";

export default function ProductPage({ result }: { result: AnalyzeResponse }) {
  const { name = "" } = useParams();
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const stats = result.products.find((product) => product.product === name);

  if (!stats) {
    return (
      <div className="card">
        <p>There is no product called “{name}” in this file.</p>
        <Link to="/">← Back to the dashboard</Link>
      </div>
    );
  }

  const reviews = result.reviews.filter((review) => review.product === name);

  return (
    <>
      <Link to="/" className="back-link">
        ← All products
      </Link>
      <h1 className="page-title">{name}</h1>
      <p className="muted">
        {plural(stats.analysed, "review")} analysed out of {plural(stats.total_rows, "row")} · {stats.needs_reply} need a
        reply
      </p>

      <div className="section two-columns">
        <div className="card">
          <h3>Sentiment split</h3>
          <div className="split-stats">
            {SENTIMENTS.map((sentiment) => (
              <div key={sentiment} className={`stat-card tone-${sentiment}`}>
                <span className="stat-value">{percentOf(stats.sentiment[sentiment], stats.analysed)}%</span>
                <span className="stat-sub">
                  {SENTIMENT_LABELS[sentiment]} · {plural(stats.sentiment[sentiment], "review")}
                </span>
              </div>
            ))}
          </div>
          <SentimentBar counts={stats.sentiment} />
        </div>
        <div className="card">
          <h3>Top issues</h3>
          {stats.top_issues.length === 0 ? (
            <p className="empty-note">No complaints about this product.</p>
          ) : (
            <ol className="issue-list">
              {stats.top_issues.map((issue) => (
                <li key={issue.topic}>
                  <div>
                    <strong>{TOPIC_LABELS[issue.topic]}</strong>
                    {complaintSummaries(reviews, issue.topic).map((summary) => (
                      <div key={summary} className="muted small">
                        {summary}
                      </div>
                    ))}
                  </div>
                  <span className="muted">{plural(issue.count, "review")}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>

      <section className="section">
        <div className="section-head">
          <h2 className="section-title">Reviews</h2>
        </div>
        <ReviewTable reviews={reviews} filters={filters} onFiltersChange={setFilters} showProduct={false} />
      </section>
    </>
  );
}

function percentOf(part: number, whole: number): number {
  return whole ? Math.round((100 * part) / whole) : 0;
}

/** AI summaries of this product's complaints about one topic (same rule as the backend's top issues). */
function complaintSummaries(reviews: ReviewResult[], topic: Topic): string[] {
  return reviews
    .filter((review) => review.status === "analysed" && review.analysis)
    .filter(({ analysis }) => analysis!.topics.includes(topic))
    .filter(({ analysis }) => analysis!.needs_reply || analysis!.sentiment === "negative")
    .map(({ analysis }) => analysis!.summary);
}
