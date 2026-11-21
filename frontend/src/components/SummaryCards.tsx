import { SENTIMENTS, SENTIMENT_LABELS, plural } from "../format";
import type { Summary } from "../types";
import SentimentBar from "./SentimentBar";

interface Props {
  summary: Summary;
  onShowNeedsReply: () => void;
}

export default function SummaryCards({ summary, onShowNeedsReply }: Props) {
  const notAnalysed = [
    summary.skipped_empty > 0 && `${summary.skipped_empty} empty`,
    summary.duplicates > 0 && plural(summary.duplicates, "duplicate"),
    summary.failed > 0 && `${summary.failed} failed`,
  ].filter(Boolean);

  return (
    <div className="stat-grid">
      <div className="card stat-card">
        <span className="stat-label">Reviews analysed</span>
        <span className="stat-value">{summary.analysed}</span>
        <span className="stat-sub">
          of {plural(summary.total_rows, "row")}
          {notAnalysed.length > 0 && ` · ${notAnalysed.join(" · ")}`}
        </span>
        <SentimentBar counts={summary.sentiment} />
      </div>

      {SENTIMENTS.map((sentiment) => (
        <div key={sentiment} className={`card stat-card tone-${sentiment}`}>
          <span className="stat-label">{SENTIMENT_LABELS[sentiment]}</span>
          <span className="stat-value">{summary.sentiment_percent[sentiment]}%</span>
          <span className="stat-sub">{plural(summary.sentiment[sentiment], "review")}</span>
        </div>
      ))}

      <button type="button" className="card stat-card tone-accent" onClick={onShowNeedsReply}>
        <span className="stat-label">Need a reply</span>
        <span className="stat-value">{summary.needs_reply}</span>
        <span className="stat-sub">Show them in the table ↓</span>
      </button>
    </div>
  );
}
