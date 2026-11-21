import { Link } from "react-router";
import { TOPIC_LABELS, plural, productPath } from "../format";
import type { ProductStats } from "../types";
import SentimentBar from "./SentimentBar";

export default function ProductGrid({ products }: { products: ProductStats[] }) {
  return (
    <div className="product-grid">
      {products.map((product) => (
        <Link key={product.product} to={productPath(product.product)} className="card product-card">
          <span className="product-name">{product.product}</span>
          <SentimentBar counts={product.sentiment} />
          <span className="product-meta">
            <span>{plural(product.analysed, "review")}</span>
            <span>{product.needs_reply} need a reply</span>
          </span>
          <span className="muted small">
            {product.top_issues.length > 0
              ? `Top issue: ${TOPIC_LABELS[product.top_issues[0].topic]}`
              : "No complaints"}
          </span>
        </Link>
      ))}
    </div>
  );
}
