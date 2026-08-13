import { z } from "zod";

export const sheetSchema = z.object({ name: z.string(), rows: z.number(), columns: z.number(), has_data: z.boolean() });
export const healthSchema = z.object({
  status: z.enum(["ok", "degraded"]), service: z.literal("bayyinah-backend"),
  mode: z.enum(["mock", "ollama", "groq"]), model: z.string(), llm_ready: z.boolean(), detail: z.string(),
  database: z.enum(["sqlite", "postgresql"]), jobs: z.enum(["inline", "celery"]),
});
export const workbookSchema = z.object({
  file_id: z.string(), original_name: z.string(), safe_name: z.string(), size_bytes: z.number(),
  mime_type: z.string(), sheets: z.array(sheetSchema), created_at: z.string(),
});
const resultValueSchema = z.object({ value: z.union([z.string(), z.number()]), operation: z.string(), source_columns: z.array(z.string()), query: z.string() });
const chartSchema = z.object({
  id: z.string(), title: z.string(), type: z.string(), categories: z.array(z.string()),
  series: z.array(z.object({ name: z.string(), values: z.array(z.number()) })), result_refs: z.array(z.string()),
  x_label: z.string(), y_label: z.string(),
});
export const dashboardSchema = z.object({
  title: z.string(), description: z.string(),
  kpis: z.array(z.object({ id: z.string(), label: z.string(), result_ref: z.string(), format: z.string(), tone: z.string() })),
  charts: z.array(chartSchema),
  tables: z.array(z.object({ id: z.string(), title: z.string(), columns: z.array(z.string()), rows: z.array(z.record(z.string(), z.unknown())) })),
  filters: z.array(z.object({ column: z.string(), label: z.string(), values: z.array(z.string()) })),
  computed_results: z.record(z.string(), resultValueSchema), value_formats: z.record(z.string(), z.string()),
  layout: z.array(z.string()), warnings: z.array(z.string()), quality_notes: z.array(z.string()),
  executive_summary: z.string(), detailed_insights: z.array(z.object({ title: z.string(), text: z.string(), result_refs: z.array(z.string()) })),
  dimensions: z.array(z.string()).default([]), measures: z.array(z.string()).default([]),
});
export const previewSchema = z.object({
  file_id: z.string(), sheet_name: z.string(), total_rows: z.number(),
  columns: z.array(z.object({ name: z.string(), inferred_type: z.string(), semantic_role: z.string(), null_count: z.number(), unique_count: z.number(), sample_values: z.array(z.unknown()), ambiguous: z.boolean(), reason: z.string() })),
  rows: z.array(z.record(z.string(), z.unknown())),
});
export const analysisSchema = z.object({
  analysis_id: z.string(), status: z.enum(["waiting_for_clarification", "completed", "completed_with_fallback", "failed"]),
  stage: z.string(), progress: z.number(), ambiguity: z.record(z.string(), z.unknown()).nullable(),
  analysis_plan: z.object({
    mode: z.enum(["mock", "ollama", "groq"]), model: z.string(), objective: z.string(),
    measures: z.array(z.string()), dimensions: z.array(z.string()), dates: z.array(z.string()),
    chart_strategy: z.array(z.enum(["trend", "category_comparison", "share", "distribution"])),
    privacy: z.string(),
  }).nullable(),
  dashboard: dashboardSchema.nullable(), quality: z.object({
    row_count: z.number(), column_count: z.number(), missing_cells: z.number(), missing_rate: z.number(),
    duplicate_rows: z.number(), invalid_values: z.number(), outlier_count: z.number(), formula_like_cells: z.number(),
    score: z.number(), notes: z.array(z.string()),
  }).nullable(), trace: z.array(z.string()), error: z.string().nullable(),
});

export const analysisSummarySchema = z.object({
  id: z.string(), file_id: z.string(), sheet_name: z.string(),
  status: z.string(), created_at: z.string(), original_name: z.string(),
});
export const analysisListSchema = z.array(analysisSummarySchema);

export type Workbook = z.infer<typeof workbookSchema>;
export type Health = z.infer<typeof healthSchema>;
export type Preview = z.infer<typeof previewSchema>;
export type Analysis = z.infer<typeof analysisSchema>;
export type AnalysisSummary = z.infer<typeof analysisSummarySchema>;
export type Dashboard = z.infer<typeof dashboardSchema>;
