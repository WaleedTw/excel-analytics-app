"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import type { Dashboard } from "@/lib/schemas";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });
type Chart = Dashboard["charts"][number];
type Table = Dashboard["tables"][number];

const palette = ["#0f9f95", "#27c4b4", "#087a76", "#6ad8ca", "#355f61", "#e3a34d", "#719a97", "#a8ded6"];
const chartLabel: Record<string, string> = { donut: "توزيع نسبي", line: "اتجاه زمني", area: "اتجاه", bar: "مقارنة" };
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
    current.total += value;
    current.count += 1;
    groups.set(key, current);
  });
  let entries = [...groups].map(([name, item]) => ({ name, value: average ? item.total / item.count : item.total }));
  entries = chronological
    ? entries.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))
    : entries.sort((a, b) => b.value - a.value);
  return entries.slice(0, limit);
}

export function ChartCard({ chart, tableSpec, dimensions, measures }: { chart: Chart; tableSpec: Table; dimensions: string[]; measures: string[] }) {
  const initialDimension = dimensions.includes(chart.x_label) ? chart.x_label : dimensions[0] ?? "";
  const initialMeasure = measures.includes(chart.series[0]?.name) ? chart.series[0].name : measures[0] ?? "";
  const [dimension, setDimension] = useState(initialDimension);
  const [measure, setMeasure] = useState(initialMeasure);
  const isDistribution = chart.id === "distribution";
  const interactive = Boolean(measure && (isDistribution || dimension));
  const model = useMemo(() => {
    if (!interactive) return { categories: chart.categories, values: chart.series[0]?.values ?? [], title: chart.title };
    if (isDistribution) {
      const values = tableSpec.rows.map((row) => numeric(row[measure])).filter((value): value is number => value != null);
      const minimum = values.length ? Math.min(...values) : 0;
      const maximum = values.length ? Math.max(...values) : 0;
      const average = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
      return { categories: ["الأدنى", "المتوسط", "الأعلى"], values: [minimum, average, maximum], title: `نطاق ${measure}` };
    }
    const percentage = /percentage|percent|rate|margin|نسبة|النسبة/i.test(measure);
    const points = aggregate(tableSpec.rows, dimension, measure, percentage, chart.type === "line" ? 24 : chart.type === "donut" ? 6 : 10, chart.type === "line");
    return { categories: points.map((point) => point.name), values: points.map((point) => point.value), title: `${measure} حسب ${dimension}` };
  }, [chart, dimension, interactive, isDistribution, measure, tableSpec.rows]);

  const font = "'Thmanyah Sans', Tahoma, Arial";
  const base = {
    color: palette,
    animationDuration: 900,
    animationEasing: "cubicOut",
    textStyle: { fontFamily: font, color: "#25364b" },
    tooltip: { trigger: chart.type === "donut" ? "item" : "axis", confine: true, backgroundColor: "rgba(16,42,67,.96)", borderWidth: 0, textStyle: { fontFamily: font, color: "#fff" }, valueFormatter: (value: number) => number.format(value) },
  };
  const option = chart.type === "donut" ? {
    ...base,
    legend: { type: "scroll", bottom: 0, left: "center", width: "92%", itemWidth: 11, itemHeight: 8, textStyle: { fontFamily: font, fontSize: 10, color: "#526477" } },
    series: [{ name: measure || chart.series[0]?.name, type: "pie", radius: ["52%", "76%"], center: ["50%", "43%"], avoidLabelOverlap: true, itemStyle: { borderColor: "#fff", borderWidth: 4, borderRadius: 6 }, label: { show: true, position: "inside", formatter: "{d}%", color: "#fff", fontWeight: 800, fontSize: 10 }, labelLine: { show: false }, emphasis: { scaleSize: 8, label: { show: true, formatter: "{b}\n{d}%", fontFamily: font, fontSize: 11 } }, data: model.categories.map((name, index) => ({ name, value: model.values[index] ?? 0 })) }],
  } : {
    ...base,
    grid: { top: 25, left: 20, right: 18, bottom: 68, containLabel: true },
    xAxis: { type: "category", data: model.categories, axisTick: { alignWithLabel: true }, axisLine: { lineStyle: { color: "#b8c6d1" } }, axisLabel: { interval: 0, hideOverlap: false, rotate: model.categories.length > 5 ? 28 : 0, margin: 13, fontFamily: font, fontSize: 10, color: "#526477", width: 90, overflow: "truncate" } },
    yAxis: { type: "value", name: measure || chart.y_label, nameTextStyle: { fontFamily: font, color: "#718096", fontSize: 9 }, splitLine: { lineStyle: { color: "#e8eef2", type: "dashed" } }, axisLabel: { fontFamily: font, color: "#718096", formatter: (value: number) => compact.format(value) } },
    series: [{ name: measure || chart.series[0]?.name, data: model.values, type: chart.type === "line" || chart.type === "area" ? "line" : "bar", smooth: true, showSymbol: model.categories.length <= 12, symbolSize: 7, lineStyle: { width: 3 }, areaStyle: chart.type === "area" ? { opacity: .12 } : undefined, barMaxWidth: 40, itemStyle: { borderRadius: chart.type === "bar" ? [7, 7, 2, 2] : undefined, color: palette[0] } }],
  };
  return <article className="chart-card">
    <div className="chart-head"><div><span className="chart-type">{chartLabel[chart.type] ?? "تحليل"}</span><h3>{model.title}</h3></div><div className="chart-controls">
      {!isDistribution && dimensions.length > 0 && <label>التصنيف<select aria-label="تغيير عمود التصنيف" value={dimension} onChange={(event) => setDimension(event.target.value)}>{dimensions.map((item) => <option key={item}>{item}</option>)}</select></label>}
      {measures.length > 0 && <label>المقياس<select aria-label="تغيير عمود المقياس" value={measure} onChange={(event) => setMeasure(event.target.value)}>{measures.map((item) => <option key={item}>{item}</option>)}</select></label>}
    </div></div>
    <ReactECharts option={option} notMerge lazyUpdate style={{ height: 340 }}/>
  </article>;
}
