"use client";

import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { createColumnHelper, flexRender, getCoreRowModel, getFilteredRowModel, getSortedRowModel, useReactTable } from "@tanstack/react-table";
import type { Analysis, Dashboard } from "@/lib/schemas";
import { useLanguage } from "@/lib/i18n";

const PAGE_SIZE = 50;
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const integer = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const displayCell = (value: unknown) => value == null ? "—" : typeof value === "number" ? number.format(value) : String(value);

type CleaningAudit = NonNullable<Analysis["cleaning_audit"]>;

export function DataTable({ tableSpec, filters = {}, cleaningAudit }: { tableSpec: Dashboard["tables"][number]; filters?: Record<string, string>; cleaningAudit?: CleaningAudit | null }) {
  const { t } = useLanguage();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const filteredRows = useMemo(
    () => tableSpec.rows.map((row,index):Record<string,unknown>=>({...row,__source_index:index})).filter((row) => Object.entries(filters).every(([column, value]) => !value || String(row[column] ?? "") === value)),
    [filters, tableSpec.rows],
  );
  const repairedCells = useMemo(() => new Set(cleaningAudit?.imputation_actions.filter((action)=>action.strategy!=="retained").flatMap((action)=>action.source_rows.map((sourceRow)=>`${action.column}::${sourceRow}`))??[]),[cleaningAudit]);
  const columns = useMemo(() => {
    const helper = createColumnHelper<Record<string, unknown>>();
    return tableSpec.columns.map((column) => helper.accessor((row) => row[column], { id: column, header: column, cell: (info) => displayCell(info.getValue()) }));
  }, [tableSpec.columns]);
  // TanStack Table intentionally exposes stateful functions; React Compiler skips this hook safely.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({ data: filteredRows, columns, getRowId:(row)=>String(row.__source_index), state: { globalFilter: query }, onGlobalFilterChange: (value) => { setQuery(value); setPage(0); }, getCoreRowModel: getCoreRowModel(), getFilteredRowModel: getFilteredRowModel(), getSortedRowModel: getSortedRowModel() });
  const rows = table.getRowModel().rows;
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const currentPage = Math.min(page, pages - 1);
  const from = rows.length ? currentPage * PAGE_SIZE + 1 : 0;
  const to = Math.min((currentPage + 1) * PAGE_SIZE, rows.length);

  return <section className="data-table-card">
    <div className="table-head"><div><span className="section-kicker">{t("البيانات", "Data")}</span><h3>{tableSpec.title}</h3><small>{t("جميع الصفوف متاحة — استخدم البحث أو تنقّل بين الصفحات.", "All rows are available — search or navigate between pages.")}</small></div><input aria-label={t("البحث في الجدول", "Search table")} value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} placeholder={t("ابحث في جميع الصفوف…", "Search all rows…")} /></div>
    <div className="table-scroll"><table><thead>{table.getHeaderGroups().map((group) => <tr key={group.id}>{group.headers.map((header) => <th key={header.id} onClick={header.column.getToggleSortingHandler()}>{flexRender(header.column.columnDef.header, header.getContext())}<span>{header.column.getIsSorted() === "asc" ? " ↑" : header.column.getIsSorted() === "desc" ? " ↓" : ""}</span></th>)}</tr>)}</thead>
    <tbody>{rows.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE).map((row) => {const sourceRow=cleaningAudit?.output_source_rows[Number(row.id)];return <tr key={row.id}>{row.getVisibleCells().map((cell) => {const repaired=sourceRow!=null&&repairedCells.has(`${cell.column.id}::${sourceRow}`);return <td className={repaired?"repaired-cell":undefined} title={repaired?t(`قيمة عالجها إيجنت التنظيف — صف Excel ${sourceRow}`, `Value treated by the Data Cleaning Agent — Excel row ${sourceRow}`):undefined} key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>})}</tr>})}</tbody></table></div>
    <footer className="table-pagination"><span>{t("عرض", "Showing")} <b dir="ltr">{integer.format(from)}–{integer.format(to)}</b> {t("من", "of")} <b dir="ltr">{integer.format(rows.length)}</b> {t("صف", "rows")}</span><div><button disabled={currentPage === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}><ChevronRight/> {t("السابق", "Previous")}</button><b dir="ltr">{integer.format(currentPage + 1)} / {integer.format(pages)}</b><button disabled={currentPage >= pages - 1} onClick={() => setPage((value) => Math.min(pages - 1, value + 1))}>{t("التالي", "Next")} <ChevronLeft/></button></div></footer>
  </section>;
}