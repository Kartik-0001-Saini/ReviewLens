import { plural } from "../format";
import type { InsightTheme, Insights } from "../types";

const SOURCE_NOTES: Record<Insights["source"], string> = {
  ai: "Themes named by the AI from the review summaries; review counts checked by ReviewLens.",
  topic_counts: "AI themes were unavailable, so these come from topic counts.",
  none: "",
};

export default function InsightsPanel({ insights }: { insights: Insights }) {
  return (
    <section className="section">
      <div className="section-head">
        <h2 className="section-title">What customers say</h2>
        <span className="muted small">{SOURCE_NOTES[insights.source]}</span>
      </div>
      <div className="two-columns">
        <ThemeCard title="Top complaints" kind="complaints" themes={insights.complaints} empty="No complaints found." />
        <ThemeCard title="Top praises" kind="praises" themes={insights.praises} empty="No praise found." />
      </div>
    </section>
  );
}

interface ThemeCardProps {
  title: string;
  kind: "complaints" | "praises";
  themes: InsightTheme[];
  empty: string;
}

function ThemeCard({ title, kind, themes, empty }: ThemeCardProps) {
  return (
    <div className={`card ${kind}`}>
      <h3>{title}</h3>
      {themes.length === 0 ? (
        <p className="empty-note">{empty}</p>
      ) : (
        <ol className="theme-list">
          {themes.map((theme, index) => (
            <li key={`${index}-${theme.title}`}>
              <span className="rank">{index + 1}</span>
              <span className="theme-title">{theme.title}</span>
              <span className="theme-meta">
                {plural(theme.count, "review")}:
                {theme.review_ids.map((id) => (
                  <span key={id} className="id-chip">
                    {id}
                  </span>
                ))}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
