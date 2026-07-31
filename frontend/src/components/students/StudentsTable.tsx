import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowUpDown, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { attentionBand, BAND_BG, cn, fmtClock, pct } from "../../lib/utils";
import type { StudentStats } from "../../types";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";

export function StudentsTable({ students }: { students: StudentStats[] }) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: "avg_attention", desc: true },
  ]);
  const [filter, setFilter] = useState("");

  const columns = useMemo<ColumnDef<StudentStats>[]>(
    () => [
      {
        accessorKey: "label",
        header: "Student",
        cell: ({ row }) => (
          <span className="font-medium">{row.original.label}</span>
        ),
      },
      {
        accessorKey: "avg_attention",
        header: "Attention",
        cell: ({ getValue }) => {
          const v = getValue<number>();
          return (
            <span className="flex items-center gap-2">
              <span className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
                <span
                  className={cn("block h-full rounded-full", BAND_BG[attentionBand(v)])}
                  style={{ width: `${v}%` }}
                />
              </span>
              <span className="tabular-nums">{v.toFixed(0)}</span>
            </span>
          );
        },
      },
      {
        accessorKey: "forward_ratio",
        header: "Forward",
        cell: ({ getValue }) => pct(getValue<number>()),
      },
      {
        accessorKey: "avg_blink_rate",
        header: "Blinks/min",
        cell: ({ getValue }) => getValue<number>().toFixed(1),
      },
      {
        accessorKey: "phone_usage_ratio",
        header: "Phone",
        cell: ({ getValue }) => {
          const v = getValue<number>();
          return v > 0.02 ? (
            <Badge variant="critical">{pct(v)}</Badge>
          ) : (
            <span className="text-muted-foreground">—</span>
          );
        },
      },
      {
        accessorKey: "hand_raised_ratio",
        header: "Hand raises",
        cell: ({ getValue }) => {
          const v = getValue<number>();
          return v > 0 ? (
            <Badge variant="good">{pct(v, 1)}</Badge>
          ) : (
            <span className="text-muted-foreground">—</span>
          );
        },
      },
      {
        accessorKey: "last_seen",
        header: "Last seen",
        cell: ({ getValue }) => (
          <span className="tabular-nums text-muted-foreground">
            {fmtClock(getValue<number>())}
          </span>
        ),
      },
    ],
    [],
  );

  const table = useReactTable({
    data: students,
    columns,
    state: { sorting, globalFilter: filter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 8 } },
  });

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold">All students</h3>
        <div className="relative w-56">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter students…"
            aria-label="Filter students"
            className="h-8 pl-8 text-xs"
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="sticky top-0 bg-card">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b border-border">
                {hg.headers.map((header) => (
                  <th key={header.id} className="px-4 py-2.5">
                    <button
                      className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-muted-foreground transition-colors hover:text-foreground"
                      onClick={header.column.getToggleSortingHandler()}
                      aria-label={`Sort by ${String(header.column.columnDef.header)}`}
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                      <ArrowUpDown className="h-3 w-3 opacity-50" aria-hidden />
                    </button>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                className="border-b border-border/60 transition-colors last:border-0 hover:bg-accent/50"
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-4 py-3">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {table.getPageCount() > 1 && (
        <div className="flex items-center justify-between border-t border-border px-4 py-2.5 text-xs text-muted-foreground">
          <span>
            Page {table.getState().pagination.pageIndex + 1} of{" "}
            {table.getPageCount()}
          </span>
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              aria-label="Previous page"
            >
              <ChevronLeft aria-hidden />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              aria-label="Next page"
            >
              <ChevronRight aria-hidden />
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
