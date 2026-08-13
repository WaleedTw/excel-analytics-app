"use client";

import { ChangeEvent, CSSProperties, DragEvent, useEffect, useRef, useState } from "react";
import {
  Activity, ArrowLeft, Bot, Check, ChevronLeft, CircleAlert, Clock3,
  Database, FolderClock, LayoutDashboard, Loader2, Search,
  ShieldCheck, Sparkles, TrendingUp, Upload, WandSparkles,
} from "lucide-react";
import {
  getAnalysis, getHealth, getPreview, listAnalyses,
  resumeAnalysis, startAnalysis, uploadWorkbook,
} from "@/lib/api";
import type { Analysis, AnalysisSummary, Dashboard, Health, Preview, Workbook } from "@/lib/schemas";
import { ChartCard } from "./chart-card";
import { DataTable } from "./data-table";

type View = "home" | "upload" | "history" | "sheets" | "preview" | "clarify" | "progress" | "dashboard" | "insights" | "error";
const stages = ["رفع الملف", "اختيار الورقة", "معاينة البيانات", "التحليل الذكي", "اللوحة"];

const enNumber = (value: number) => new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
const displayCell = (value: unknown) => value == null ? "—" : typeof value === "number" ? enNumber(value) : String(value);
const formatMetric = (value: number | string, format: string) => {
  if (typeof value !== "number") return value;
  if (format === "currency") return new Intl.NumberFormat("en-US", { style: "currency", currency: "SAR", currencyDisplay: "code", maximumFractionDigits: 0 }).format(value);
  if (format === "percent") return new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 }).format(Math.abs(value) <= 1 ? value : value / 100);
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
};

function AnimatedMetric({ value, format }: { value: number | string; format: string }) {
  const [display, setDisplay] = useState(typeof value === "number" ? 0 : value);
  useEffect(() => {
    if (typeof value !== "number") return;
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
  return <>{formatMetric(display, format)}</>;
}

function Logo({ onClick }: { onClick?: () => void }) {
  return <button className="logo" onClick={onClick} aria-label="بينة — العودة إلى الرئيسية"><strong>بــــيّنة</strong></button>;
}

function Header({ view, go, health }: { view: View; go: (view: View) => void; health: Health | null }) {
  const label = !health ? "فحص النموذج…" : health.mode === "mock" ? "وضع الاختبار" : health.llm_ready ? `${health.model} متصل` : "النموذج غير متصل";
  return <header className="site-header"><Logo onClick={() => go("home")} /><nav aria-label="التنقل الرئيسي">
    <button className={view === "home" ? "active" : ""} onClick={() => go("home")}>الرئيسية</button>
    <button className={view === "upload" ? "active" : ""} onClick={() => go("upload")}>تحليل جديد</button>
    <button className={view === "history" ? "active" : ""} onClick={() => go("history")}>الملفات السابقة</button>
  </nav><div className={`system-badge ${health?.llm_ready ? "ready" : "not-ready"}`} title={health?.detail}><i></i>{label}</div></header>;
}

function Journey({ current }: { current: number }) {
  return <div className="journey" aria-label="مراحل التحليل">{stages.map((stage, index) => <div className={index < current ? "done" : index === current ? "current" : ""} key={stage}><span>{index < current ? <Check size={13} /> : index + 1}</span><b>{stage}</b></div>)}</div>;
}

function EmptyHistory({ go }: { go: (view: View) => void }) {
  return <main className="center-page"><div className="empty-illustration"><FolderClock /></div><span className="section-kicker">السجل المحفوظ</span><h1>لا توجد تحليلات سابقة بعد</h1><p>ستظهر هنا اللوحات المحفوظة لتعود إليها في أي وقت.</p><button className="primary" onClick={() => go("upload")}>ابدأ أول تحليل <ArrowLeft size={18} /></button></main>;
}

function HistoryPage({ go, open }: { go: (view: View) => void; open: (id: string) => void }) {
  const [items, setItems] = useState<AnalysisSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  useEffect(() => {
    let active = true;
    listAnalyses().then((value) => active && setItems(value)).catch((error: unknown) => active && setLoadError(error instanceof Error ? error.message : "تعذر تحميل السجل.")).finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);
  if (loading) return <main className="center-page"><Loader2 className="spin"/><h1>نستعيد تحليلاتك المحفوظة…</h1></main>;
  if (loadError) return <main className="center-page"><div className="empty-illustration error"><CircleAlert/></div><h1>تعذر تحميل السجل</h1><p>{loadError}</p><button className="primary" onClick={() => go("upload")}>تحليل جديد</button></main>;
  if (!items.length) return <EmptyHistory go={go}/>;
  return <main className="flow-page wide"><div className="flow-heading"><span className="section-kicker">السجل المحفوظ</span><h1>تحليلاتك السابقة</h1><p>افتح أي لوحة للعودة إلى نتائجها الموثقة.</p></div><div className="sheet-grid">{items.map((item) => <button key={item.id} onClick={() => open(item.id)}><span className="sheet-icon"><FolderClock/></span><div><h3>{item.original_name}</h3><p>{item.sheet_name} · <span dir="ltr">{new Date(item.created_at).toLocaleDateString("en-US")}</span></p></div><span className="ready">{item.status === "completed_with_fallback" ? "مسار محافظ" : "مكتمل"}</span><ChevronLeft/></button>)}</div></main>;
}

function Home({ go }: { go: (view: View) => void }) {
  return <main className="home-page home-v3"><section className="hero-section">
    <div className="hero-copy"><div className="eyebrow"><span></span> ذكاء تحليلي سحابي آمن</div><h1>ملفك يتكلم.<br/><em>بيّنة تفهمه.</em></h1><p>وكيل عربي يحوّل جداول Excel إلى قرارات مفهومة: يفحص الجودة، يختار التحليل، وينشئ لوحة قابلة للاستكشاف بأرقام موثقة.</p><div className="hero-actions"><button className="primary large" onClick={() => go("upload")}>ابدأ التحليل الآن <ArrowLeft size={20}/></button><small><ShieldCheck/> لا تُرسل صفوف الملف إلى النموذج</small></div><div className="trust-row"><span><Bot/> Groq</span><span><Activity/> LangGraph</span><span><Database/> DuckDB</span></div></div>
  </section><section className="home-proof"><div><b>01</b><span><strong>يفهم البنية</strong><small>الأبعاد والمقاييس والتواريخ</small></span></div><div><b>02</b><span><strong>يتحقق من الجودة</strong><small>النواقص والتكرار والقيم الشاذة</small></span></div><div><b>03</b><span><strong>يبني الدليل</strong><small>رسوم مرنة ورؤى قابلة للتتبّع</small></span></div></section></main>;
}

function UploadPage({ onFile, loading }: { onFile: (file: File) => void; loading: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const drop = (event: DragEvent) => { event.preventDefault(); const file = event.dataTransfer.files[0]; if (file) onFile(file); };
  return <main className="flow-page"><Journey current={0}/><div className="flow-heading"><span className="section-kicker">تحليل جديد</span><h1>ابدأ من ملف Excel</h1><p>ملف XLSX واحد، بحجم لا يتجاوز 10 ميجابايت.</p></div><section className="upload-zone" onDrop={drop} onDragOver={(event) => event.preventDefault()}><div className="upload-icon">{loading ? <Loader2 className="spin"/> : <Upload/>}</div><h2>{loading ? "نفحص الملف الآن…" : "اسحب ملفك إلى هنا"}</h2><p>أو اختره من جهازك.</p><input ref={input} type="file" accept=".xlsx" onChange={(event: ChangeEvent<HTMLInputElement>) => event.target.files?.[0] && onFile(event.target.files[0])}/><button className="primary" disabled={loading} onClick={() => input.current?.click()}>اختيار ملف</button><div className="upload-rules"><span><Check/> XLSX فقط</span><span><Check/> حسابات موثقة</span><span><Check/> فحص آمن</span></div></section></main>;
}

function SheetsPage({ workbook, choose }: { workbook: Workbook; choose: (sheet: string) => void }) {
  return <main className="flow-page wide"><Journey current={1}/><div className="flow-heading"><span className="section-kicker">تم التحقق من الملف</span><h1>اختر ورقة العمل</h1><p>{workbook.original_name} · {enNumber(workbook.sheets.length)} أوراق</p></div><div className="sheet-grid">{workbook.sheets.map((sheet, index) => <button key={sheet.name} disabled={!sheet.has_data} onClick={() => choose(sheet.name)}><span className="sheet-icon">{index + 1}</span><div><h3>{sheet.name}</h3><p>{enNumber(sheet.rows)} صف · {enNumber(sheet.columns)} عمود</p></div><span className={sheet.has_data ? "ready" : "empty"}>{sheet.has_data ? "جاهزة" : "فارغة"}</span><ChevronLeft/></button>)}</div></main>;
}

function PreviewPage({ preview, analyze }: { preview: Preview; analyze: () => void }) {
  return <main className="flow-page extra-wide"><Journey current={2}/><div className="split-heading"><div><span className="section-kicker">معاينة البيانات</span><h1>{preview.sheet_name}</h1><p>{enNumber(preview.total_rows)} صفًا · {enNumber(preview.columns.length)} أعمدة · أول {enNumber(preview.rows.length)} صفًا</p></div><button className="primary" onClick={() => analyze()}>حلّل هذه الورقة <ArrowLeft/></button></div><div className="profile-row">{preview.columns.map((column) => <article key={column.name} className={column.ambiguous ? "warn" : ""}><span>{column.semantic_role === "measure" ? "مقياس" : column.semantic_role === "date" ? "تاريخ" : column.semantic_role === "dimension" ? "بُعد" : column.semantic_role === "identifier" ? "معرّف" : "يحتاج توضيحًا"}</span><b>{column.name}</b><small><span dir="ltr">{enNumber(column.unique_count)}</span> قيمة فريدة · {column.null_count === 0 ? "لا توجد قيم مفقودة" : <><span dir="ltr">{enNumber(column.null_count)}</span> قيمة مفقودة</>}</small></article>)}</div><section className="preview-table"><table><thead><tr>{preview.columns.map((column) => <th key={column.name}>{column.name}<small>{column.inferred_type}</small></th>)}</tr></thead><tbody>{preview.rows.slice(0,12).map((row, index) => <tr key={index}>{preview.columns.map((column) => <td key={column.name}>{displayCell(row[column.name])}</td>)}</tr>)}</tbody></table></section></main>;
}

function ClarifyPage({ analysis, submit }: { analysis: Analysis; submit: (mapping: Record<string,string>) => void }) {
  const columns = (analysis.ambiguity?.columns as Array<{name:string; sample_values:unknown[]; reason:string}>) ?? [];
  const [mapping, setMapping] = useState<Record<string,string>>(() => Object.fromEntries(columns.map((column) => [column.name, "dimension"])));
  return <main className="flow-page"><Journey current={3}/><div className="clarify-card"><div className="clarify-icon"><WandSparkles/></div><span className="section-kicker">تدخل بشري ذكي</span><h1>نحتاج معنى {columns.length === 1 ? "عمود واحد" : "بعض الأعمدة"}</h1><p>أوقف LangGraph المسار وحفظ حالته. اختر المعنى الأقرب ثم سيكمل من النقطة نفسها.</p>{columns.map((column) => <div className="clarify-row" key={column.name}><div><b>{column.name}</b><span>عينة: {column.sample_values.map(String).join("، ") || "لا توجد قيم"}</span></div><select aria-label={`دور العمود ${column.name}`} value={mapping[column.name]} onChange={(event) => setMapping({...mapping, [column.name]: event.target.value})}><option value="dimension">بُعد وصفي</option><option value="measure">مقياس رقمي</option><option value="date">تاريخ</option><option value="identifier">معرّف</option></select></div>)}<button className="primary full" onClick={() => submit(mapping)}>حفظ التوضيح ومتابعة التحليل <ArrowLeft/></button><small className="memory-note"><Database/> الحالة محفوظة تحت المعرّف {analysis.analysis_id.slice(0,8)}</small></div></main>;
}

function ProgressPage({ health }: { health: Health | null }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => { const timer = window.setInterval(() => setSeconds((value) => value + 1), 1000); return () => window.clearInterval(timer); }, []);
  return <main className="flow-page"><Journey current={3}/><div className="progress-card"><div className="agent-orbit"><Bot/><span></span></div><span className="section-kicker">تنفيذ فعلي جارٍ</span><h1>الوكيل يحلل ملفك الآن</h1><p>LangGraph يدير المسار، و{health?.model ?? "Groq"} يخطط للتحليل، ثم ينفذ DuckDB الحسابات ويتحقق النظام من كل نتيجة.</p><div className="live-status"><i></i><div><b>اتصال آمن بخادم التحليل</b><small>مضى <span dir="ltr">{enNumber(seconds)}</span> ثانية</small></div><Clock3/></div><div className="progress-list"><span className="done"><Check/> اكتمل فحص الملف وبنية الأعمدة</span><span className="active"><Loader2 className="spin"/> الوكيل ينشئ الخطة وينفذ الحسابات</span><span><ShieldCheck/> التحقق من النتائج وإنشاء اللوحة</span></div></div></main>;
}

function AgentProof({ analysis }: { analysis: Analysis }) {
  const plan = analysis.analysis_plan;
  return <section className="agent-proof"><div className="agent-proof-icon"><Bot/></div><div className="agent-proof-copy"><span className="section-kicker">حالة الوكيل</span><h2>Agent فعّال ومثبت في نتيجة التحليل</h2><p>{plan?.objective ?? "تم تنفيذ المسار التحليلي المتحقق."}</p></div><div className="agent-proof-stats"><span><b>{plan?.mode === "mock" ? "Mock" : plan?.model}</b><small>التخطيط الدلالي</small></span><span><b>LangGraph</b><small>إدارة المسار</small></span><span><b dir="ltr">{enNumber(analysis.trace.length)}</b><small>خطوات موثقة</small></span><span><b>DuckDB</b><small>حساب الأرقام</small></span></div></section>;
}

function DashboardView({ analysis, go }: { analysis: Analysis; go: (view: View) => void }) {
  const dashboard = analysis.dashboard as Dashboard;
  const visibleKpis = dashboard.kpis.filter((kpi) => kpi.id !== "rows" && kpi.result_ref !== "rows.total");
  const [filters, setFilters] = useState<Record<string,string>>({});
  const score = analysis.quality?.score ?? 0;
  const ringStyle = { "--score": `${score * 3.6}deg` } as CSSProperties;
  return <main className="dashboard-page"><aside className="dash-sidebar"><Logo onClick={() => go("home")}/><nav><button className="active"><LayoutDashboard/> نظرة عامة</button><button onClick={() => go("insights")}><Sparkles/> الرؤى التفصيلية</button></nav><div className="sidebar-foot"><span><i></i> محفوظ على الخادم</span><small>{analysis.analysis_id.slice(0,8)}</small></div></aside><section className="dash-main"><header className="dash-head"><div><span className="section-kicker">لوحة تنفيذية موثقة</span><h1>{dashboard.title}</h1><p>{dashboard.description}</p></div><button className="primary" onClick={() => go("upload")}><Upload/> تحليل ملف جديد</button></header>
    <AgentProof analysis={analysis}/>
    {dashboard.warnings.length > 0 && <div className="warning-banner"><CircleAlert/><div><b>ملاحظة على جودة البيانات</b><span>{dashboard.warnings.join(" ")}</span></div></div>}
    <section className="kpi-grid">{visibleKpis.map((kpi, index) => { const result = dashboard.computed_results[kpi.result_ref]; return <article key={kpi.id} className={`${kpi.tone} kpi-${index}`}><div className="kpi-top"><span>{kpi.label}</span><TrendingUp/></div><b className="metric-value" dir="ltr" title={String(result.value)}><AnimatedMetric value={result.value} format={kpi.format}/></b><small><Check/> محسوب وموثق</small></article>; })}</section>
    <div className="section-title"><div><span className="section-kicker">الرسوم التحليلية</span><h2>الصورة الكاملة للأداء</h2></div><p>مرّر على الرسم لعرض القيمة الدقيقة.</p></div>
    <section className="charts-grid">{dashboard.charts.slice(0,4).map((chart) => <ChartCard chart={chart} tableSpec={dashboard.tables[0]} dimensions={dashboard.dimensions} measures={dashboard.measures} key={chart.id}/>)}</section>
    <section className="insight-grid quality-only"><article className="quality-card"><div className="score-ring" style={ringStyle}><span><b dir="ltr">{score}</b><small>من 100</small></span></div><div><span className="section-kicker">جودة البيانات</span><h2>{score >= 85 ? "موثوقة لاتخاذ القرار" : "تحتاج إلى مراجعة"}</h2><p>{analysis.quality?.notes[0]}</p></div></article></section>
    {dashboard.filters.length > 0 && <section className="filter-bar"><div><Search/><span><b>تصفية جدول البيانات</b><small>تُطبق الخيارات على السجلات أدناه</small></span></div>{dashboard.filters.map((filter) => <label key={filter.column}>{filter.label}<select value={filters[filter.column] ?? ""} onChange={(event) => setFilters({...filters,[filter.column]:event.target.value})}><option value="">الكل</option>{filter.values.map((value) => <option key={value}>{value}</option>)}</select></label>)}</section>}
    <DataTable tableSpec={dashboard.tables[0]} filters={filters}/></section></main>;
}

function InsightsPage({ analysis, go }: { analysis: Analysis; go: (view: View) => void }) {
  const dashboard = analysis.dashboard!;
  return <main className="flow-page wide"><button className="back" onClick={() => go("dashboard")}><ChevronLeft/> العودة إلى اللوحة</button><div className="flow-heading"><span className="section-kicker">{enNumber(dashboard.detailed_insights.length)} رؤى موثقة</span><h1>تحليل يمكن تتبّعه</h1><p>كل استنتاج رقمي مرتبط بنتيجة محفوظة من DuckDB.</p></div>{analysis.analysis_plan && <section className="agent-plan-card"><div><Bot/><span><b>خطة الوكيل الدلالية</b><small>{analysis.analysis_plan.mode === "mock" ? "Mock للاختبار فقط" : `${analysis.analysis_plan.mode === "groq" ? "Groq" : "Ollama"} · ${analysis.analysis_plan.model}`}</small></span></div><p>{analysis.analysis_plan.objective}</p><footer><span><Activity/> استراتيجية الرسوم: {analysis.analysis_plan.chart_strategy.join(" · ")}</span><span><ShieldCheck/> {analysis.analysis_plan.privacy}</span></footer></section>}<div className="details-list">{dashboard.detailed_insights.map((insight,index) => <article key={`${insight.title}-${index}`}><b>{String(index+1).padStart(2,"0")}</b><div><h2>{insight.title}</h2><p>{insight.text}</p><small><ShieldCheck/> {insight.result_refs.join(" · ")}</small></div></article>)}</div></main>;
}

export function BayyinahApp() {
  const [view, setView] = useState<View>("home");
  const [workbook,setWorkbook] = useState<Workbook|null>(null);
  const [preview,setPreview] = useState<Preview|null>(null);
  const [analysis,setAnalysis] = useState<Analysis|null>(null);
  const [health,setHealth] = useState<Health|null>(null);
  const [loading,setLoading] = useState(false);
  const [error,setError] = useState("");
  useEffect(() => { let active = true; getHealth().then((value) => active && setHealth(value)).catch(() => undefined); return () => { active = false; }; }, []);
  const go = (next: View) => { setView(next); window.scrollTo({top:0,behavior:"smooth"}); };
  const safe = async (action: () => Promise<void>) => { setLoading(true); setError(""); try { await action(); } catch (caught) { setError(caught instanceof Error ? caught.message : "حدث خطأ غير متوقع."); go("error"); } finally { setLoading(false); } };
  const acceptWorkbook = (item: Workbook) => { setWorkbook(item); go("sheets"); };
  const onFile = (file: File) => safe(async () => acceptWorkbook(await uploadWorkbook(file)));
  const choose = (sheet: string) => safe(async () => { if (!workbook) return; setPreview(await getPreview(workbook.file_id,sheet)); go("preview"); });
  const analyze = () => safe(async () => { if (!workbook || !preview) return; go("progress"); const result = await startAnalysis(workbook.file_id,preview.sheet_name); setAnalysis(result); go(result.status === "waiting_for_clarification" ? "clarify" : result.status === "failed" ? "error" : "dashboard"); });
  const clarify = (mapping:Record<string,string>) => safe(async () => { if (!analysis) return; go("progress"); const result = await resumeAnalysis(analysis.analysis_id,mapping); setAnalysis(result); go(result.status === "completed" || result.status === "completed_with_fallback" ? "dashboard" : "error"); });
  const openSaved = (analysisId: string) => safe(async () => { const result = await getAnalysis(analysisId); setAnalysis(result); go(result.dashboard ? "dashboard" : "error"); });
  const renderContent = () => {
    if (view === "home") return <Home go={go}/>;
    if (view === "upload") return <UploadPage onFile={onFile} loading={loading}/>;
    if (view === "history") return <HistoryPage go={go} open={openSaved}/>;
    if (view === "sheets" && workbook) return <SheetsPage workbook={workbook} choose={choose}/>;
    if (view === "preview" && preview) return <PreviewPage preview={preview} analyze={analyze}/>;
    if (view === "clarify" && analysis) return <ClarifyPage analysis={analysis} submit={clarify}/>;
    if (view === "progress") return <ProgressPage health={health}/>;
    if (view === "dashboard" && analysis?.dashboard) return <DashboardView analysis={analysis} go={go}/>;
    if (view === "insights" && analysis?.dashboard) return <InsightsPage analysis={analysis} go={go}/>;
    if (view === "error") return <main className="center-page"><div className="empty-illustration error"><CircleAlert/></div><span className="section-kicker">تعذر إكمال العملية</span><h1>حدث خطأ في التحليل</h1><p>{error || analysis?.error || "حدث خطأ غير متوقع."}</p><button className="primary" onClick={() => go("upload")}>العودة إلى رفع الملف</button></main>;
    return <Home go={go}/>;
  };
  const showLlmNotice = health && (health.mode === "mock" || !health.llm_ready);
  return <div className={`app-shell ${view === "home" ? "home-active" : ""}`}>{view !== "dashboard" && <Header view={view} go={go} health={health}/>} {view !== "dashboard" && showLlmNotice && <div className={`llm-notice ${health.mode}`}><CircleAlert/><div><b>{health.mode === "mock" ? "وضع الاختبار مفعّل" : "خدمة الذكاء الاصطناعي تحتاج إعدادًا"}</b><span>{health.detail}</span></div></div>} {renderContent()} {view !== "dashboard" && <footer className="site-footer"><Logo onClick={() => go("home")}/><p>تحليل آمن · أرقام موثقة · قرار أوضح</p><span>الإصدار الأكاديمي ٢٫١</span></footer>}</div>;
}
