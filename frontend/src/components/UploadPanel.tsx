import { useEffect, useState } from "react";
import type { DragEvent } from "react";
import { analyzeFile } from "../api";
import type { AnalyzeResponse } from "../types";

const MAX_BYTES = 2_000_000; // same limit as the server

interface Props {
  onAnalysed: (result: AnalyzeResponse, fileName: string) => void;
}

export default function UploadPanel({ onAnalysed }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const seconds = useSecondsWhile(busy);

  function choose(candidate: File | undefined) {
    setError("");
    if (!candidate) return;
    if (!candidate.name.toLowerCase().endsWith(".csv")) {
      setFile(null);
      setError("Please choose a .csv file.");
    } else if (candidate.size > MAX_BYTES) {
      setFile(null);
      setError("The file is larger than 2 MB.");
    } else {
      setFile(candidate);
    }
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    if (!busy) choose(event.dataTransfer.files[0]);
  }

  async function analyse() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      onAnalysed(await analyzeFile(file), file.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <section className="upload card">
      <h1>Analyse your product reviews</h1>
      <p className="upload-intro">
        Upload a CSV and ReviewLens shows what customers love, what they complain about, and which
        reviews need a reply.
      </p>

      <label
        className={`dropzone${dragging ? " dragging" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <input
          type="file"
          accept=".csv,text/csv"
          disabled={busy}
          onChange={(event) => choose(event.target.files?.[0])}
        />
        <span className="dropzone-title">Drop reviews.csv here or click to choose a file</span>
        <span className="muted small">Columns: review_id, product, rating, date, review_text · up to 2 MB</span>
        {file && <span className="file-name">{file.name}</span>}
      </label>

      <div className="upload-actions">
        <button type="button" className="btn btn-primary" onClick={analyse} disabled={!file || busy}>
          Analyse reviews
        </button>
        {busy && (
          <span className="progress" role="status">
            <span className="spinner" aria-hidden="true" />
            Analysing… {seconds}s
          </span>
        )}
      </div>
      {busy && (
        <p className="muted small">
          Reviews go to the AI in batches of 5. Free-tier rate limits can add short waits. Uploading
          the same file again is instant because results are cached.
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <ul className="upload-notes">
        <li>Empty reviews are skipped, and duplicate reviews are analysed only once.</li>
        <li>Missing or invalid ratings are shown as unknown.</li>
        <li>The AI key stays on the server. Your browser only talks to ReviewLens.</li>
      </ul>
    </section>
  );
}

/** Counts seconds while `running` is true, so long analyses show visible progress. */
function useSecondsWhile(running: boolean): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!running) return;
    setSeconds(0);
    const timer = setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, [running]);
  return seconds;
}
