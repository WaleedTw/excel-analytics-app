"use client";

import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { createColumnHelper, flexRender, getCoreRowModel, getFilteredRowModel, getSortedRowModel, useReactTable } from "@tanstack/react-table";
import type { Dashboard } from "@/lib/schemas";

const PAGE_SIZE = 50;
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const integer = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const displayCell = (value: unknown) => value == null ? "—" : typeof value === "number" ? number.format(value) : String(value);

export function DataTable({ tableSpec, filters = {} }: { tableSpec: Dashboard["tables"][number]; filters?: Record<string, string> }) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const filteredRows = useMemo(
    () => tableSpec.rows.filter((row) => Object.entries(filters).every(([column, value]) => !value || String(row[column] ?? "") === value)),
    [filters, tableSpec.rows],
  );
  const columns = useMemo(() => {
    const helper = createColumnHelper<Record<string, unknown>>();
    return tableSpec.columns.map((column) => helper.accessor((row) => row[column], { id: column, header: column, cell: (info) => displayCell(info.getValue()) }));
  }, [tableSpec.columns]);
  // TanStack Table intentionally exposes stateful functions; React Compiler skips this hook safely.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({ data: filteredRows, columns, state: { globalFilter: query }, onGlobalFilterChange: (value) => { setQuery(value); setPage(0); }, getCoreRowModel: getCoreRowModel(), getFilteredRowModel: getFilteredRowModel(), getSortedRowModel: getSortedRowModel() });
  const rows = table.getRowModel().rows;
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const currentPage = Math.min(page, pages - 1);
  const from = rows.length ? currentPage * PAGE_SIZE + 1 : 0;
  const to = Math.min((currentPage + 1) * PAGE_SIZE, rows.length);

  return <section className="data-table-card">
    <div className="table-head"><div><span className="section-kicker">البيانات</span><h3>{tableSpec.title}</h3><small>جميع الصفوف متاحة — استخدم البحث أو تنقّل بين الصفحات.</small></div><input aria-label="البحث في الجدول" value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} placeholder="ابحث في جميع الصفوف…" /></div>
    <div className="table-scroll"><table><thead>{table.getHeaderGroups().map((group) => <tr key={group.id}>{group.headers.map((header) => <th key={header.id} onClick={header.column.getToggleSortingHandler()}>{flexRender(header.column.columnDef.header, header.getContext())}<span>{header.column.getIsSorted() === "asc" ? " ↑" : header.column.getIsSorted() === "desc" ? " ↓" : ""}</span></th>)}</tr>)}</thead>
    <tbody>{rows.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE).map((row) => <tr key={row.id}>{row.getVisibleCells().map((cell) => <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}</tr>)}</tbody></table></div>
    <footer className="table-pagination"><span>عرض <b dir="ltr">{integer.format(from)}–{integer.format(to)}</b> من <b dir="ltr">{integer.format(rows.length)}</b> صف</span><div><button disabled={currentPage === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}><ChevronRight/> السابق</button><b dir="ltr">{integer.format(currentPage + 1)} / {integer.format(pages)}</b><button disabled={currentPage >= pages - 1} onClick={() => setPage((value) => Math.min(pages - 1, value + 1))}>التالي <ChevronLeft/></button></div></footer>
  </section>;
}
