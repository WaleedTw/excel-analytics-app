import { analysisListSchema, analysisSchema, healthSchema, previewSchema, workbookSchema } from "./schemas";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001/api/v1";

async function json<T>(response: Response, parser: { parse: (value: unknown) => T }): Promise<T> {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "تعذر إكمال الطلب.");
  return parser.parse(body);
}

export async function uploadWorkbook(file: File) {
  const data = new FormData(); data.append("file", file);
  return json(await fetch(`${API}/files`, { method: "POST", body: data }), workbookSchema);
}
export async function getHealth() {
  return json(await fetch(`${API}/health`, { cache: "no-store" }), healthSchema);
}
export async function loadSample(kind: "sales" | "messy") {
  return json(await fetch(`${API}/samples/${kind}`, { method: "POST" }), workbookSchema);
}
export async function getPreview(fileId: string, sheet: string) {
  return json(await fetch(`${API}/files/${fileId}/preview?sheet=${encodeURIComponent(sheet)}`), previewSchema);
}
export async function startAnalysis(fileId: string, sheetName: string, columnMapping: Record<string, string> = {}) {
  return json(await fetch(`${API}/analyses`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ file_id: fileId, sheet_name: sheetName, max_iterations: 3, column_mapping: columnMapping }) }), analysisSchema);
}
export async function resumeAnalysis(analysisId: string, mappings: Record<string, string>) {
  return json(await fetch(`${API}/analyses/${analysisId}/resume`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mappings }) }), analysisSchema);
}
export async function listAnalyses() {
  return json(await fetch(`${API}/analyses`), analysisListSchema);
}
export async function getAnalysis(analysisId: string) {
  return json(await fetch(`${API}/analyses/${analysisId}`), analysisSchema);
}
