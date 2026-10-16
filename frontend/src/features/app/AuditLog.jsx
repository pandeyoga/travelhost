import { useMemo, useState } from "react";
import { ShieldCheck, Search } from "lucide-react";
import { useResource } from "@/hooks/useResource";
import DataTable from "@/components/shared/DataTable";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { StatusPill } from "@/components/shared/StatusPill";
import { formatDateTime } from "@/utils/formatters";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const ACTION_LABEL = { create: "Tambah", update: "Ubah", delete: "Hapus", confirm: "Konfirmasi", cancel: "Batal", complete: "Selesai" };
const ACTION_TONE = { create: "success", update: "info", delete: "danger", confirm: "success", cancel: "danger", complete: "info" };
const ENTITY_LABEL = { vehicle: "Armada", driver: "Driver", customer: "Customer", payment: "Pembayaran", expense: "Pengeluaran", invoice: "Invoice", settings: "Pengaturan", booking: "Booking" };

export default function AuditLog() {
  const [entityType, setEntityType] = useState("all");
  const [action, setAction] = useState("all");
  const [q, setQ] = useState("");

  const path = useMemo(() => {
    const p = new URLSearchParams();
    if (entityType !== "all") p.set("entity_type", entityType);
    if (action !== "all") p.set("action", action);
    if (q.trim()) p.set("q", q.trim());
    const qs = p.toString();
    return `/audit-logs${qs ? `?${qs}` : ""}`;
  }, [entityType, action, q]);

  const { data, loading, error, reload } = useResource(path);
  const rows = Array.isArray(data) ? data : [];

  const columns = [
    { key: "timestamp", label: "Waktu", render: (r) => <span className="tabular-nums text-[#3A3A3C]">{formatDateTime(r.timestamp)}</span> },
    {
      key: "actor", label: "Aktor", render: (r) => (
        <span className="font-semibold text-[#1C1C1E]">
          {r.actor_name || "Sistem"}
          {r.actor_role ? <span className="ml-1 text-[11px] font-normal text-[#8E8E93]">({r.actor_role})</span> : null}
        </span>
      ),
    },
    { key: "action", label: "Aksi", render: (r) => <StatusPill value={ACTION_LABEL[r.action] || r.action} tone={ACTION_TONE[r.action] || "neutral"} /> },
    { key: "entity_type", label: "Entitas", render: (r) => ENTITY_LABEL[r.entity_type] || r.entity_type || "-" },
    { key: "summary", label: "Ringkasan", render: (r) => <span className="text-[#3A3A3C]">{r.summary || "-"}</span> },
    { key: "entity_id", label: "ID Objek", mono: true, render: (r) => <span className="text-[12px] text-[#6B6B73]">{r.entity_id || "-"}</span> },
  ];

  const Filters = (
    <div className="flex flex-wrap items-center gap-2" data-testid="auditlog-filters">
      <div className="relative">
        <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[#8E8E93]" />
        <Input className="h-9 w-52 pl-8" placeholder="Cari ringkasan / aktor / ID"
          value={q} onChange={(e) => setQ(e.target.value)} data-testid="auditlog-search-input" />
      </div>
      <Select value={entityType} onValueChange={setEntityType}>
        <SelectTrigger className="h-9 w-40" data-testid="auditlog-entity-select"><SelectValue placeholder="Semua entitas" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Semua entitas</SelectItem>
          {Object.entries(ENTITY_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
        </SelectContent>
      </Select>
      <Select value={action} onValueChange={setAction}>
        <SelectTrigger className="h-9 w-36" data-testid="auditlog-action-select"><SelectValue placeholder="Semua aksi" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Semua aksi</SelectItem>
          {Object.entries(ACTION_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );

  return (
    <div data-testid="auditlog-page" className="space-y-4">
      {loading ? (
        <LoadingState testId="auditlog-loading" />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : rows.length === 0 ? (
        <div className="section-card">
          <div className="section-head">
            <div className="flex min-w-0 items-center gap-2"><ShieldCheck size={16} className="text-[#007AFF]" /><h2 className="truncate">Jejak Audit</h2></div>
            <div className="flex flex-wrap items-center justify-end gap-2">{Filters}</div>
          </div>
          <EmptyState title="Belum ada jejak audit" description="Aksi sensitif (ubah master, keuangan, pengaturan, hapus) akan tercatat otomatis di sini." testId="auditlog-empty" />
        </div>
      ) : (
        <DataTable
          title="Jejak Audit"
          icon={ShieldCheck}
          actions={Filters}
          columns={columns}
          rows={rows}
          footer={`${rows.length} entri terbaru`}
          testId="auditlog-table"
        />
      )}
    </div>
  );
}
