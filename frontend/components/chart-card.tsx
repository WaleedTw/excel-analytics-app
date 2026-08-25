"use client";

import dynamic from "next/dynamic";
import { Activity, Check, ChevronDown } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Dashboard } from "@/lib/schemas";
import { useLanguage } from "@/lib/i18n";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });
type Chart = Dashboard["charts"][number];
type Table = Dashboard["tables"][number];
export type ChartSelection = { dimension: string; value: string } | null;

const palette = ["#075e5b", "#087a76", "#0b9189", "#0f9f95", "#22b8aa", "#43c8bb", "#6ad8ca", "#a8e8df"];
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });

function numeric(value: unknown) {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const parsed = Number(String(value ?? "").replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function aggregate(rows: Table["rows"], dimension: string, measure: string, average: boolean, limit: number, chronological: boolean) {
  const groups = new Map<string, { total: number; count: number }>();
  rows.forEach((row) => {
    const value = numeric(row[measure]);
    if (value == null || row[dimension] == null || String(row[dimension]).trim() === "") return;
    const key = String(row[dimension]);
    const current = groups.get(key) ?? { total: 0, count: 0 };
    current.total += value; current.count += 1; groups.set(key, current);
  });
  let entries = [...groups].map(([name,item]) => ({ name, value: average ? item.total/item.count : item.total }));
  entries = chronological ? entries.sort((a,b) => a.name.localeCompare(b.name,undefined,{numeric:true})) : entries.sort((a,b) => b.value-a.value);
  return entries.slice(0,limit);
}

function ChartPicker({ label, value, options, onChange }: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  const { t } = useLanguage();
  const picker = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const close = (event: PointerEvent) => {
      if (picker.current?.open && !picker.current.contains(event.target as Node)) picker.current.removeAttribute("open");
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);
  return <div className="chart-picker"><label className="chart-native-picker"><span>{label}</span><select aria-label={`${label}: ${value}`} value={value} onChange={(event)=>onChange(event.target.value)}>{options.map((item)=><option value={item} key={item}>{item}</option>)}</select></label><details ref={picker} onKeyDown={(event) => {
    if (event.key === "Escape") picker.current?.removeAttribute("open");
  }}><summary aria-label={`${label}: ${value}`}><span className="chart-summary-icon"><Activity/></span><span className="chart-summary-copy"><small>{label}</small><strong>{value}</strong></span><ChevronDown className="chart-summary-chevron"/></summary><div className="chart-picker-panel"><header><b>{t("اختر", "Choose")} {label}</b><span dir="ltr">{options.length}</span></header><div className="chart-picker-options" role="listbox" aria-label={label}>{options.map((item) => <button type="button" role="option" aria-selected={item === value} className={item === value ? "selected" : ""} key={item} onClick={() => {
    onChange(item);
    picker.current?.removeAttribute("open");
  }}><b>{item === value && <Check/>}</b><span>{item}</span></button>)}</div></div></details></div>;
}

export function ChartCard({ chart, tableSpec, dimensions, measures, selection, onSelectionChange }: {
  chart: Chart; tableSpec: Table; dimensions: string[]; measures: string[];
  selection?: ChartSelection; onSelectionChange?: (selection: ChartSelection) => void;
}) {
  const { t } = useLanguage();
  const chartLabel: Record<string, string> = { donut:t("توزيع نسبي", "Share"), line:t("اتجاه زمني", "Time trend"), area:t("اتجاه", "Trend"), bar:t("مقارنة", "Comparison") };
  const initialDimension = dimensions.includes(chart.x_label) ? chart.x_label : dimensions[0] ?? "";
  const initialMeasure = measures.includes(chart.series[0]?.name) ? chart.series[0].name : measures[0] ?? "";
  const [dimension,setDimension] = useState(initialDimension);
  const [measure,setMeasure] = useState(initialMeasure);
  const isDistribution = chart.id === "distribution";
  const interactive = Boolean(measure && (isDistribution || dimension));
  const chartRows = useMemo(() => !selection || selection.dimension === dimension ? tableSpec.rows : tableSpec.rows.filter((row) => String(row[selection.dimension] ?? "") === selection.value), [dimension,selection,tableSpec.rows]);
  const model = useMemo(() => {
    if (!interactive) return { categories:chart.categories, values:chart.series[0]?.values ?? [], title:chart.title };
    if (isDistribution) {
      const values = chartRows.map((row) => numeric(row[measure])).filter((value): value is number => value != null);
      const minimum = values.length ? Math.min(...values) : 0;
      const maximum = values.length ? Math.max(...values) : 0;
      const average = values.length ? values.reduce((sum,value) => sum+value,0)/values.length : 0;
      return { categories:[t("الأدنى", "Minimum"),t("المتوسط", "Average"),t("الأعلى", "Maximum")], values:[minimum,average,maximum], title:t(`نطاق ${measure}`, `${measure} range`) };
    }
    const percentage = /percentage|percent|rate|margin|نسبة|النسبة/i.test(measure);
    const points = aggregate(chartRows,dimension,measure,percentage,chart.type === "line" ? 24 : chart.type === "donut" ? 8 : 10,chart.type === "line");
    return { categories:points.map((point) => point.name), values:points.map((point) => point.value), title:t(`${measure} حسب ${dimension}`, `${measure} by ${dimension}`) };
  },[chart,chartRows,dimension,interactive,isDistribution,measure,t]);

  const font = "'Thmanyah Sans', Tahoma, Arial";
  const selectedHere = selection?.dimension === dimension ? selection.value : null;
  const data = model.categories.map((name,index) => ({ name, value:model.values[index] ?? 0, itemStyle:{color:palette[index%palette.length],opacity:selectedHere&&selectedHere!==name ? .22 : 1} }));
  const base = { color:palette, animationDuration:700, textStyle:{fontFamily:font,color:"#25364b"}, tooltip:{trigger:chart.type === "donut"?"item":"axis",confine:true,backgroundColor:"rgba(16,42,67,.96)",borderWidth:0,textStyle:{fontFamily:font,color:"#fff"},valueFormatter:(value:number)=>number.format(value)} };
  const option = chart.type === "donut" ? {
    ...base, legend:{type:"scroll",bottom:0,left:"center",width:"92%",itemWidth:11,itemHeight:8,textStyle:{fontFamily:font,fontSize:10,color:"#526477"}},
    series:[{name:measure||chart.series[0]?.name,type:"pie",radius:["61%","88%"],center:["50%","49%"],itemStyle:{borderColor:"#fff",borderWidth:4,borderRadius:6},label:{show:true,position:"inside",formatter:"{d}%",color:"#fff",fontWeight:800,fontSize:11},data}],
  } : {
    ...base, grid:{top:28,left:8,right:8,bottom:28,containLabel:true},
    xAxis:{type:"category",data:model.categories,axisLabel:{interval:0,rotate:model.categories.length>5?28:0,margin:13,fontFamily:font,fontSize:10,color:"#526477",width:90,overflow:"truncate"}},
    yAxis:{type:"value",max:(extent:{max:number})=>extent.max>0?extent.max*1.08:1,name:measure||chart.y_label,nameGap:8,nameTextStyle:{fontFamily:font,color:"#718096",fontSize:9},splitLine:{lineStyle:{color:"#e8eef2",type:"dashed"}},axisLabel:{fontFamily:font,color:"#718096",formatter:(value:number)=>compact.format(value)}},
    series:[{name:measure||chart.series[0]?.name,data,type:chart.type === "line"||chart.type === "area"?"line":"bar",smooth:true,showSymbol:model.categories.length<=12,symbolSize:8,lineStyle:{width:3,color:palette[0]},areaStyle:chart.type === "line"||chart.type === "area"?{opacity:1,color:{type:"linear",x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:"rgba(15,159,149,.34)"},{offset:.55,color:"rgba(39,196,180,.13)"},{offset:1,color:"rgba(39,196,180,0)"}]}}:undefined,barMaxWidth:54,itemStyle:{borderRadius:chart.type === "bar"?[7,7,2,2]:undefined}}],
  };
  const onEvents = onSelectionChange && !isDistribution ? { click:(params:{name?:string}) => {
    if (!params.name) return;
    const next = {dimension,value:String(params.name)};
    onSelectionChange(selection?.dimension === next.dimension && selection.value === next.value ? null : next);
  }} : undefined;
  return <article className={`chart-card ${selectedHere?"has-selection":""}`}>
    <div className="chart-head"><div><span className="chart-type">{chartLabel[chart.type]??t("تحليل", "Analysis")}</span><h3>{model.title}</h3></div><div className="chart-controls">
      {!isDistribution&&dimensions.length>0&&<ChartPicker label={t("التصنيف", "Dimension")} value={dimension} options={dimensions} onChange={setDimension}/>}
      {measures.length>0&&<ChartPicker label={t("المقياس", "Measure")} value={measure} options={measures} onChange={setMeasure}/>}
    </div></div>
    <ReactECharts className="chart-plot" option={option} onEvents={onEvents} notMerge lazyUpdate style={{height:"100%",minHeight:245}}/>
  </article>;
}