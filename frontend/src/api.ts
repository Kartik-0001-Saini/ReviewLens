// The only place the browser talks to a server: our own FastAPI backend under /api.
import type { AnalyzeResponse, ReplyResult } from "./types";

export function analyzeFile(file: File): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<AnalyzeResponse>("/api/analyze", { method: "POST", body: form });
}

export function suggestReply(textHash: string): Promise<ReplyResult> {
  return request<ReplyResult>("/api/reply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text_hash: textHash }),
  });
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new Error("Cannot reach the server. Is the backend running?");
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(errorMessage(body, response.status));
  }
  return body as T;
}

function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  return `The server returned an error (HTTP ${status}).`;
}
