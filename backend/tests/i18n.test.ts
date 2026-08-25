import { describe, expect, it } from "vitest";
import { hasArabic } from "../lib/i18n";

describe("English locale guardrails", () => {
  it("detects Arabic script in system-authored copy", () => {
    expect(hasArabic("Data quality note")).toBe(false);
    expect(hasArabic("ملاحظة على جودة البيانات")).toBe(true);
  });

  it("keeps the English navigation vocabulary free of Arabic script", () => {
    const copy = [
      "Home", "New analysis", "Upload file", "Select sheet", "Data preview",
      "Smart analysis", "Dashboard", "Overview", "Detailed insights",
      "Data Cleaning Agent", "Analysis & Calculation Agent", "Dashboard & Insights Agent",
    ];
    expect(copy.some(hasArabic)).toBe(false);
  });
});