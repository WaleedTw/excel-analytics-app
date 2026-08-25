"use client";

import { ChangeEvent, CSSProperties, DragEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity, ArrowLeft, ArrowRight, BarChart3, Bot, Check, ChevronDown, ChevronLeft, ChevronRight, CircleAlert,
  Clock3, Database, Github, Globe2, Layers3, LayoutDashboard, Lightbulb, Linkedin, Loader2, MessageCircleQuestion, Search,
  PencilLine, Send, ShieldCheck, Sparkles, Trash2, TrendingUp, Upload, WandSparkles, X,
} from "lucide-react";
import {
  askAnalysis, getAnalysis, getHealth, getPreview, resumeAnalysis, startAnalysis,
  uploadWorkbook,
} from "@/lib/api";
import type { MissingValueOverride } from "@/lib/api";
import type { Analysis, Dashboard, Health, Preview, Workbook } from "@/lib/schemas";
import { LanguageProvider, useLanguage } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import { ChartCard, type ChartSelection } from "./chart-card";
import { DataTable } from "./data-table";

type View = "home" | "upload" | "sheets" | "preview" | "clarify" | "progress" | "dashboard" | "insights" | "error";
const stages: Record<Locale, string[]> = {
  ar: ["رفع الملف", "اختيار الورقة", "معاينة البيانات", "التحليل الذكي", "اللوحة"],
  en: ["Upload file", "Select sheet", "Preview data", "Smart analysis", "Dashboard"],
};
const stageLabels: Record<Locale, Record<string, string>> = {
  ar: {
    queued: "تم إدراج التحليل في قائمة التنفيذ", validate_file: "التحقق من أمان الملف",
    inspect_workbook: "فحص أوراق ملف Excel", detect_tables: "اكتشاف الجداول القابلة للتحليل",
    infer_semantics: "فهم أنواع العواميد وأدوارها", detect_ambiguities: "فحص العواميد التي تحتاج توضيحًا",
    request_user_clarification: "انتظار توضيح معنى العواميد", resume_queued: "استئناف التحليل بعد التوضيح",
    profile_dataset: "تنظيف نسخة التحليل وقياس جودتها", create_analysis_plan: "إنشاء خطة التحليل",
    execute_analysis: "تنفيذ الحسابات", validate_results: "التحقق من صحة النتائج",
    generate_dashboard_spec: "تجهيز الرسوم والمؤشرات", generate_insights: "صياغة الرؤى النهائية",
    save_analysis: "تجهيز النتيجة للجلسة الحالية", fallback_analysis: "تشغيل المسار التحليلي الاحتياطي",
    handle_failure: "إيقاف التحليل بأمان", background_failure: "تعذر إكمال مهمة التحليل",
  },
  en: {
    queued: "Analysis queued", validate_file: "Validating file security",
    inspect_workbook: "Inspecting workbook sheets", detect_tables: "Detecting analyzable tables",
    infer_semantics: "Understanding column types and roles", detect_ambiguities: "Checking ambiguous columns",
    request_user_clarification: "Waiting for column clarification", resume_queued: "Resuming after clarification",
    profile_dataset: "Cleaning the analysis copy and scoring quality", create_analysis_plan: "Creating the analysis plan",
    execute_analysis: "Running deterministic calculations", validate_results: "Validating calculated results",
    generate_dashboard_spec: "Preparing charts and KPIs", generate_insights: "Generating final insights",
    save_analysis: "Preparing the session result", fallback_analysis: "Running the verified fallback path",
    handle_failure: "Stopping analysis safely", background_failure: "Background analysis could not be completed",
  },
};

const enNumber = (value: number) => new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
const displayCell = (value: unknown) => value == null ? "—" : typeof value === "number" ? enNumber(value) : String(value);
const missingTokens = new Set(["", "-", "—", "–", "na", "n/a", "nan", "null", "none", "غير متوفر", "غير متاح", "لا يوجد"]);
const isMissingCell = (value: unknown) => value == null || (typeof value === "string" && missingTokens.has(value.trim().toLowerCase()));
const looksLikeIdentifier = (name: string) => /(^|[\s_-])(id|code|ref|key|number|no)(?=$|[\s_-])|معرف|رقم\s*(الطلب|العملية|المنتج|العميل)?/i.test(name);
const looksMonetary = (name: string) => /(price|sales|revenue|amount|cost|total|salary|سعر|مبيعات|إيراد|ايراد|مبلغ|تكلفة|إجمالي|اجمالي)/i.test(name);
const formatMetric = (value: number | string, format: string, currency = "SAR") => {
  if (typeof value !== "number") return value;
  if (format === "currency") return new Intl.NumberFormat("en-US", { style: "currency", currency, currencyDisplay: "code", maximumFractionDigits: 0 }).format(value);
  if (format === "percent") return new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 }).format(Math.abs(value) <= 1 ? value : value / 100);
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
};

function AnimatedMetric({ value, format, currency }: { value: number | string; format: string; currency?: string }) {
  const [display, setDisplay] = useState(typeof value === "number" ? 0 : value);
  useEffect(() => {
    if (typeof value !== "number") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const frame = requestAnimationFrame(() => setDisplay(value));
      return () => cancelAnimationFrame(frame);
    }
    let frame = 0;
    const started = performance.now();
    const duration = 850;
    const animate = (now: number) => {
      const progress = Math.min((now - started) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(value * eased);
      if (progress < 1) frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [value]);
  return <>{formatMetric(display, format, currency)}</>;
}

function Logo({ onClick }: { onClick?: () => void }) {
  const { t } = useLanguage();
  return <button className="logo" onClick={onClick} aria-label={t("بينة — العودة إلى الرئيسية", "Bayyinah — back to home")}><strong>{t("بــــيّنة", "Bayyinah")}</strong></button>;
}

function LanguageToggle() {
  const { locale, toggleLocale } = useLanguage();
  return <button type="button" className="language-toggle" onClick={toggleLocale} aria-label={locale === "ar" ? "Switch to English" : "Switch to Arabic"}><Globe2 aria-hidden="true"/><span>{locale === "ar" ? "English" : "العربية"}</span></button>;
}

function ForwardArrow({ size = 20 }: { size?: number }) {
  const { direction } = useLanguage();
  return direction === "rtl" ? <ArrowLeft size={size}/> : <ArrowRight size={size}/>;
}

function ForwardChevron() {
  const { direction } = useLanguage();
  return direction === "rtl" ? <ChevronLeft/> : <ChevronRight/>;
}

function SiteFooter({ compact = false, go }: { compact?: boolean; go: (view: View) => void }) {
  const { t } = useLanguage();
  return <footer className={`site-footer ${compact ? "results-footer" : ""}`}>
    <Logo onClick={() => go("home")}/>
    <p><strong>{t("وليد التويجري", "Waleed Altuwaijri")}</strong><small>{t("© 2026 جميع الحقوق محفوظة.", "© 2026 All rights reserved.")}</small></p>
    <nav className="creator-links" aria-label={t("روابط وليد التويجري", "Waleed Altuwaijri links")}>
      <a href="https://www.linkedin.com/in/waleed-altuwaijri-803273353" target="_blank" rel="noreferrer noopener" aria-label="LinkedIn"><Linkedin/><span>LinkedIn</span></a>
      <a href="https://github.com/WaleedTw" target="_blank" rel="noreferrer noopener" aria-label="GitHub"><Github/><span>GitHub</span></a>
    </nav>
  </footer>;
}

function Header({ view, go }: { view: View; go: (view: View) => void }) {
  const { t } = useLanguage();
  return <header className="site-header"><Logo onClick={() => go("home")} /><nav aria-label={t("التنقل الرئيسي", "Main navigation")}>
    <button className={view === "home" ? "active" : ""} aria-current={view === "home" ? "page" : undefined} onClick={() => go("home")}>{t("الرئيسية", "Home")}</button>
    <button className={view === "upload" ? "active" : ""} aria-current={view === "upload" ? "page" : undefined} onClick={() => go("upload")}>{t("تحليل جديد", "New analysis")}</button>
  </nav><LanguageToggle/></header>;
}

function Journey({ current }: { current: number }) {
  const { locale, t } = useLanguage();
  return <div className="journey" aria-label={t("مراحل التحليل", "Analysis stages")}>{stages[locale].map((stage, index) => <div className={index < current ? "done" : index === current ? "current" : ""} aria-current={index === current ? "step" : undefined} key={stage}><span>{index < current ? <Check size={13} /> : index + 1}</span><b>{stage}</b></div>)}</div>;
}

// ======== الصفحة الرئيسية – معدلة لتكون في المنتصف ========
function Home({ go }: { go: (view: View) => void }) {
  const { t } = useLanguage();
  return (
    <main className="home-page home-apple" style={{
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      alignItems: "center",
      minHeight: "80vh",
      textAlign: "center",
      padding: "2rem 1.5rem",
    }}>
      <section className="hero-section" style={{ maxWidth: "820px", width: "100%" }}>
        <div className="hero-copy">
          <div className="eyebrow" style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "0.5rem" }}>
            <Sparkles/> {t("تحليــــل عربي واضح", "Clear, verified analytics")}
          </div>
          <h1 style={{ fontSize: "clamp(2.2rem, 6vw, 3.6rem)", lineHeight: 1.2, margin: "1.2rem 0 0.8rem" }}>
            {t("حوّل الأرقــــام إلى", "Turn numbers into")}<br/>
            <em>{t("قــــرار واضــــح.", "clear decisions.")}</em>
          </h1>
          <p style={{ fontSize: "1.2rem", maxWidth: "600px", margin: "0 auto 1.8rem", opacity: 0.85 }}>
            {t("ارفع ملف Excel أو CSV واترك «بيّنة» يفهم بنيته، يتحقق من جودته، ثم يبني لك لوحة تفاعلية بأرقام قابلة للتتبّع.", "Upload an Excel or CSV file. Bayyinah understands its structure, validates data quality, and builds an interactive dashboard with traceable numbers.")}
          </p>
          <div className="hero-actions" style={{ display: "flex", justifyContent: "center", gap: "1rem", flexWrap: "wrap" }}>
            <button type="button" className="primary large hero-primary" onClick={() => go("upload")}>
              {t("ابــــدأ تحليل ملفك", "Start analyzing your file")} <ForwardArrow/>
            </button>
          </div>
          <div className="trust-row" style={{
            display: "flex",
            justifyContent: "center",
            gap: "2rem",
            flexWrap: "wrap",
            marginTop: "2rem",
            fontSize: "0.95rem",
          }}>
            <span><ShieldCheck/> {t("حسابات موثقة", "Verified calculations")}</span>
            <span><BarChart3/> {t("رسوم تفاعلية", "Interactive charts")}</span>
            <span><Database/> {t("يدعم XLSX وCSV", "XLSX and CSV support")}</span>
          </div>
        </div>
      </section>
      <section className="home-proof" style={{
        display: "flex",
        justifyContent: "center",
        gap: "2.5rem",
        flexWrap: "wrap",
        marginTop: "3rem",
        maxWidth: "820px",
        width: "100%",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <b>01</b>
          <span>
            <strong>{t("إيجنت تنظيف البيانات", "Data Cleaning Agent")}</strong>
            <small style={{ display: "block", opacity: 0.7 }}>{t("تهيئة البيانات وفحص جودتها", "Prepares data and validates quality")}</small>
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <b>02</b>
          <span>
            <strong>{t("إيجنت التحليل والحسابات", "Analysis & Calculation Agent")}</strong>
            <small style={{ display: "block", opacity: 0.7 }}>{t("حساب المؤشرات واستخراج الاتجاهات", "Calculates KPIs and identifies trends")}</small>
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <b>03</b>
          <span>
            <strong>{t("إيجنت الداشبورد والرؤى", "Dashboard & Insights Agent")}</strong>
            <small style={{ display: "block", opacity: 0.7 }}>{t("اعتماد النتائج وتجهيز اللوحة", "Validates results and prepares the dashboard")}</small>
          </span>
        </div>
      </section>
    </main>
  );
}
// ======== نهاية التعديل ========

function UploadPage({ onFile, loading }: { onFile: (file: File) => void; loading: boolean }) {
  const { t } = useLanguage();
  const input = useRef<HTMLInputElement>(null);
  const [dragActive,setDragActive] = useState(false);
  const drop = (event: DragEvent) => { event.preventDefault(); setDragActive(false); const file = event.dataTransfer.files[0]; if (file) onFile(file); };
  return <main className="flow-page"><Journey current={0}/><div className="flow-heading"><span className="section-kicker">{t("تحليل جديد", "New analysis")}</span><h1>{t("ابــــدأ من ملف بيانات", "Start with a data file")}</h1><p>{t("ملف XLSX أو CSV واحد، بحجم لا يتجاوز 10 ميجابايت.", "One XLSX or CSV file, up to 10 MB.")}</p></div><section className={`upload-zone ${dragActive ? "drag-active" : ""}`} aria-busy={loading} onDrop={drop} onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }} onDragLeave={() => setDragActive(false)} onDragOver={(event) => event.preventDefault()}><div className="upload-icon">{loading ? <Loader2 className="spin"/> : <Upload/>}</div><h2>{loading ? t("نفحص الملف الآن…", "Checking the file…") : dragActive ? t("اترك الملف هنا", "Drop the file here") : t("اسحب ملفك إلى هنا", "Drag your file here")}</h2><p>{t("أو اختره من جهازك.", "Or choose it from your device.")}</p><input ref={input} type="file" accept=".xlsx,.csv,text/csv" onChange={(event: ChangeEvent<HTMLInputElement>) => event.target.files?.[0] && onFile(event.target.files[0])}/><button className="primary" disabled={loading} onClick={() => input.current?.click()}>{t("اختيار ملف", "Choose file")}</button><div className="upload-rules"><span><Check/> {t("XLSX أو CSV", "XLSX or CSV")}</span><span><Check/> {t("حسابات موثقة", "Verified calculations")}</span><span><Check/> {t("فحص آمن", "Secure validation")}</span></div></section></main>;
}

function SheetsPage({ workbook, choose, openingSheet }: { workbook: Workbook; choose: (sheet: string) => void; openingSheet: string | null }) {
  const { t } = useLanguage();
  return <main className="flow-page wide"><Journey current={1}/><div className="flow-heading"><span className="section-kicker">{t("تم التحقق من الملف", "File verified")}</span><h1>{t("اختــــر ورقة العمل", "Select a worksheet")}</h1><p>{workbook.original_name} · {enNumber(workbook.sheets.length)} {t("أوراق", "sheets")}</p></div><div className="sheet-grid">{workbook.sheets.map((sheet, index) => {const isOpening=openingSheet===sheet.name;return <button type="button" key={sheet.name} aria-busy={isOpening} disabled={!sheet.has_data||openingSheet!==null} onClick={() => choose(sheet.name)}><span className="sheet-icon">{index + 1}</span><div><h3>{sheet.name}</h3><p>{enNumber(sheet.rows)} {t("صف", "rows")} · {enNumber(sheet.columns)} {t("عامود", "columns")}</p></div><span className={sheet.has_data ? "ready" : "empty"}>{isOpening?<><Loader2 className="spin"/> {t("جارٍ الفتح…", "Opening…")}</>:sheet.has_data?t("جاهزة", "Ready"):t("فارغة", "Empty")}</span><ForwardChevron/></button>;})}</div></main>;
}

type CleaningAuditView = NonNullable<Preview["cleaning_audit"]>;

function CleaningNotice({ audit, proposal = false }: { audit: CleaningAuditView; proposal?: boolean }) {
  const { t } = useLanguage();
  const actions = audit.imputation_actions;
  const missingTotal = Object.values(audit.missing_values_before).reduce((sum,count)=>sum+count,0);
  const strategyLabel = { derived:t("علاقة محسوبة", "Calculated relationship"), sequential:t("تسلسل معرّف", "Identifier sequence"), mean:t("المتوسط", "Mean"), median:t("الوسيط", "Median"), label:t("وسم واضح", "Explicit label"), manual:t("إدخال يدوي", "Manual entry"), delete_row:t("حذف الصف", "Row deleted"), retained:t("مراجعة مطلوبة", "Review required") } as const;
  return <section className={`cleaning-notice ${missingTotal ? "has-missing" : "clean"}`}>
    <header><span><ShieldCheck/></span><div><small>{t("إيجنت تنظيف البيانات", "Data Cleaning Agent")}</small><h2>{missingTotal ? proposal ? t(`اكتشف ${enNumber(missingTotal)} قيمة ناقصة ويطلب قرارك`, `Found ${enNumber(missingTotal)} missing values and needs your decision`) : t(`عالج ${enNumber(missingTotal)} قيمة ناقصة`, `Resolved ${enNumber(missingTotal)} missing values`) : t("بيانات الصفوف الفعلية مكتملة", "Actual data rows are complete")}</h2><p>{missingTotal ? proposal ? t("هذه معالجة بيّنة المقترحة فقط؛ اختر اعتمادها أو أدخل القيم يدويًا قبل بدء التحليل.", "This is Bayyinah's proposed treatment. Approve it or enter values manually before analysis starts.") : t("هذه هي العواميد المتأثرة وطريقة المعالجة التي طُبقت على نسخة التحليل.", "These are the affected columns and the treatments applied to the analysis copy.") : audit.excluded_summary_rows.length ? t(`استُبعد ${enNumber(audit.excluded_summary_rows.length)} صف إجمالي بنيوي؛ خلاياه الفارغة ليست سجلات مفقودة.`, `${enNumber(audit.excluded_summary_rows.length)} structural total row was excluded; its blank cells are not missing records.`) : t("لم تُرصد قيم ناقصة تحتاج إلى تعويض في نسخة التحليل.", "No missing values requiring treatment were found in the analysis copy.")}</p></div></header>
    {actions.length>0&&<div className="cleaning-actions">{actions.map((action,index)=><article className={action.strategy === "retained" ? "retained" : action.strategy === "delete_row" ? "deleted" : "resolved"} key={`${action.column}-${action.strategy}-${index}`}><div><b>{action.column}</b><small><span dir="ltr">{enNumber(action.count)}</span> {action.strategy === "delete_row" ? t("صف محذوف من نسخة التحليل", "rows removed from the analysis copy") : t("قيمة ناقصة", "missing values")}{action.source_rows.length ? <> · {t("صفوف Excel", "Excel rows")}: <span dir="ltr">{action.source_rows.map(enNumber).join(", ")}</span></> : null}</small></div><strong>{strategyLabel[action.strategy]}</strong><p>{action.explanation}{action.fill_value!=null&&action.strategy!=="label"?<> {t("القيمة/القاعدة المستخدمة", "Applied value/rule")}: <b dir="ltr">{typeof action.fill_value === "number" ? enNumber(action.fill_value) : action.fill_value}</b>.</>:null}</p></article>)}</div>}
    <footer>{audit.formula_calculations>0&&<span><Activity/> {t("احتُسبت", "Calculated")} <b dir="ltr">{enNumber(audit.formula_calculations)}</b> {t("صيغة صفية آمنة", "safe row formulas")}</span>}{audit.removed_duplicate_rows.length>0&&<span><X/> {t("أزيل", "Removed")} <b dir="ltr">{enNumber(audit.removed_duplicate_rows.length)}</b> {t("صف مكرر مطابق", "exact duplicate rows")}</span>}{audit.user_deleted_rows.length>0&&<span><Trash2/> {t("حُذف بقرار المستخدم", "Deleted by user choice")} <b dir="ltr">{enNumber(audit.user_deleted_rows.length)}</b> {t("صف من نسخة التحليل", "rows from the analysis copy")}</span>}{audit.excluded_empty_columns.length>0&&<span><X/> {t("استُبعدت العواميد الفارغة", "Excluded empty columns")}: {audit.excluded_empty_columns.join(", ")}</span>}{Object.keys(audit.remaining_missing_values).length>0&&<span className="needs-review"><CircleAlert/> {t("بقيت للمراجعة", "Still requires review")}: {Object.entries(audit.remaining_missing_values).map(([column,count])=>`${column} (${enNumber(count)})`).join(", ")}</span>}</footer>
  </section>;
}

function PreviewPage({ preview, analyze }: { preview: Preview; analyze: (mode: "recommended" | "manual", overrides: MissingValueOverride[]) => void }) {
  const { t } = useLanguage();
  const fallbackAudit = useMemo<CleaningAuditView | null>(() => {
    const reportedMissing = preview.columns.reduce((sum, column) => sum + column.null_count, 0);
    const auditHasLocations = preview.cleaning_audit
      ? Object.values(preview.cleaning_audit.missing_locations).some((rows) => rows.length > 0)
      : false;
    if (preview.cleaning_audit && (reportedMissing === 0 || auditHasLocations)) return null;
    const outputSourceRows = preview.rows.map((_, index) => index + 2);
    const missingLocations = Object.fromEntries(preview.columns.map((column) => {
      const sourceRows = preview.rows.flatMap((row, index) => isMissingCell(row[column.name]) ? [outputSourceRows[index]] : []);
      return [column.name, sourceRows] as const;
    }).filter(([, sourceRows]) => sourceRows.length > 0));
    if (Object.keys(missingLocations).length === 0) return null;

    const imputationActions: CleaningAuditView["imputation_actions"] = preview.columns.flatMap((column) => {
      const sourceRows = missingLocations[column.name] ?? [];
      if (sourceRows.length === 0) return [];
      const uncertain = column.semantic_role === "date" || column.semantic_role === "identifier" || looksLikeIdentifier(column.name);
      let strategy: CleaningAuditView["imputation_actions"][number]["strategy"] = "retained";
      let fillValue: string | number | null = null;
      let explanation = t("هذه القيمة تحتاج إدخالًا يدويًا موثوقًا أو حذف الصف كاملًا.", "This value needs trusted manual input or deletion of the entire row.");
      if (!uncertain && column.semantic_role === "measure") {
        strategy = looksMonetary(column.name) ? "mean" : "median";
        explanation = strategy === "mean"
          ? t("ستُعالج القيم الرقمية المالية بمتوسط القيم الصحيحة في العامود.", "Missing monetary values will use the mean of valid values in the column.")
          : t("ستُعالج القيم الرقمية بوسيط القيم الصحيحة لتقليل أثر القيم الشاذة.", "Missing numeric values will use the median of valid values to limit outlier impact.");
      } else if (!uncertain && column.semantic_role === "dimension") {
        strategy = "label";
        fillValue = t("غير محدد", "Unspecified");
        explanation = t("ستُحفظ القيمة الوصفية الناقصة تحت وسم واضح دون اختراع معلومة.", "The missing descriptive value will use an explicit label without inventing data.");
      }
      return [{ column: column.name, count: sourceRows.length, strategy, fill_value: fillValue, source_rows: sourceRows, explanation }];
    });
    const missingValuesBefore = Object.fromEntries(Object.entries(missingLocations).map(([column, rows]) => [column, rows.length]));
    const remainingMissingValues = Object.fromEntries(imputationActions.filter((action) => action.strategy === "retained").map((action) => [action.column, action.count]));
    return {
      input_rows: preview.total_rows,
      output_rows: preview.total_rows,
      excluded_summary_rows: [],
      numeric_conversions: 0,
      date_conversions: 0,
      normalized_text_cells: 0,
      invalid_numeric_cells: 0,
      invalid_date_cells: 0,
      excluded_empty_columns: [],
      formula_calculations: 0,
      missing_value_mode: "recommended",
      missing_values_before: missingValuesBefore,
      missing_locations: missingLocations,
      output_source_rows: outputSourceRows,
      remaining_missing_values: remainingMissingValues,
      imputation_actions: imputationActions,
      removed_duplicate_rows: [],
      user_deleted_rows: [],
      policy: t("تقرير احتياطي محافظ بُني من صفوف المعاينة لأن الخادم لم يرسل سجل التنظيف.", "A conservative fallback audit built from preview rows because the server omitted the cleaning audit."),
    };
  }, [preview, t]);
  const audit = fallbackAudit ?? preview.cleaning_audit;
  const [mode,setMode] = useState<"recommended"|"manual">("recommended");
  const [manualValues,setManualValues] = useState<Record<string,string>>({});
  const [cellDecisions,setCellDecisions] = useState<Record<string,"replace"|"delete_row">>({});
  const affectedCells = useMemo(() => audit ? Object.entries(audit.missing_locations).flatMap(([column,rows]) => rows.map((sourceRow)=>({column,sourceRow}))) : [],[audit]);
  const unresolvedCells = useMemo(() => audit ? audit.imputation_actions.filter((action)=>action.strategy==="retained").flatMap((action)=>action.source_rows.map((sourceRow)=>({column:action.column,sourceRow}))) : [],[audit]);
  const actionFor = (column:string,sourceRow:number) => audit?.imputation_actions.find((action)=>action.column===column&&action.source_rows.includes(sourceRow));
  const cellKey = (column:string,sourceRow:number) => `${column}::${sourceRow}`;
  const decisionCells = mode === "recommended" ? unresolvedCells : affectedCells;
  const deletedRows = new Set(decisionCells.filter(({column,sourceRow})=>cellDecisions[cellKey(column,sourceRow)]==="delete_row").map(({sourceRow})=>sourceRow));
  const decisionComplete = decisionCells.every(({column,sourceRow})=>deletedRows.has(sourceRow)||(cellDecisions[cellKey(column,sourceRow)]==="replace"&&manualValues[cellKey(column,sourceRow)]?.trim()));
  const deleteOverrides: MissingValueOverride[] = [...deletedRows].map((sourceRow)=>{const cell=decisionCells.find((item)=>item.sourceRow===sourceRow)!;return {column:cell.column,source_row:sourceRow,action:"delete_row"};});
  const replacementOverrides: MissingValueOverride[] = decisionCells.filter(({column,sourceRow})=>!deletedRows.has(sourceRow)&&cellDecisions[cellKey(column,sourceRow)]==="replace").map(({column,sourceRow})=>({column,source_row:sourceRow,action:"replace",value:manualValues[cellKey(column,sourceRow)]??""}));
  const overrides = [...deleteOverrides,...replacementOverrides];
  const run = () => decisionComplete && analyze(mode,overrides);
  return <main className="flow-page extra-wide">
    <Journey current={2}/>
    <div className="split-heading">
      <div><span className="section-kicker">{t("معاينة البيانات", "Data preview")}</span><h1>{preview.sheet_name}</h1><p>{enNumber(preview.total_rows)} {t("صفًا", "rows")} · {enNumber(preview.columns.length)} {t("عواميد", "columns")} · {t("جميع الصفوف متاحة أدناه", "all rows available below")}</p></div>
      <button type="button" className="primary flow-primary" disabled={!decisionComplete} onClick={run}>{t("حلّل هذه الورقة", "Analyze this sheet")} <ForwardArrow/></button>
    </div>
    {audit&&<CleaningNotice audit={audit} proposal/>}
    {affectedCells.length>0&&<section className="cleaning-decision">
      <header><div><span className="section-kicker">{t("قرار المستخدم قبل التحليل", "Your decision before analysis")}</span><h2>{t("كيف تريد التعامل مع القيم الناقصة؟", "How should missing values be handled?")}</h2><p>{t("تطبّق بيّنة المعالجات الآمنة تلقائيًا. أما التاريخ أو المعرّف غير المؤكد فتختار له إدخالًا يدويًا أو حذف صفه كاملًا من نسخة التحليل.", "Bayyinah applies safe treatments automatically. For an uncertain date or identifier, enter a value manually or delete its entire row from the analysis copy.")}</p></div><ShieldCheck/></header>
      <div className="decision-options" role="radiogroup" aria-label={t("طريقة معالجة القيم الناقصة", "Missing-value treatment method")}>
        <button type="button" role="radio" aria-checked={mode==="recommended"} className={mode==="recommended"?"selected":""} onClick={()=>setMode("recommended")}><span><WandSparkles/></span><div><b>{t("معالجة بيّنة المقترحة", "Bayyinah's recommended treatment")}</b><small>{unresolvedCells.length?t("ستُعالج القيم الآمنة تلقائيًا، ثم تحسم الحالات غير المؤكدة أدناه.", "Safe values are treated automatically; resolve the uncertain cases below."):t("جميع القيم الناقصة قابلة للمعالجة الآمنة دون قرار إضافي.", "All missing values can be treated safely without an additional decision.")}</small></div><i className="decision-check" aria-hidden="true"><Check/></i></button>
        <button type="button" role="radio" aria-checked={mode==="manual"} className={mode==="manual"?"selected":""} onClick={()=>setMode("manual")}><span><PencilLine/></span><div><b>{t("سأراجع كل قيمة بنفسي", "I will review every value")}</b><small>{t("لكل خلية ناقصة: أدخل قيمة صحيحة أو احذف صفها كاملًا من نسخة التحليل.", "For every missing cell, enter a valid value or delete its entire row from the analysis copy.")}</small></div><i className="decision-check" aria-hidden="true"><Check/></i></button>
      </div>
      {decisionCells.length>0&&<div className="manual-values decision-cell-list">
        {decisionCells.map(({column,sourceRow})=>{const action=actionFor(column,sourceRow);const key=cellKey(column,sourceRow);const rowDeleted=deletedRows.has(sourceRow);const decision=cellDecisions[key];return <article className={`manual-value-row ${rowDeleted?"delete-selected":""}`} key={key}>
          <div className="decision-cell-title"><span><b>{column}</b><small>{t("صف Excel", "Excel row")} <i dir="ltr">{enNumber(sourceRow)}</i>{action?.fill_value!=null?<> · {t("اقتراح بيّنة", "Bayyinah suggestion")}: <i dir="ltr">{String(action.fill_value)}</i></>:null}</small></span><div className="cell-decision-actions" role="group" aria-label={t(`قرار عامود ${column} في صف ${sourceRow}`, `Decision for column ${column}, row ${sourceRow}`)}><button type="button" className={decision==="replace"&&!rowDeleted?"selected":""} onClick={()=>setCellDecisions({...cellDecisions,[key]:"replace"})}><PencilLine/> {t("إدخال يدوي", "Enter manually")}</button><button type="button" className={rowDeleted?"selected delete":"delete"} onClick={()=>setCellDecisions({...cellDecisions,[key]:"delete_row"})}><Trash2/> {t("حذف الصف كاملًا", "Delete entire row")}</button></div></div>
          {rowDeleted?<p className="row-delete-note"><Trash2/> {t(`سيُحذف صف Excel ${sourceRow} كاملًا من نسخة التحليل فقط، ولن يتغير ملفك الأصلي.`, `Excel row ${sourceRow} will be removed only from the analysis copy; your original file will not change.`)}</p>:decision==="replace"?<input value={manualValues[key]??""} onChange={(event)=>setManualValues({...manualValues,[key]:event.target.value})} placeholder={t("أدخل القيمة الصحيحة", "Enter the correct value")} aria-label={t(`القيمة البديلة لعامود ${column} في صف ${sourceRow}`, `Replacement value for column ${column}, row ${sourceRow}`)}/>:<p className="decision-prompt"><CircleAlert/> {t("اختر إدخال القيمة يدويًا أو حذف الصف كاملًا.", "Choose manual entry or delete the entire row.")}</p>}
        </article>})}
        <p className={decisionComplete?"complete":"pending"}>{decisionComplete?<><Check/> {t("اكتملت القرارات ويمكن بدء التحليل.", "All decisions are complete. Analysis can now start.")}</>:<><CircleAlert/> {t("احسم جميع الحالات قبل بدء التحليل.", "Resolve every case before starting analysis.")}</>}</p>
      </div>}
    </section>}
    <div className="profile-row">{preview.columns.map((column) => <article key={column.name} className={column.ambiguous ? "warn" : ""}><span>{column.semantic_role === "measure" ? t("مقياس", "Measure") : column.semantic_role === "date" ? t("تاريخ", "Date") : column.semantic_role === "dimension" ? t("بُعد", "Dimension") : column.semantic_role === "identifier" ? t("معرّف", "Identifier") : column.null_count === preview.total_rows ? t("فارغ بالكامل", "Completely empty") : t("يحتاج توضيحًا", "Needs clarification")}</span><b>{column.name}</b><small><span dir="ltr">{enNumber(column.unique_count)}</span> {t("قيمة فريدة", "unique values")} · {column.null_count === 0 ? t("لا توجد قيم مفقودة", "No missing values") : <><span dir="ltr">{enNumber(column.null_count)}</span> {t("قيمة مفقودة", "missing values")}</>}</small></article>)}</div>
    <section className="preview-table" aria-label={t("جميع بيانات الورقة", "All worksheet data")}><table><thead><tr>{preview.columns.map((column) => <th key={column.name}>{column.name}<small>{column.inferred_type}</small></th>)}</tr></thead><tbody>{preview.rows.map((row, index) => {const sourceRow=audit?.output_source_rows[index]??index+2;const rowDeleted=deletedRows.has(sourceRow);return <tr className={rowDeleted?"row-marked-for-deletion":undefined} key={index}>{preview.columns.map((column) => {const affected=audit?.missing_locations[column.name]?.includes(sourceRow);const key=cellKey(column.name,sourceRow);const manualValue=manualValues[key];const proposedValue=actionFor(column.name,sourceRow)?.fill_value;const replaced=Boolean(affected&&!rowDeleted&&cellDecisions[key]==="replace"&&manualValue?.trim());const value=replaced?manualValue:affected&&mode==="manual"?null:affected&&proposedValue!=null?proposedValue:row[column.name];const cellClass=rowDeleted?"deleted-cell":replaced?"repaired-cell manual":affected?"repaired-cell proposed":undefined;const title=rowDeleted?t(`سيُحذف صف Excel ${sourceRow} من نسخة التحليل`, `Excel row ${sourceRow} will be removed from the analysis copy`):replaced?t(`قيمة يدوية — صف Excel ${sourceRow}`, `Manual value — Excel row ${sourceRow}`):affected?t(`قيمة معالجة أو بانتظار قرار — صف Excel ${sourceRow}`, `Treated value or pending decision — Excel row ${sourceRow}`):undefined;return <td className={cellClass} title={title} key={column.name}>{displayCell(value)}</td>})}</tr>})}</tbody></table></section>
  </main>;
}

function ClarifyPage({ analysis, submit }: { analysis: Analysis; submit: (mapping: Record<string,string>) => void }) {
  const { t } = useLanguage();
  const columns = (analysis.ambiguity?.columns as Array<{name:string; sample_values:unknown[]; reason:string}>) ?? [];
  const [mapping, setMapping] = useState<Record<string,string>>(() => Object.fromEntries(columns.map((column) => [column.name, "dimension"])));
  return <main className="flow-page"><Journey current={3}/><div className="clarify-card"><div className="clarify-icon"><WandSparkles/></div><span className="section-kicker">{t("تدخل بشري ذكي", "Smart human review")}</span><h1>{t(`نحتاج معنى ${columns.length === 1 ? "عامود واحد" : "بعض العواميد"}`, `We need the meaning of ${columns.length === 1 ? "one column" : "a few columns"}`)}</h1><p>{t("أوقف النظام المسار وحفظ حالته. اختر المعنى الأقرب ثم سيكمل من النقطة نفسها.", "The workflow has paused and saved its state. Choose the closest meaning and it will continue from the same point.")}</p>{columns.map((column) => <div className="clarify-row" key={column.name}><div><b>{column.name}</b><span>{t("عينة", "Sample")}: {column.sample_values.map(String).join(", ") || t("لا توجد قيم", "No values")}</span></div><select aria-label={t(`دور العامود ${column.name}`, `Role of column ${column.name}`)} value={mapping[column.name]} onChange={(event) => setMapping({...mapping, [column.name]: event.target.value})}><option value="dimension">{t("بُعد وصفي", "Descriptive dimension")}</option><option value="measure">{t("مقياس رقمي", "Numeric measure")}</option><option value="date">{t("تاريخ", "Date")}</option><option value="identifier">{t("معرّف", "Identifier")}</option></select></div>)}<button className="primary full flow-primary" onClick={() => submit(mapping)}>{t("حفظ التوضيح ومتابعة التحليل", "Save clarification and continue")} <ForwardArrow/></button><small className="memory-note"><Database/> {t("الحالة محفوظة تحت المعرّف", "State saved under ID")} {analysis.analysis_id.slice(0,8)}</small></div></main>;
}

function ProgressPage({ analysis, presentingDashboard }: { analysis: Analysis | null; presentingDashboard: boolean }) {
  const { locale, t } = useLanguage();
  const [seconds, setSeconds] = useState(0);
  useEffect(() => { const timer = window.setInterval(() => setSeconds((value) => value + 1), 1000); return () => window.clearInterval(timer); }, []);
  const progress = presentingDashboard ? Math.min(analysis?.progress ?? 0,96) : analysis?.progress ?? 0;
  const stage = presentingDashboard ? t("إيجنت الداشبورد والرؤى يجهز مكونات اللوحة للعرض", "Dashboard & Insights Agent is preparing the dashboard") : stageLabels[locale][analysis?.stage ?? "queued"] ?? t("جارٍ تنفيذ التحليل", "Running analysis");
  const failureAgent = analysis?.status === "failed"
    ? analysis.stage.startsWith("create_") || analysis.stage === "execute_analysis" ? 1
      : ["validate_results", "generate_dashboard_spec", "generate_insights", "save_analysis", "fallback_analysis"].includes(analysis.stage) ? 2 : 0
    : -1;
  type AgentStageState = "completed" | "running" | "failed" | "pending";
  const agentStages = [
    { name:t("إيجنت تنظيف البيانات", "Data Cleaning Agent"), detail:t("تهيئة نسخة التحليل وفحص الجودة", "Preparing the analysis copy and validating quality"), icon:<ShieldCheck/>, activeAt:0, completeAt:53 },
    { name:t("إيجنت التحليل والحسابات", "Analysis & Calculation Agent"), detail:t("بناء الخطة وتنفيذ الحسابات", "Building the plan and running calculations"), icon:<Activity/>, activeAt:53, completeAt:73 },
    { name:t("إيجنت الداشبورد والرؤى", "Dashboard & Insights Agent"), detail:t("اعتماد النتائج وتجهيز اللوحة", "Validating results and preparing the dashboard"), icon:<LayoutDashboard/>, activeAt:73, completeAt:100 },
  ].map((item,index) => {
    const state: AgentStageState = presentingDashboard
      ? index < 2 ? "completed" : "running"
      : failureAgent >= 0
      ? index < failureAgent ? "completed" : index === failureAgent ? "failed" : "pending"
      : progress >= item.completeAt ? "completed" : progress >= item.activeAt ? "running" : "pending";
    return {...item,state};
  });
  const stateLabel = { completed:t("مكتمل", "Completed"), running:t("قيد التنفيذ", "In progress"), failed:t("فشل", "Failed"), pending:t("بانتظار دوره", "Waiting") } as const;
  return <main className="flow-page"><Journey current={3}/><div className="progress-card"><div className="agent-orbit"><Bot/><span></span></div><span className="section-kicker">{t("تنفيذ خلفي فعلي", "Live background execution")}</span><h1>{t("يتم تحليــــل ملفك الآن", "Your file is being analyzed")}</h1><p>{t("يمكنك متابعة المرحلة والنسبة الفعلية المرسلة من الخادم أثناء تنفيذ المهمة.", "Track the live stage and actual progress reported by the server.")}</p><div className="real-progress" aria-label={t(`اكتمل ${progress}% من التحليل`, `${progress}% of the analysis is complete`)}><div><span style={{width:`${progress}%`}}></span></div><b dir="ltr">{progress}%</b></div><div className="live-status"><i></i><div><b>{stage}</b><small>{t("مضى", "Elapsed")} <span dir="ltr">{enNumber(seconds)}</span> {t("ثانية", "seconds")} · {enNumber(analysis?.trace.length ?? 0)} {t("مراحل مسجّلة", "recorded stages")}</small></div><Clock3/></div><div className="progress-list" aria-label={t("حالة إيجنتات التحليل", "Analysis agent status")}>{agentStages.map((item)=><article className={item.state} key={item.name}><span>{item.state === "completed" ? <Check/> : item.state === "running" ? <Loader2 className="spin"/> : item.state === "failed" ? <X/> : item.icon}</span><div><b>{item.name}</b><small>{item.detail}</small></div><strong>{stateLabel[item.state]}</strong></article>)}</div></div></main>;
}

function AgentProof({ analysis }: { analysis: Analysis }) {
  const { t } = useLanguage();
  const order = ["cleaning_agent","analysis_agent","dashboard_agent"];
  const runs = order.map((agent)=>[...analysis.agent_runs].reverse().find((run)=>run.agent===agent)).filter((run):run is Analysis["agent_runs"][number]=>Boolean(run));
  return <section className="agent-proof"><div className="agent-proof-icon"><Bot/></div><div className="agent-proof-copy"><span className="section-kicker">{t("نتيجة التحليل", "Analysis result")}</span><h2>{t("اكتمل المسار وتحقّقــــت النتائج", "Workflow completed and results verified")}</h2><p>{t("أكملت الإيجنتات مراحل التنظيف والتحليل والتحقق، واعتمدت النتائج قبل عرضها.", "The agents completed cleaning, analysis, and validation before approving the results for display.")}</p></div><details className="trace-disclosure"><summary><span className="trace-summary-icon"><Activity/></span><span className="trace-summary-copy"><small>{t("المراحل التنفيذية", "Execution stages")}</small><strong><b dir="ltr">{enNumber(runs.length)}</b> {t("مراحل رئيسية حسب الإيجنت", "main agent stages")}</strong></span><span className="trace-status"><Check/> {t("مكتمل", "Completed")}</span><ChevronDown className="trace-chevron"/></summary><div className="trace-panel agent-run-panel"><header><b>{t("المراحل التنفيذية والمسؤول عنها", "Execution stages and owners")}</b><span dir="ltr">{enNumber(runs.length)}</span></header><ol>{runs.map((run,index) => <li key={run.agent}><b><Check/></b><span><small dir="ltr">{String(index+1).padStart(2,"0")}</small><strong>{run.label}</strong><em>{run.responsibility}</em><i>{run.summary}</i></span></li>)}</ol></div></details></section>;
}

function numericCell(value: unknown) {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const parsed = Number(String(value ?? "").replace(/,/g,""));
  return Number.isFinite(parsed) ? parsed : null;
}

function arabicFieldLabel(name: string, kind: "dimension" | "measure") {
  const normalized = name.toLowerCase().replace(/[_-]+/g," ");
  if (kind === "dimension") {
    if (/company|brand|شركة/.test(normalized)) return "الشركات";
    if (/product|منتج/.test(normalized)) return "المنتجات";
    if (/category|segment|فئ|تصنيف/.test(normalized)) return "الفئات";
    if (/region|منطق/.test(normalized)) return "المناطق";
    if (/city|مدين/.test(normalized)) return "المدن";
    if (/customer|client|عميل/.test(normalized)) return "العملاء";
    if (/year|سن|عام/.test(normalized)) return "السنوات";
    if (/quarter|ربع/.test(normalized)) return "الأرباع";
    if (/date|تاريخ/.test(normalized)) return "التواريخ";
  }
  if (/e.?com|online|إلكترون/.test(normalized) && /revenue|sales|إيراد|مبيعات/.test(normalized)) return "إيرادات التجارة الإلكترونية";
  if (/revenue|sales|إيراد|مبيعات/.test(normalized)) return "إجمالي الإيرادات";
  if (/profit|ربح/.test(normalized)) return "إجمالي الأرباح";
  if (/percentage|percent|rate|نسب/.test(normalized)) return "النسبة";
  if (/quantity|count|كمية/.test(normalized)) return "الكمية";
  if (/price|cost|سعر|تكلفة/.test(normalized)) return "السعر";
  return name;
}

const englishFieldLabel = (name: string) => name.replace(/[_-]+/g," ").replace(/\s+/g," ").trim();

function AskBayyinah({ analysisId, dashboard }: { analysisId: string; dashboard: Dashboard }) {
  const { locale, t } = useLanguage();
  const [question,setQuestion] = useState("");
  const [answer,setAnswer] = useState("");
  const [sources,setSources] = useState<string[]>([]);
  const [busy,setBusy] = useState(false);
  const [failure,setFailure] = useState("");
  const suggestions = useMemo(() => {
    const dimension = dashboard.dimensions[0];
    const measure = dashboard.measures[0];
    const dimensionAr = dimension ? arabicFieldLabel(dimension,"dimension") : "";
    const measureAr = measure ? arabicFieldLabel(measure,"measure") : "";
    const dimensionEn = dimension ? englishFieldLabel(dimension) : "";
    const measureEn = measure ? englishFieldLabel(measure) : "";
    return [
      t("ما القيم الناقصة وكيف عولجت؟", "Which values were missing, and how were they treated?"),
      dimension && measure ? t(`ما أعلى 3 من ${dimensionAr} حسب ${measureAr}؟`, `What are the top 3 ${dimensionEn} by ${measureEn}?`) : t("ما أهم نتيجة في التحليل؟", "What is the most important result?"),
      dimension && measure ? t(`قارن ${measureAr} بين ${dimensionAr}`, `Compare ${measureEn} by ${dimensionEn}`) : t("هل توجد ملاحظات على جودة البيانات؟", "Are there any data-quality concerns?"),
    ];
  },[dashboard.dimensions,dashboard.measures,t]);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); if (question.trim().length < 2 || busy) return;
    setBusy(true); setFailure("");
    try { const result = await askAnalysis(analysisId,question.trim(),locale); setAnswer(result.answer); setSources(result.sources); }
    catch (caught) { setFailure(caught instanceof Error ? caught.message : t("تعذر إرسال السؤال.", "The question could not be sent.")); }
    finally { setBusy(false); }
  };
  return <section className="ask-bayyinah"><header><div className="ask-icon"><MessageCircleQuestion/></div><div><span className="section-kicker">{t("مساعد النتائج الموثّق", "Verified results assistant")}</span><h2>{t("اسأل بيّنة عن التحليل", "Ask Bayyinah about the analysis")}</h2><p>{t("يفهم المقياس والبُعد والفلاتر، ثم يحسب الإجابة من البيانات ويتحقق منها بمحركين مستقلين.", "It understands measures, dimensions, and filters, then calculates the answer from the data and verifies it with two independent engines.")}</p></div></header><div className="ask-suggestions" aria-label={t("أسئلة مقترحة", "Suggested questions")}>{suggestions.map((suggestion)=><button type="button" dir="auto" key={suggestion} onClick={()=>setQuestion(suggestion)}>{suggestion}</button>)}</div><form onSubmit={submit}><input dir="auto" value={question} onChange={(event)=>setQuestion(event.target.value)} maxLength={500} placeholder={t("مثال: ما أعلى 3 منتجات حسب إجمالي المبيعات؟", "Example: What are the top 3 products by total sales?")} aria-label={t("سؤالك عن التحليل", "Your question about the analysis")}/><button className="primary" disabled={busy||question.trim().length<2}>{busy?<Loader2 className="spin"/>:<Send/>} {t("إرسال", "Send")}</button></form>{failure&&<div className="ask-error" dir="auto"><CircleAlert/><bdi>{failure}</bdi></div>}{answer&&<article className="ask-answer"><b>{t("إجابة بيّنة", "Bayyinah's answer")}</b><p dir="auto"><bdi>{answer}</bdi></p><small className="answer-sources">{sources.map((source,index)=><span key={`${source}-${index}`}><bdi dir="auto">{source}</bdi></span>)}</small></article>}</section>;
}

function DashboardNav({ active, go }: { active: "dashboard" | "insights"; go: (view: View) => void }) {
  const { t } = useLanguage();
  return <aside className="dash-sidebar"><button className="dash-brand" onClick={() => go("home")} aria-label={t("بينة — العودة إلى الرئيسية", "Bayyinah — back to home")}><strong>{t("بــــيّنة", "Bayyinah")}</strong></button><nav aria-label={t("أقسام لوحة التحليل", "Analysis dashboard sections")}><button className={active === "dashboard" ? "active" : ""} aria-current={active === "dashboard" ? "page" : undefined} onClick={() => go("dashboard")}><LayoutDashboard/><span>{t("نظرة عامة", "Overview")}</span></button><button className={active === "insights" ? "active" : ""} aria-current={active === "insights" ? "page" : undefined} onClick={() => go("insights")}><Sparkles/><span>{t("الرؤى التفصيلية", "Detailed insights")}</span></button></nav></aside>;
}

function DashboardView({ analysis, go }: { analysis: Analysis; go: (view: View) => void }) {
  const { t } = useLanguage();
  const dashboard = analysis.dashboard as Dashboard;
  const visibleKpis = dashboard.kpis.filter((kpi) => {
    const identity = `${kpi.id} ${kpi.result_ref} ${kpi.label}`.toLowerCase();
    return !identity.includes("rows") && !identity.includes("quality") && !kpi.label.includes("جودة البيانات") && !kpi.label.includes("إجمالي السجلات");
  }).slice(0,4);
  const [filters,setFilters] = useState<Record<string,string>>({});
  const [selection,setSelection] = useState<ChartSelection>(null);
  const selectedRows = useMemo(() => !selection ? dashboard.tables[0].rows : dashboard.tables[0].rows.filter((row) => String(row[selection.dimension] ?? "") === selection.value), [dashboard.tables,selection]);
  const metricValue = (resultRef:string) => {
    const result = dashboard.computed_results[resultRef];
    if (!selection || !result.source_columns.length) return result.value;
    const column = result.source_columns.find((name) => dashboard.measures.includes(name));
    if (!column) return result.operation === "count" ? selectedRows.length : result.value;
    const values = selectedRows.map((row)=>numericCell(row[column])).filter((value):value is number=>value!==null);
    if (!values.length) return 0;
    if (/average|avg/i.test(result.operation)) return values.reduce((sum,value)=>sum+value,0)/values.length;
    if (/^max$/i.test(result.operation)) return Math.max(...values);
    if (/^min$/i.test(result.operation)) return Math.min(...values);
    return values.reduce((sum,value)=>sum+value,0);
  };
  const score = analysis.quality?.score ?? 0;
  const ringStyle = { "--score": `${score * 3.6}deg` } as CSSProperties;
  return <main className="dashboard-page"><DashboardNav active="dashboard" go={go}/><section className="dash-main"><header className="dash-head"><div><span className="section-kicker">{t("لوحة تنفيذية موثقة", "Verified executive dashboard")}</span><h1>{dashboard.title}</h1><p>{dashboard.description}</p></div><button className="primary" onClick={()=>go("upload")}><Upload/> {t("تحليل ملف جديد", "Analyze a new file")}</button></header>
    <AgentProof analysis={analysis}/>
    {analysis.cleaning_audit&&<CleaningNotice audit={analysis.cleaning_audit}/>}
    {dashboard.warnings.length>0&&<div className="warning-banner"><CircleAlert/><div><b>{t("ملاحظة على جودة البيانات", "Data quality note")}</b><span>{dashboard.warnings.join(" ")}</span></div></div>}
    {selection&&<div className="active-selection"><span>{t("التصفية النشطة", "Active filter")}: <b>{selection.dimension}</b> = <strong>{selection.value}</strong></span><button onClick={()=>setSelection(null)}><X/> {t("مسح التحديد", "Clear selection")}</button></div>}
    <section className="kpi-grid">{visibleKpis.map((kpi,index)=>{const value=metricValue(kpi.result_ref);return <article key={kpi.id} className={`${kpi.tone} kpi-${index}`}><div className="kpi-top"><span>{kpi.label}</span><TrendingUp/></div><b className="metric-value" dir="ltr" title={String(value)}><AnimatedMetric value={value} format={kpi.format} currency={dashboard.value_formats.currency}/></b><small><Check/> {selection?t("محدّث حسب التحديد", "Updated for selection"):t("محسوب وموثق", "Calculated and verified")}</small></article>;})}</section>
    <div className="section-title"><div><span className="section-kicker">{t("الرسوم التحليلية", "Analytical charts")}</span><h2>{t("الصــــورة الكاملة للأداء", "The complete performance picture")}</h2></div><p>{t("اضغط على أي فئة لتصفية جميع الرسومات والمؤشرات.", "Select any category to filter all charts and KPIs.")}</p></div>
    <section className="charts-grid">{dashboard.charts.slice(0,4).map((chart)=><ChartCard chart={chart} tableSpec={dashboard.tables[0]} dimensions={dashboard.dimensions} measures={dashboard.measures} selection={selection} onSelectionChange={setSelection} key={chart.id}/>)}</section>
    <section className="insight-grid quality-only"><article className="quality-card"><div className="score-ring" style={ringStyle}><span><b dir="ltr">{score}</b><small>{t("من 100", "out of 100")}</small></span></div><div><span className="section-kicker">{t("جودة البيانات", "Data quality")}</span><h2>{score>=85?t("موثوقة لاتخاذ القرار", "Reliable for decision-making"):t("تحتاج إلى مراجعة", "Needs review")}</h2><p>{analysis.quality?.notes[0]}</p></div></article></section>
    {dashboard.filters.length>0&&<section className="filter-bar"><div><Search/><span><b>{t("تصفية جدول البيانات", "Filter data table")}</b><small>{t("تُطبق الخيارات على السجلات أدناه", "Options apply to the records below")}</small></span></div>{dashboard.filters.map((filter)=><label key={filter.column}>{filter.label}<select value={filters[filter.column]??""} onChange={(event)=>setFilters({...filters,[filter.column]:event.target.value})}><option value="">{t("الكل", "All")}</option>{filter.values.map((value)=><option key={value}>{value}</option>)}</select></label>)}</section>}
    <DataTable tableSpec={dashboard.tables[0]} filters={filters} cleaningAudit={analysis.cleaning_audit}/><SiteFooter compact go={go}/></section></main>;
}

function InsightsPage({ analysis, go }: { analysis: Analysis; go: (view: View) => void }) {
  const { locale, t } = useLanguage();
  const dashboard = analysis.dashboard!;
  const groups = [
    {id:"performance",label:t("الأداء والاتجاهات", "Performance & trends"),icon:<BarChart3/>,terms:locale==="ar"?["أداء","اتجاه","نمو","تغير","ذروة","فترة","متوسط","إيراد"]:["performance","trend","growth","change","peak","period","average","revenue"]},
    {id:"segments",label:t("الفئات والمقارنات", "Segments & comparisons"),icon:<Layers3/>,terms:locale==="ar"?["فئة","حصة","تركيز","شركة","منطقة","منتج","قناة","تصنيف","مقارنة"]:["category","share","concentration","company","region","product","channel","segment","comparison"]},
    {id:"quality",label:t("جودة البيانات", "Data quality"),icon:<ShieldCheck/>,terms:locale==="ar"?["جودة","مفقود","تكرار","شاذ","اكتمال","صالح","نوع"]:["quality","missing","duplicate","outlier","complete","valid","type"]},
  ].map((group,groupIndex,definitions)=>({...group,insights:dashboard.detailed_insights.filter((insight)=>definitions.findIndex((candidate)=>candidate.terms.some((term)=>`${insight.title} ${insight.text}`.toLowerCase().includes(term)))===groupIndex)}));
  const groupedInsights = new Set(groups.flatMap((group)=>group.insights));
  const otherInsights = dashboard.detailed_insights.filter((insight)=>!groupedInsights.has(insight));
  const visibleGroups = otherInsights.length?[...groups,{id:"other",label:t("رؤى أخرى", "Other insights"),icon:<Lightbulb/>,terms:[],insights:otherInsights}]:groups;
  return <main className="dashboard-page insights-dashboard"><DashboardNav active="insights" go={go}/><section className="dash-main insights-main"><div className="flow-heading"><span className="section-kicker">{enNumber(dashboard.detailed_insights.length)} {t("رؤى موثقة", "verified insights")}</span><h1>{t("تحليــــل يمكن تتبّعه", "Traceable analysis")}</h1><p>{t("كل استنتاج رقمي مرتبط بنتيجة محسوبة وموثقة.", "Every numeric conclusion is linked to a calculated and verified result.")}</p></div><AskBayyinah key={locale} analysisId={analysis.analysis_id} dashboard={dashboard}/><div className="insight-groups">{visibleGroups.filter((group)=>group.insights.length>0).map((group)=><section className={`insight-group ${group.id}`} key={group.id}><header><span>{group.icon}</span><h2>{group.label}</h2><b dir="ltr">{enNumber(group.insights.length)}</b></header><div className="details-list">{group.insights.map((insight,index)=><article key={`${insight.title}-${index}`}><b>{String(index+1).padStart(2,"0")}</b><div><h3>{insight.title}</h3><p>{insight.text}</p><small><ShieldCheck/> {insight.result_refs.join(" · ")}</small></div></article>)}</div></section>)}</div><SiteFooter compact go={go}/></section></main>;
}

function BayyinahAppContent() {
  const { locale, t } = useLanguage();
  const localeRef = useRef(locale);
  const [view, setView] = useState<View>("home");
  const [workbook,setWorkbook] = useState<Workbook|null>(null);
  const [preview,setPreview] = useState<Preview|null>(null);
  const [analysis,setAnalysis] = useState<Analysis|null>(null);
  const [health,setHealth] = useState<Health|null>(null);
  const [loading,setLoading] = useState(false);
  const [openingSheet,setOpeningSheet] = useState<string|null>(null);
  const [error,setError] = useState("");
  const [presentingDashboard,setPresentingDashboard] = useState(false);
  useEffect(() => { localeRef.current = locale; }, [locale]);
  useEffect(() => { let active = true; getHealth(locale).then((value) => active && setHealth(value)).catch(() => undefined); return () => { active = false; }; }, [locale]);
  useEffect(() => {
    if (!analysis?.analysis_id) return;
    let active = true;
    getAnalysis(analysis.analysis_id, locale).then((value)=>active&&setAnalysis(value)).catch(()=>undefined);
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale]);
  useEffect(() => {
    if (!workbook || !preview) return;
    let active = true;
    getPreview(workbook.file_id, preview.sheet_name, locale).then((value)=>active&&setPreview(value)).catch(()=>undefined);
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale]);
  const go = (next: View) => { setView(next); window.scrollTo({top:0,behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"}); };
  const safe = async (action: () => Promise<void>) => { setLoading(true); setError(""); try { await action(); } catch (caught) { setError(caught instanceof Error ? caught.message : t("حدث خطأ غير متوقع.", "An unexpected error occurred.")); go("error"); } finally { setLoading(false); } };
  const acceptWorkbook = (item: Workbook) => { setWorkbook(item); setOpeningSheet(null); go("sheets"); };
  const onFile = (file: File) => safe(async () => acceptWorkbook(await uploadWorkbook(file,locale)));
  const choose = (sheet: string) => {
    if (!workbook || openingSheet) return;
    setOpeningSheet(sheet);
    void safe(async () => { setPreview(await getPreview(workbook.file_id,sheet,locale)); go("preview"); }).finally(() => setOpeningSheet(null));
  };
  const waitForResult = async (initial: Analysis) => {
    let current = initial;
    let dashboardVisibleSince = current.progress >= 73 ? performance.now() : null;
    setAnalysis(current);
    while (current.status === "queued" || current.status === "running") {
      await new Promise((resolve) => window.setTimeout(resolve,800));
      current = await getAnalysis(current.analysis_id,localeRef.current);
      if (current.progress >= 73 && dashboardVisibleSince == null) dashboardVisibleSince = performance.now();
      setAnalysis(current);
    }
    if (current.status === "waiting_for_clarification") return go("clarify");
    if (current.status === "failed") return go("error");
    if (current.dashboard) {
      const visibleSince = dashboardVisibleSince ?? performance.now();
      setPresentingDashboard(true);
      await new Promise((resolve) => window.setTimeout(resolve,Math.max(0,1600-(performance.now()-visibleSince))));
      setPresentingDashboard(false);
      await new Promise((resolve) => window.setTimeout(resolve,220));
      return go("dashboard");
    }
    setError(t("اكتمل الطلب دون أن تصل لوحة نتائج صالحة.", "The request completed without a valid dashboard result."));
    go("error");
  };
  const analyze = (mode: "recommended" | "manual", overrides: MissingValueOverride[]) => safe(async () => { if (!workbook || !preview) return; setAnalysis(null); setPresentingDashboard(false); go("progress"); await waitForResult(await startAnalysis(workbook.file_id,preview.sheet_name,{},mode,overrides,locale)); });
  const clarify = (mapping:Record<string,string>) => safe(async () => { if (!analysis) return; go("progress"); await waitForResult(await resumeAnalysis(analysis.analysis_id,mapping,locale)); });
  const renderContent = () => {
    if (view === "home") return <Home go={go}/>;
    if (view === "upload") return <UploadPage onFile={onFile} loading={loading}/>;
    if (view === "sheets" && workbook) return <SheetsPage workbook={workbook} choose={choose} openingSheet={openingSheet}/>;
    if (view === "preview" && preview) return <PreviewPage preview={preview} analyze={analyze}/>;
    if (view === "clarify" && analysis) return <ClarifyPage analysis={analysis} submit={clarify}/>;
    if (view === "progress") return <ProgressPage analysis={analysis} presentingDashboard={presentingDashboard}/>;
    if (view === "dashboard" && analysis?.dashboard) return <DashboardView analysis={analysis} go={go}/>;
    if (view === "insights" && analysis?.dashboard) return <InsightsPage analysis={analysis} go={go}/>;
    if (view === "error") return <main className="center-page"><div className="empty-illustration error"><CircleAlert/></div><span className="section-kicker">{t("تعذر إكمال العملية", "Operation could not be completed")}</span><h1>{t("حدث خطأ في التحليل", "An analysis error occurred")}</h1><p>{error || analysis?.error || t("حدث خطأ غير متوقع.", "An unexpected error occurred.")}</p><button className="primary" onClick={() => go("upload")}>{t("العودة إلى رفع الملف", "Return to file upload")}</button></main>;
    return <Home go={go}/>;
  };
  const showLlmNotice = health && (health.mode === "mock" || !health.llm_ready);
  const inResults = view === "dashboard" || view === "insights";
  return <div className={`app-shell ${view === "home" ? "home-active" : ""}`}>{!inResults && <Header view={view} go={go}/>} {!inResults && showLlmNotice && <div className={`llm-notice ${health.mode}`}><CircleAlert/><div><b>{health.mode === "mock" ? t("وضع الاختبار مفعّل", "Test mode is active") : t("خدمة الذكاء الاصطناعي تحتاج إعدادًا", "AI service requires configuration")}</b><span>{health.detail}</span></div></div>} {inResults ? renderContent() : <div className="view-stage" key={view}>{renderContent()}</div>} {!inResults && <SiteFooter go={go}/>}</div>;
}

export function BayyinahApp() {
  return <LanguageProvider><BayyinahAppContent/></LanguageProvider>;
}