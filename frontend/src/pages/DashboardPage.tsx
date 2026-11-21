import { useRef, useState } from "react";
import InsightsPanel from "../components/InsightsPanel";
import ProductGrid from "../components/ProductGrid";
import ReviewTable, { NO_FILTERS } from "../components/ReviewTable";
import type { Filters } from "../components/ReviewTable";
import RunLogCard from "../components/RunLogCard";
import SummaryCards from "../components/SummaryCards";
import type { AnalyzeResponse } from "../types";

export default function DashboardPage({ result }: { result: AnalyzeResponse }) {
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const tableSection = useRef<HTMLElement>(null);

  function showNeedsReply() {
    setFilters({ ...NO_FILTERS, needsReplyOnly: true });
    tableSection.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <>
      <SummaryCards summary={result.summary} onShowNeedsReply={showNeedsReply} />

      <InsightsPanel insights={result.insights} />

      <section className="section products-runlog">
        <div>
          <div className="section-head">
            <h2 className="section-title">Products</h2>
            <span className="muted small">Open a product for its own breakdown</span>
          </div>
          <ProductGrid products={result.products} />
        </div>
        <div>
          <div className="section-head">
            <h2 className="section-title">This run</h2>
          </div>
          <RunLogCard run={result.run} ratingCheck={result.rating_check} />
        </div>
      </section>

      <section className="section" ref={tableSection}>
        <div className="section-head">
          <h2 className="section-title">All reviews</h2>
        </div>
        <ReviewTable reviews={result.reviews} filters={filters} onFiltersChange={setFilters} />
      </section>
    </>
  );
}
