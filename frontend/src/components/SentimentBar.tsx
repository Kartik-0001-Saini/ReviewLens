import { SENTIMENTS } from "../format";
import type { SentimentCounts } from "../types";

export default function SentimentBar({ counts }: { counts: SentimentCounts }) {
  const total = counts.positive + counts.neutral + counts.negative;
  const share = (count: number) => (total ? (100 * count) / total : 0);
  const description = total
    ? SENTIMENTS.map((s) => `${Math.round(share(counts[s]))}% ${s}`).join(", ")
    : "No analysed reviews";

  return (
    <div className="sentiment-bar" role="img" aria-label={description} title={description}>
      {SENTIMENTS.map(
        (s) => counts[s] > 0 && <span key={s} className={`seg-${s}`} style={{ width: `${share(counts[s])}%` }} />,
      )}
    </div>
  );
}
