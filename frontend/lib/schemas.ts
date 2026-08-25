import { z } from "zod";

export const sheetSchema = z.object({ name: z.string(), rows: z.number(), columns: z.number(), has_data: z.boolean() });
export const healthSchema = z.object({
  status: z.enum(["ok", "degraded"]), service: z.literal("bayyinah-backend"),
  mode: z.enum(["mock", "ollama", "groq"]), model: z.string(), llm_ready: z.boolean(), detail: z.string(),
  database: z.enum(["sqlite", "postgresql"]), jobs: z.enum(["inline", "background", "celery"]),
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
const cleaningAuditSchema = z.object({
  input_rows: z.number(), output_rows: z.number(), excluded_summary_rows: z.array(z.number()),
  numeric_conversions: z.number(), date_conversions: z.number(), normalized_text_cells: z.number(),
  invalid_numeric_cells: z.number(), invalid_date_cells: z.number(),
  excluded_empty_columns: z.array(z.string()).default([]), formula_calculations: z.number().default(0),
  missing_value_mode: z.enum(["recommended", "manual"]).default("recommended"),
  missing_values_before: z.record(z.string(), z.number()).default({}),
  missing_locations: z.record(z.string(), z.array(z.number())).default({}),
  output_source_rows: z.array(z.number()).default([]),
  remaining_missing_values: z.record(z.string(), z.number()).default({}),
  imputation_actions: z.array(z.object({
    column: z.string(), count: z.number(), strategy: z.enum(["derived", "sequential", "mean", "median", "label", "manual", "retained"]),
    fill_value: z.union([z.string(), z.number()]).nullable(), source_rows: z.array(z.number()).default([]), explanation: z.string(),
  })).default([]), removed_duplicate_rows: z.array(z.number()).default([]),
  policy: z.string(),
});
export const previewSchema = z.object({
  file_id: z.string(), sheet_name: z.string(), total_rows: z.number(),
  columns: z.array(z.object({ name: z.string(), inferred_type: z.string(), semantic_role: z.string(), null_count: z.number(), unique_count: z.number(), sample_values: z.array(z.unknown()), ambiguous: z.boolean(), reason: z.string() })),
  rows: z.array(z.record(z.string(), z.unknown())), cleaning_audit: cleaningAuditSchema.nullable().default(null),
});
export const analysisSchema = z.object({
  analysis_id: z.string(), status: z.enum(["queued", "running", "waiting_for_clarification", "completed", "completed_with_fallback", "failed"]),
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
  }).nullable(), cleaning_audit: cleaningAuditSchema.nullable().default(null), trace: z.array(z.string()), error: z.string().nullable(),
  agent_runs: z.array(z.object({
    // Keep the client compatible with older deployments that used aliases.
    // The UI normalizes the value to one of the three canonical agent ids.
    agent: z.string(),
    label: z.string(), responsibility: z.string(), status: z.enum(["completed", "failed"]),
    summary: z.string(), artifacts: z.array(z.string()),
  })).default([]),
});
export const analysisAnswerSchema = z.object({ answer: z.string(), sources: z.array(z.string()) });
export const customCalculationSchema = z.object({
  name: z.string(), expression: z.string(), value: z.number(), format: z.enum(["percent", "decimal"]),
  source_columns: z.array(z.string()), verification: z.string(), query: z.string(),
});

export type Workbook = z.infer<typeof workbookSchema>;
export type Health = z.infer<typeof healthSchema>;
export type Preview = z.infer<typeof previewSchema>;
export type Analysis = z.infer<typeof analysisSchema>;
export type Dashboard = z.infer<typeof dashboardSchema>;
export type AnalysisAnswer = z.infer<typeof analysisAnswerSchema>;
export type CustomCalculation = z.infer<typeof customCalculationSchema>;