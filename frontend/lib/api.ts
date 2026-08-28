import { analysisAnswerSchema, analysisSchema, customCalculationSchema, healthSchema, previewSchema, workbookSchema } from "./schemas";
import type { Locale } from "./i18n";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001/api/v1";

async function json<T>(response: Response, parser: { parse: (value: unknown) => T }, locale: Locale): Promise<T> {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = (body as { detail?: unknown }).detail;
    const validationMessage = Array.isArray(detail)
      ? detail.map((item) => typeof item === "object" && item !== null && "msg" in item ? String(item.msg) : "").filter(Boolean).join(" · ")
      : "";
    throw new Error(
      typeof detail === "string"
        ? detail
        : validationMessage || (locale === "ar" ? "تعذر إكمال الطلب." : "The request could not be completed."),
    );
  }
  return parser.parse(body);
}

const withLocale = (path: string, locale: Locale) => `${path}${path.includes("?") ? "&" : "?"}locale=${locale}`;

export async function uploadWorkbook(file: File, locale: Locale) {
  const data = new FormData(); data.append("file", file);
  return json(await fetch(withLocale(`${API}/files`, locale), { method: "POST", body: data }), workbookSchema, locale);
}
export async function getHealth(locale: Locale) {
  return json(await fetch(withLocale(`${API}/health`, locale), { cache: "no-store" }), healthSchema, locale);
}
export async function loadSample(kind: "sales" | "messy", locale: Locale) {
  return json(await fetch(withLocale(`${API}/samples/${kind}`, locale), { method: "POST" }), workbookSchema, locale);
}
export async function getPreview(fileId: string, sheet: string, locale: Locale) {
  return json(await fetch(withLocale(`${API}/files/${fileId}/preview?sheet=${encodeURIComponent(sheet)}`, locale)), previewSchema, locale);
}
export type MissingValueOverride = {
  column: string;
  source_row: number;
  action: "replace" | "delete_row";
  value?: string;
};

export async function startAnalysis(
  fileId: string,
  sheetName: string,
  columnMapping: Record<string, string> = {},
  missingValueMode: "recommended" | "manual" = "recommended",
  missingValueOverrides: MissingValueOverride[] = [],
  locale: Locale = "ar",
) {
  return json(await fetch(withLocale(`${API}/analyses`, locale), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ file_id: fileId, sheet_name: sheetName, max_iterations: 3, column_mapping: columnMapping, missing_value_mode: missingValueMode, missing_value_overrides: missingValueOverrides }) }), analysisSchema, locale);
}
export async function resumeAnalysis(analysisId: string, mappings: Record<string, string>, locale: Locale) {
  return json(await fetch(withLocale(`${API}/analyses/${analysisId}/resume`, locale), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mappings }) }), analysisSchema, locale);
}
export async function getAnalysis(analysisId: string, locale: Locale) {
  return json(await fetch(withLocale(`${API}/analyses/${analysisId}`, locale)), analysisSchema, locale);
}
export async function askAnalysis(analysisId: string, question: string, locale: Locale) {
  return json(await fetch(withLocale(`${API}/analyses/${analysisId}/ask`, locale), {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }),
  }), analysisAnswerSchema, locale);
}

export async function createCustomCalculation(analysisId: string, instruction: string, locale: Locale) {
  return json(await fetch(withLocale(`${API}/analyses/${analysisId}/calculations`, locale), {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ instruction }),
  }), customCalculationSchema, locale);
}
