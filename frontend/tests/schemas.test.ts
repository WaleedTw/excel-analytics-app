import { describe, expect, it } from "vitest";
import { dashboardSchema, healthSchema, workbookSchema } from "../lib/schemas";

describe("عقود Zod", () => {
  it("تقبل بيانات مصنف صحيحة", () => {
    const result = workbookSchema.parse({
      file_id: "abc", original_name: "بيانات.xlsx", safe_name: "abc.xlsx", size_bytes: 100,
      mime_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      sheets: [{ name: "المبيعات", rows: 5, columns: 3, has_data: true }], created_at: "2026-08-11T00:00:00Z",
    });
    expect(result.sheets[0].name).toBe("المبيعات");
  });

  it("ترفض DashboardSpec ناقصة", () => {
    expect(() => dashboardSchema.parse({ title: "لوحة ناقصة" })).toThrow();
  });

  it("تقبل حالة Ollama المحلية", () => {
    const result = healthSchema.parse({
      status: "ok", service: "bayyinah-backend", mode: "ollama", model: "llama3.2",
      llm_ready: true, detail: "جاهز", database: "sqlite", jobs: "inline",
    });
    expect(result.llm_ready).toBe(true);
  });

  it("تقبل حالة Groq السحابية", () => {
    const result = healthSchema.parse({
      status: "ok", service: "bayyinah-backend", mode: "groq",
      model: "llama-3.3-70b-versatile", llm_ready: true,
      detail: "جاهز", database: "sqlite", jobs: "inline",
    });
    expect(result.mode).toBe("groq");
  });
});
