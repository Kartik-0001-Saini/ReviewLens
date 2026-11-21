import { formatSeconds } from "../format";
import type { RatingCheck, RunLog } from "../types";

interface Props {
  run: RunLog;
  ratingCheck: RatingCheck;
}

export default function RunLogCard({ run, ratingCheck }: Props) {
  return (
    <div className="card runlog">
      <h3>Cost and speed</h3>
      <dl>
        <dt>AI calls made</dt>
        <dd>{run.ai_calls}</dd>
        <dt>Reviews served from cache</dt>
        <dd>
          {run.cache_hits} of {run.unique_reviews}
        </dd>
        <dt>Reviews sent to the AI</dt>
        <dd>{run.sent_to_ai}</dd>
        <dt>Rate-limit retries (backoff)</dt>
        <dd>{run.rate_limit_retries}</dd>
        <dt>Invalid AI answers retried</dt>
        <dd>{run.validation_retries}</dd>
        <dt>Analysis failed</dt>
        <dd>{run.failed}</dd>
      </dl>
      <dl>
        <dt>Processing time</dt>
        <dd>{formatSeconds(run.elapsed_ms)}</dd>
        <dt>Model</dt>
        <dd>{run.model}</dd>
      </dl>

      <div className="agreement">
        <strong>
          Stars vs. text: {ratingCheck.agreement_percent === null ? "n/a" : `${ratingCheck.agreement_percent}% agree`}
        </strong>{" "}
        ({ratingCheck.agreeing} of {ratingCheck.compared} rated reviews).
        {ratingCheck.mismatched_ids.length > 0 && (
          <>
            {" "}
            Opposite signals:{" "}
            {ratingCheck.mismatched_ids.map((id) => (
              <span key={id} className="id-chip">
                {id}
              </span>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
