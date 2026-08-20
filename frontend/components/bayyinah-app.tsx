"use client";

import { ChangeEvent, CSSProperties, DragEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity, ArrowLeft, BarChart3, Bot, Check, ChevronDown, ChevronLeft, CircleAlert,
  Clock3, Database, Layers3, LayoutDashboard, Lightbulb, Loader2, MessageCircleQuestion, Search,
  Send, ShieldCheck, Sparkles, TrendingUp, Upload, WandSparkles, X,
} from "lucide-react";
import {
  askAnalysis, getAnalysis, getHealth, getPreview, resumeAnalysis, startAnalysis,
  uploadWorkbook,
} from "@/lib/api";
import type { Analysis, Dashboard, Health, Preview, Workbook } from "@/lib/schemas";
import { ChartCard, type ChartSelection } from "./chart-card";
import { DataTable } from "./data-table";

type View = "home" | "upload" | "sheets" | "preview" | "clarify" | "progress" | "dashboard" | "insights" | "error";
const stages = ["رفع الملف", "اختيار الورقة", "معاينة البيانات", "التحليل الذكي", "اللوحة"];
const stageLabels: Record<string, string> = {
  queued: "تم إدراج التحليل في قائمة التنفيذ",
  validate_file: "التحقق من أمان الملف",
  inspect_workbook: "فحص أوراق ملف Excel",
  detect_tables: "اكتشاف الجداول القابلة للتحليل",
  infer_semantics: "فهم أنواع الأعمدة وأدوارها",
  detect_ambiguities: "فحص الأعمدة التي تحتاج توضيحًا",
  request_user_clarification: "انتظار توضيح معنى الأعمدة",
  resume_queued: "استئناف التحليل بعد التوضيح",
  profile_dataset: "قياس جودة البيانات",
  create_analysis_plan: "إنشاء خطة التحليل",
  execute_analysis: "تنفيذ الحسابات",
  validate_results: "التحقق من صحة النتائج",
  generate_dashboard_spec: "تجهيز الرسوم والمؤشرات",
  generate_insights: "صياغة الرؤى النهائية",
  save_analysis: "تجهيز النتيجة للجلسة الحالية",
  fallback_analysis: "تشغيل المسار التحليلي الاحتياطي",
  handle_failure: "إيقاف التحليل بأمان",
  background_failure: "تعذر إكمال مهمة التحليل",
};

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
  return <>{formatMetric(display, format)}</>;
}

function Logo({ onClick }: { onClick?: () => void }) {
  return <button className="logo" onClick={onClick} aria-label="بينة — العودة إلى الرئيسية"><strong>بــــيّنة</strong></button>;
}

function Header({ view, go }: { view: View; go: (view: View) => void }) {
  return <header className="site-header"><Logo onClick={() => go("home")} /><nav aria-label="التنقل الرئيسي">
    <button className={view === "home" ? "active" : ""} aria-current={view === "home" ? "page" : undefined} onClick={() => go("home")}>الرئيسية</button>
    <button className={view === "upload" ? "active" : ""} aria-current={view === "upload" ? "page" : undefined} onClick={() => go("upload")}>تحليل جديد</button>
  </nav></header>;
}

function Journey({ current }: { current: number }) {
  return <div className="journey" aria-label="مراحل التحليل">{stages.map((stage, index) => <div className={index < current ? "done" : index === current ? "current" : ""} aria-current={index === current ? "step" : undefined} key={stage}><span>{index < current ? <Check size={13} /> : index + 1}</span><b>{stage}</b></div>)}</div>;
}

function Home({ go }: { go: (view: View) => void }) {
  return <main className="home-page home-apple"><section className="hero-section">
    <div className="hero-copy">
      <div className="eyebrow"><Sparkles/> تحليــــل عربي واضح</div>
      <h1>حوّل الأرقــــام إلى<br/><em>قــــرار واضــــح.</em></h1>
      <p>ارفع ملف Excel واترك «بيّنة» تفهم بنيته، تتحقق من جودته، ثم تبني لك لوحة تفاعلية بأرقام قابلة للتتبّع.</p>
      <div className="hero-actions"><button className="primary large hero-primary" onClick={() => go("upload")}>ابــــدأ تحليل ملفك <ArrowLeft size={20}/></button></div>
      <div className="trust-row"><span><ShieldCheck/> حسابات موثقة</span><span><BarChart3/> رسوم تفاعلية</span><span><Database/> يدعم ملفات XLSX</span></div>
    </div>
  </section><section className="home-proof"><div><b>01</b><span><strong>يفهــــم البنية</strong><small>الأبعاد والمقاييس والتواريخ</small></span></div><div><b>02</b><span><strong>يتحقّــــق من الجودة</strong><small>النواقص والتكرار والقيم الشاذة</small></span></div><div><b>03</b><span><strong>يشــــرح النتيجة</strong><small>رسوم ورؤى قابلة للتتبّع</small></span></div></section></main>;
}

function UploadPage({ onFile, loading }: { onFile: (file: File) => void; loading: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [dragActive,setDragActive] = useState(false);
  const drop = (event: DragEvent) => { event.preventDefault(); setDragActive(false); const file = event.dataTransfer.files[0]; if (file) onFile(file); };
  return <main className="flow-page"><Journey current={0}/><div className="flow-heading"><span className="section-kicker">تحليل جديد</span><h1>ابــــدأ من ملف Excel</h1><p>ملف XLSX واحد، بحجم لا يتجاوز 10 ميجابايت.</p></div><section className={`upload-zone ${dragActive ? "drag-active" : ""}`} aria-busy={loading} onDrop={drop} onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }} onDragLeave={() => setDragActive(false)} onDragOver={(event) => event.preventDefault()}><div className="upload-icon">{loading ? <Loader2 className="spin"/> : <Upload/>}</div><h2>{loading ? "نفحص الملف الآن…" : dragActive ? "اترك الملف هنا" : "اسحب ملفك إلى هنا"}</h2><p>أو اختره من جهازك.</p><input ref={input} type="file" accept=".xlsx" onChange={(event: ChangeEvent<HTMLInputElement>) => event.target.files?.[0] && onFile(event.target.files[0])}/><button className="primary" disabled={loading} onClick={() => input.current?.click()}>اختيار ملف</button><div className="upload-rules"><span><Check/> XLSX فقط</span><span><Check/> حسابات موثقة</span><span><Check/> فحص آمن</span></div></section></main>;
}

function SheetsPage({ workbook, choose }: { workbook: Workbook; choose: (sheet: string) => void }) {
  return <main className="flow-page wide"><Journey current={1}/><div className="flow-heading"><span className="section-kicker">تم التحقق من الملف</span><h1>اختــــر ورقة العمل</h1><p>{workbook.original_name} · {enNumber(workbook.sheets.length)} أوراق</p></div><div className="sheet-grid">{workbook.sheets.map((sheet, index) => <button key={sheet.name} disabled={!sheet.has_data} onClick={() => choose(sheet.name)}><span className="sheet-icon">{index + 1}</span><div><h3>{sheet.name}</h3><p>{enNumber(sheet.rows)} صف · {enNumber(sheet.columns)} عمود</p></div><span className={sheet.has_data ? "ready" : "empty"}>{sheet.has_data ? "جاهزة" : "فارغة"}</span><ChevronLeft/></button>)}</div></main>;
}

function PreviewPage({ preview, analyze }: { preview: Preview; analyze: () => void }) {
  return <main className="flow-page extra-wide"><Journey current={2}/><div className="split-heading"><div><span className="section-kicker">معاينة البيانات</span><h1>{preview.sheet_name}</h1><p>{enNumber(preview.total_rows)} صفًا · {enNumber(preview.columns.length)} أعمدة · أول {enNumber(preview.rows.length)} صفًا</p></div><button className="primary" onClick={() => analyze()}>حلّل هذه الورقة <ArrowLeft/></button></div><div className="profile-row">{preview.columns.map((column) => <article key={column.name} className={column.ambiguous ? "warn" : ""}><span>{column.semantic_role === "measure" ? "مقياس" : column.semantic_role === "date" ? "تاريخ" : column.semantic_role === "dimension" ? "بُعد" : column.semantic_role === "identifier" ? "معرّف" : "يحتاج توضيحًا"}</span><b>{column.name}</b><small><span dir="ltr">{enNumber(column.unique_count)}</span> قيمة فريدة · {column.null_count === 0 ? "لا توجد قيم مفقودة" : <><span dir="ltr">{enNumber(column.null_count)}</span> قيمة مفقودة</>}</small></article>)}</div><section className="preview-table"><table><thead><tr>{preview.columns.map((column) => <th key={column.name}>{column.name}<small>{column.inferred_type}</small></th>)}</tr></thead><tbody>{preview.rows.slice(0,12).map((row, index) => <tr key={index}>{preview.columns.map((column) => <td key={column.name}>{displayCell(row[column.name])}</td>)}</tr>)}</tbody></table></section></main>;
}

function ClarifyPage({ analysis, submit }: { analysis: Analysis; submit: (mapping: Record<string,string>) => void }) {
  const columns = (analysis.ambiguity?.columns as Array<{name:string; sample_values:unknown[]; reason:string}>) ?? [];
  const [mapping, setMapping] = useState<Record<string,string>>(() => Object.fromEntries(columns.map((column) => [column.name, "dimension"])));
  return <main className="flow-page"><Journey current={3}/><div className="clarify-card"><div className="clarify-icon"><WandSparkles/></div><span className="section-kicker">تدخل بشري ذكي</span><h1>نحتاج معنى {columns.length === 1 ? "عمود واحد" : "بعض الأعمدة"}</h1><p>أوقف النظام المسار وحفظ حالته. اختر المعنى الأقرب ثم سيكمل من النقطة نفسها.</p>{columns.map((column) => <div className="clarify-row" key={column.name}><div><b>{column.name}</b><span>عينة: {column.sample_values.map(String).join("، ") || "لا توجد قيم"}</span></div><select aria-label={`دور العمود ${column.name}`} value={mapping[column.name]} onChange={(event) => setMapping({...mapping, [column.name]: event.target.value})}><option value="dimension">بُعد وصفي</option><option value="measure">مقياس رقمي</option><option value="date">تاريخ</option><option value="identifier">معرّف</option></select></div>)}<button className="primary full" onClick={() => submit(mapping)}>حفظ التوضيح ومتابعة التحليل <ArrowLeft/></button><small className="memory-note"><Database/> الحالة محفوظة تحت المعرّف {analysis.analysis_id.slice(0,8)}</small></div></main>;
}

function ProgressPage({ analysis }: { analysis: Analysis | null }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => { const timer = window.setInterval(() => setSeconds((value) => value + 1), 1000); return () => window.clearInterval(timer); }, []);
  const progress = analysis?.progress ?? 0;
  const stage = stageLabels[analysis?.stage ?? "queued"] ?? "جارٍ تنفيذ التحليل";
  return <main className="flow-page"><Journey current={3}/><div className="progress-card"><div className="agent-orbit"><Bot/><span></span></div><span className="section-kicker">تنفيذ خلفي فعلي</span><h1>يتم تحليــــل ملفك الآن</h1><p>يمكنك متابعة المرحلة والنسبة الفعلية المرسلة من الخادم أثناء تنفيذ المهمة.</p><div className="real-progress" aria-label={`اكتمل ${progress}% من التحليل`}><div><span style={{width:`${progress}%`}}></span></div><b dir="ltr">{progress}%</b></div><div className="live-status"><i></i><div><b>{stage}</b><small>مضى <span dir="ltr">{enNumber(seconds)}</span> ثانية · {enNumber(analysis?.trace.length ?? 0)} مراحل مسجّلة</small></div><Clock3/></div><div className="progress-list"><span className={progress >= 31 ? "done" : "active"}>{progress >= 31 ? <Check/> : <Loader2 className="spin"/>} فحص الملف وفهم الأعمدة</span><span className={progress >= 73 ? "done" : progress >= 38 ? "active" : ""}>{progress >= 73 ? <Check/> : progress >= 38 ? <Loader2 className="spin"/> : <ShieldCheck/>} التخطيط وتنفيذ الحسابات</span><span className={progress >= 100 ? "done" : progress >= 73 ? "active" : ""}>{progress >= 100 ? <Check/> : progress >= 73 ? <Loader2 className="spin"/> : <ShieldCheck/>} التحقق وتجهيز لوحة النتائج</span></div></div></main>;
}

function AgentProof({ analysis }: { analysis: Analysis }) {
  const plan = analysis.analysis_plan;
  return <section className="agent-proof"><div className="agent-proof-icon"><Bot/></div><div className="agent-proof-copy"><span className="section-kicker">نتيجة التحليل</span><h2>اكتمل المسار وتحقّقــــت النتائج</h2><p>{plan?.objective ?? "تم تنفيذ المسار التحليلي المتحقق."}</p></div><details className="trace-disclosure"><summary><span className="trace-summary-icon"><Activity/></span><span className="trace-summary-copy"><small>المراحل التنفيذية</small><strong><b dir="ltr">{enNumber(analysis.trace.length)}</b> مراحل تنفيذ مسجّلة</strong></span><span className="trace-status"><Check/> مكتمل</span><ChevronDown className="trace-chevron"/></summary><div className="trace-panel"><header><b>المراحل التنفيذية</b><span dir="ltr">{enNumber(analysis.trace.length)}</span></header><ol>{analysis.trace.map((step,index) => <li key={`${step}-${index}`}><b><Check/></b><span><small dir="ltr">{String(index+1).padStart(2,"0")}</small>{step}</span></li>)}</ol></div></details></section>;
}

function numericCell(value: unknown) {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const parsed = Number(String(value ?? "").replace(/,/g,""));
  return Number.isFinite(parsed) ? parsed : null;
}

function AskBayyinah({ analysisId }: { analysisId: string }) {
  const [question,setQuestion] = useState("");
  const [answer,setAnswer] = useState("");
  const [sources,setSources] = useState<string[]>([]);
  const [busy,setBusy] = useState(false);
  const [failure,setFailure] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault(); if (question.trim().length < 2 || busy) return;
    setBusy(true); setFailure("");
    try { const result = await askAnalysis(analysisId,question.trim()); setAnswer(result.answer); setSources(result.sources); }
    catch (caught) { setFailure(caught instanceof Error ? caught.message : "تعذر إرسال السؤال."); }
    finally { setBusy(false); }
  };
  return <section className="ask-bayyinah"><header><div className="ask-icon"><MessageCircleQuestion/></div><div><span className="section-kicker">مساعد النتائج</span><h2>اسأل بيّنة عن التحليل</h2><p>اطرح سؤالًا عن المؤشرات أو الفئات أو الاتجاهات الظاهرة في هذه النتيجة.</p></div></header><form onSubmit={submit}><input value={question} onChange={(event)=>setQuestion(event.target.value)} maxLength={500} placeholder="مثال: ما الفئة الأعلى أداءً؟" aria-label="سؤالك عن التحليل"/><button className="primary" disabled={busy||question.trim().length<2}>{busy?<Loader2 className="spin"/>:<Send/>} إرسال</button></form>{failure&&<div className="ask-error"><CircleAlert/>{failure}</div>}{answer&&<article className="ask-answer"><b>إجابة بيّنة</b><p>{answer}</p><small>{sources.join(" · ")}</small></article>}</section>;
}

function DashboardNav({ active, go }: { active: "dashboard" | "insights"; go: (view: View) => void }) {
  return <aside className="dash-sidebar"><button className="dash-brand" onClick={() => go("home")} aria-label="بينة — العودة إلى الرئيسية"><strong>بــــيّنة</strong></button><nav aria-label="أقسام لوحة التحليل"><button className={active === "dashboard" ? "active" : ""} aria-current={active === "dashboard" ? "page" : undefined} onClick={() => go("dashboard")}><LayoutDashboard/><span>نظرة عامة</span></button><button className={active === "insights" ? "active" : ""} aria-current={active === "insights" ? "page" : undefined} onClick={() => go("insights")}><Sparkles/><span>الرؤى التفصيلية</span></button></nav></aside>;
}

function DashboardView({ analysis, go }: { analysis: Analysis; go: (view: View) => void }) {
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
  return <main className="dashboard-page"><DashboardNav active="dashboard" go={go}/><section className="dash-main"><header className="dash-head"><div><span className="section-kicker">لوحة تنفيذية موثقة</span><h1>{dashboard.title}</h1><p>{dashboard.description}</p></div><button className="primary" onClick={()=>go("upload")}><Upload/> تحليل ملف جديد</button></header>
    <AgentProof analysis={analysis}/>
    {dashboard.warnings.length>0&&<div className="warning-banner"><CircleAlert/><div><b>ملاحظة على جودة البيانات</b><span>{dashboard.warnings.join(" ")}</span></div></div>}
    {selection&&<div className="active-selection"><span>التصفية النشطة: <b>{selection.dimension}</b> = <strong>{selection.value}</strong></span><button onClick={()=>setSelection(null)}><X/> مسح التحديد</button></div>}
    <section className="kpi-grid">{visibleKpis.map((kpi,index)=>{const value=metricValue(kpi.result_ref);return <article key={kpi.id} className={`${kpi.tone} kpi-${index}`}><div className="kpi-top"><span>{kpi.label}</span><TrendingUp/></div><b className="metric-value" dir="ltr" title={String(value)}><AnimatedMetric value={value} format={kpi.format}/></b><small><Check/> {selection?"محدّث حسب التحديد":"محسوب وموثق"}</small></article>;})}</section>
    <div className="section-title"><div><span className="section-kicker">الرسوم التحليلية</span><h2>الصــــورة الكاملة للأداء</h2></div><p>اضغط على أي فئة لتصفية جميع الرسومات والمؤشرات.</p></div>
    <section className="charts-grid">{dashboard.charts.slice(0,5).map((chart)=><ChartCard chart={chart} tableSpec={dashboard.tables[0]} dimensions={dashboard.dimensions} measures={dashboard.measures} selection={selection} onSelectionChange={setSelection} key={chart.id}/>)}</section>
    <section className="insight-grid quality-only"><article className="quality-card"><div className="score-ring" style={ringStyle}><span><b dir="ltr">{score}</b><small>من 100</small></span></div><div><span className="section-kicker">جودة البيانات</span><h2>{score>=85?"موثوقة لاتخاذ القرار":"تحتاج إلى مراجعة"}</h2><p>{analysis.quality?.notes[0]}</p></div></article></section>
    {dashboard.filters.length>0&&<section className="filter-bar"><div><Search/><span><b>تصفية جدول البيانات</b><small>تُطبق الخيارات على السجلات أدناه</small></span></div>{dashboard.filters.map((filter)=><label key={filter.column}>{filter.label}<select value={filters[filter.column]??""} onChange={(event)=>setFilters({...filters,[filter.column]:event.target.value})}><option value="">الكل</option>{filter.values.map((value)=><option key={value}>{value}</option>)}</select></label>)}</section>}
    <DataTable tableSpec={dashboard.tables[0]} filters={filters}/></section></main>;
}

function InsightsPage({ analysis, go }: { analysis: Analysis; go: (view: View) => void }) {
  const dashboard = analysis.dashboard!;
  const groups = [
    {id:"performance",label:"الأداء والاتجاهات",icon:<BarChart3/>,terms:["أداء","اتجاه","نمو","تغير","ذروة","فترة","متوسط","إيراد"]},
    {id:"segments",label:"الفئات والمقارنات",icon:<Layers3/>,terms:["فئة","حصة","تركيز","شركة","منطقة","منتج","قناة","تصنيف","مقارنة"]},
    {id:"quality",label:"جودة البيانات",icon:<ShieldCheck/>,terms:["جودة","مفقود","تكرار","شاذ","اكتمال","صالح","نوع"]},
  ].map((group,groupIndex,definitions)=>({...group,insights:dashboard.detailed_insights.filter((insight)=>definitions.findIndex((candidate)=>candidate.terms.some((term)=>`${insight.title} ${insight.text}`.includes(term)))===groupIndex)}));
  const groupedInsights = new Set(groups.flatMap((group)=>group.insights));
  const otherInsights = dashboard.detailed_insights.filter((insight)=>!groupedInsights.has(insight));
  const visibleGroups = otherInsights.length?[...groups,{id:"other",label:"رؤى أخرى",icon:<Lightbulb/>,terms:[],insights:otherInsights}]:groups;
  return <main className="dashboard-page insights-dashboard"><DashboardNav active="insights" go={go}/><section className="dash-main insights-main"><div className="flow-heading"><span className="section-kicker">{enNumber(dashboard.detailed_insights.length)} رؤى موثقة</span><h1>تحليــــل يمكن تتبّعه</h1><p>كل استنتاج رقمي مرتبط بنتيجة محسوبة وموثقة.</p></div>{analysis.analysis_plan && <section className="agent-plan-card"><div><Bot/><span><b>خطة الوكيل الدلالية</b><small>خطة موثقة من خدمة الذكاء الاصطناعي</small></span></div><p>{analysis.analysis_plan.objective}</p><footer><span><Activity/> استراتيجية الرسوم: {analysis.analysis_plan.chart_strategy.join(" · ")}</span><span><ShieldCheck/> {analysis.analysis_plan.privacy}</span></footer></section>}<AskBayyinah analysisId={analysis.analysis_id}/><div className="insight-groups">{visibleGroups.filter((group)=>group.insights.length>0).map((group)=><section className={`insight-group ${group.id}`} key={group.id}><header><span>{group.icon}</span><h2>{group.label}</h2><b dir="ltr">{enNumber(group.insights.length)}</b></header><div className="details-list">{group.insights.map((insight,index)=><article key={`${insight.title}-${index}`}><b>{String(index+1).padStart(2,"0")}</b><div><h3>{insight.title}</h3><p>{insight.text}</p><small><ShieldCheck/> {insight.result_refs.join(" · ")}</small></div></article>)}</div></section>)}</div></section></main>;
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
  const go = (next: View) => { setView(next); window.scrollTo({top:0,behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"}); };
  const safe = async (action: () => Promise<void>) => { setLoading(true); setError(""); try { await action(); } catch (caught) { setError(caught instanceof Error ? caught.message : "حدث خطأ غير متوقع."); go("error"); } finally { setLoading(false); } };
  const acceptWorkbook = (item: Workbook) => { setWorkbook(item); go("sheets"); };
  const onFile = (file: File) => safe(async () => acceptWorkbook(await uploadWorkbook(file)));
  const choose = (sheet: string) => safe(async () => { if (!workbook) return; setPreview(await getPreview(workbook.file_id,sheet)); go("preview"); });
  const waitForResult = async (initial: Analysis) => {
    let current = initial;
    setAnalysis(current);
    while (current.status === "queued" || current.status === "running") {
      await new Promise((resolve) => window.setTimeout(resolve,800));
      current = await getAnalysis(current.analysis_id);
      setAnalysis(current);
    }
    if (current.status === "waiting_for_clarification") return go("clarify");
    if (current.status === "failed") return go("error");
    if (current.dashboard) return go("dashboard");
    setError("اكتمل الطلب دون أن تصل لوحة نتائج صالحة.");
    go("error");
  };
  const analyze = () => safe(async () => { if (!workbook || !preview) return; setAnalysis(null); go("progress"); await waitForResult(await startAnalysis(workbook.file_id,preview.sheet_name)); });
  const clarify = (mapping:Record<string,string>) => safe(async () => { if (!analysis) return; go("progress"); await waitForResult(await resumeAnalysis(analysis.analysis_id,mapping)); });
  const renderContent = () => {
    if (view === "home") return <Home go={go}/>;
    if (view === "upload") return <UploadPage onFile={onFile} loading={loading}/>;
    if (view === "sheets" && workbook) return <SheetsPage workbook={workbook} choose={choose}/>;
    if (view === "preview" && preview) return <PreviewPage preview={preview} analyze={analyze}/>;
    if (view === "clarify" && analysis) return <ClarifyPage analysis={analysis} submit={clarify}/>;
    if (view === "progress") return <ProgressPage analysis={analysis}/>;
    if (view === "dashboard" && analysis?.dashboard) return <DashboardView analysis={analysis} go={go}/>;
    if (view === "insights" && analysis?.dashboard) return <InsightsPage analysis={analysis} go={go}/>;
    if (view === "error") return <main className="center-page"><div className="empty-illustration error"><CircleAlert/></div><span className="section-kicker">تعذر إكمال العملية</span><h1>حدث خطأ في التحليل</h1><p>{error || analysis?.error || "حدث خطأ غير متوقع."}</p><button className="primary" onClick={() => go("upload")}>العودة إلى رفع الملف</button></main>;
    return <Home go={go}/>;
  };
  const showLlmNotice = health && (health.mode === "mock" || !health.llm_ready);
  const inResults = view === "dashboard" || view === "insights";
  return <div className={`app-shell ${view === "home" ? "home-active" : ""}`}>{!inResults && <Header view={view} go={go}/>} {!inResults && showLlmNotice && <div className={`llm-notice ${health.mode}`}><CircleAlert/><div><b>{health.mode === "mock" ? "وضع الاختبار مفعّل" : "خدمة الذكاء الاصطناعي تحتاج إعدادًا"}</b><span>{health.detail}</span></div></div>} {inResults ? renderContent() : <div className="view-stage" key={view}>{renderContent()}</div>} {!inResults && <footer className="site-footer"><Logo onClick={() => go("home")}/></footer>}</div>;
}