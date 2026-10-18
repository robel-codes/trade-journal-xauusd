"use client";
import { type ColumnDef, flexRender, getCoreRowModel, getSortedRowModel, type SortingState, useReactTable } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { useState } from "react";
import { cx } from "./ui";

export function DataTable<T>({ data, columns, onRowClick, initialSort = [], empty, dense }: {
  data: T[]; columns: ColumnDef<T, unknown>[]; onRowClick?: (row: T) => void; initialSort?: SortingState; empty?: React.ReactNode; dense?: boolean;
}) {
  const [sorting, setSorting] = useState<SortingState>(initialSort);
  const table = useReactTable({ data, columns, state: { sorting }, onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() });
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[12.5px]">
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id} className="border-b border-line">
              {hg.headers.map((h) => {
                const sortable = h.column.getCanSort();
                const dir = h.column.getIsSorted();
                const align = (h.column.columnDef.meta as { align?: string } | undefined)?.align;
                return (
                  <th key={h.id} scope="col" aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : undefined}
                    className={cx("label whitespace-nowrap px-3 py-2 font-semibold", align === "right" ? "text-right" : "text-left")}>
                    {sortable ? (
                      <button type="button" onClick={h.column.getToggleSortingHandler()} className={cx("inline-flex items-center gap-1 uppercase hover:text-fg cursor-pointer", align === "right" && "flex-row-reverse")}>
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {dir === "asc" ? <ArrowUp className="size-3" /> : dir === "desc" ? <ArrowDown className="size-3" /> : <ArrowUpDown className="size-3 opacity-40" />}
                      </button>
                    ) : flexRender(h.column.columnDef.header, h.getContext())}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id}
              onClick={onRowClick ? () => onRowClick(row.original) : undefined}
              onKeyDown={onRowClick ? (e) => { if (e.key === "Enter") onRowClick(row.original); } : undefined}
              tabIndex={onRowClick ? 0 : undefined}
              className={cx("border-b border-line last:border-0", onRowClick && "cursor-pointer hover:bg-panel-2 focus-visible:bg-panel-2")}>
              {row.getVisibleCells().map((cell) => {
                const align = (cell.column.columnDef.meta as { align?: string } | undefined)?.align;
                return <td key={cell.id} className={cx("px-3 whitespace-nowrap", dense ? "py-1.5" : "py-2", align === "right" && "text-right")}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length === 0 && empty}
    </div>
  );
}
