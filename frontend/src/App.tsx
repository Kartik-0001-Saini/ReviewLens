import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import Header from "./components/Header";
import UploadPanel from "./components/UploadPanel";
import DashboardPage from "./pages/DashboardPage";
import ProductPage from "./pages/ProductPage";
import type { AnalyzeResponse } from "./types";

interface Analysis {
  result: AnalyzeResponse;
  fileName: string;
}

// The last result is kept for this browser tab only, so a page refresh does not lose the dashboard.
const STORAGE_KEY = "reviewlens:last-analysis";

function loadSaved(): Analysis | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Analysis) : null;
  } catch {
    return null;
  }
}

function save(analysis: Analysis | null) {
  try {
    if (analysis) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(analysis));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage can be unavailable (private mode); the app works without it.
  }
}

export default function App() {
  const [analysis, setAnalysis] = useState<Analysis | null>(loadSaved);
  useEffect(() => save(analysis), [analysis]);

  return (
    <BrowserRouter>
      <Header fileName={analysis?.fileName ?? null} onNewUpload={() => setAnalysis(null)} />
      <main className="container">
        {analysis ? (
          <Routes>
            <Route path="/" element={<DashboardPage result={analysis.result} />} />
            <Route path="/products/:name" element={<ProductPage result={analysis.result} />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        ) : (
          <UploadPanel onAnalysed={(result, fileName) => setAnalysis({ result, fileName })} />
        )}
      </main>
    </BrowserRouter>
  );
}
