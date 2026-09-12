// AttentionPanel.jsx — panel "Perlu Perhatian" pada Kalender Keberangkatan.
//
// Menggantikan banner "bentrok armada" lama yang praktis selalu 0 (INV-4 sudah dikunci
// backend di semua jalur tulis). Sumber data: GET /api/departures/attention.
import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, ShieldCheck, ArrowRight, RefreshCw } from "lucide-react";
import { RiskBadge, RiskChip, SeverityDot } from "./RiskIndicators";
import { severityStyleOf, timeOfIso, MONTHS_SHORT } from "./calendarCore";

const PREVIEW = 4;

const whenLabel = (iso) => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return `${d.getDate()} ${MONTHS_SHORT[d.getMonth()]} · ${timeOfIso(iso)}`;
};

export default function AttentionPanel({
  data, loading, riskFilter, onFilter, onOpen, onRefresh, periodLabel,
}) {
  const [open, setOpen] = useState(true);
  const [showAll, setShowAll] = useState(false);
  const items = data?.items || [];
  const summary = data?.summary || { total: 0, high: 0, medium: 0, by_type: {} };
  const meta = data?.meta || [];

  // Daftar mengikuti chip yang aktif — klik "Bentrok sopir 2" harus memperlihatkan 2 item itu,
  // bukan seluruh daftar (inkonsistensi yang tertangkap saat verifikasi UI).
  const typeFilter = riskFilter && riskFilter !== "any" ? riskFilter : null;
  const shown = typeFilter ? items.filter((it) => it.risk_types.includes(typeFilter)) : items;
  const activeLabel = typeFilter ? (meta.find((m) => m.type === typeFilter) || {}).label : null;

  if (loading) {
    return (
      <div className="rounded-2xl border border-[#EFF0F2] bg-white p-4" data-testid="dc-attention-loading">
        <div className="h-4 w-56 animate-pulse rounded bg-[#F1F2F6]" />
        <div className="mt-3 flex gap-2">
          <div className="h-6 w-28 animate-pulse rounded-full bg-[#F1F2F6]" />
          <div className="h-6 w-32 animate-pulse rounded-full bg-[#F1F2F6]" />
          <div className="h-6 w-24 animate-pulse rounded-full bg-[#F1F2F6]" />
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-[#D8F1DF] bg-[#F2FBF5] px-4 py-3"
        data-testid="dc-attention-empty">
        <span className="inline-flex items-center gap-2 text-[12.5px] font-semibold text-[#126E2C]">
          <ShieldCheck size={16} /> Semua aman — tidak ada keberangkatan yang perlu perhatian pada {periodLabel || "periode ini"}.
        </span>
        <button className="secondary-button !py-1 !text-[12px]" onClick={onRefresh} data-testid="dc-attention-refresh">
          <RefreshCw size={13} /> Periksa lagi
        </button>
      </div>
    );
  }

  const visible = showAll ? shown : shown.slice(0, PREVIEW);
  const anyActive = riskFilter === "any";

  return (
    <div className="overflow-hidden rounded-2xl border border-[#FFD9B8] bg-white shadow-[0_2px_12px_rgba(0,0,0,0.04)]"
      data-testid="dc-attention-panel">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#F5E7D8] bg-gradient-to-r from-[#FFF6EC] to-[#FFFBF6] px-4 py-3">
        <div className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#FFE9D2] text-[#B4530A]">
            <AlertTriangle size={17} />
          </span>
          <div>
            <p className="text-[13.5px] font-bold text-[#1C1C1E]">
              Perlu Perhatian ·{" "}
              <span className="tabular-nums" data-testid="dc-attention-total">{summary.total}</span> keberangkatan
            </p>
            <p className="mt-0.5 flex items-center gap-2 text-[11.5px] text-[#8E8E93]">
              <span className="inline-flex items-center gap-1"><SeverityDot severity="high" /> {summary.high} mendesak</span>
              <span className="inline-flex items-center gap-1"><SeverityDot severity="medium" /> {summary.medium} pantau</span>
              <span className="hidden sm:inline">· {periodLabel}</span>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className={`secondary-button !py-1 !text-[12px] ${anyActive ? "!border-[#FF9500] !text-[#8C4A00]" : ""}`}
            onClick={() => onFilter(anyActive ? null : "any")} data-testid="dc-attention-only">
            {anyActive ? "Tampilkan semua jadwal" : "Saring di kalender"}
          </button>
          <button className="icon-button !h-8 !w-8" onClick={() => setOpen((o) => !o)}
            aria-label={open ? "Sembunyikan detail" : "Tampilkan detail"} data-testid="dc-attention-toggle">
            {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>
        </div>
      </div>

      {/* Chip per kelas risiko */}
      <div className="flex flex-wrap items-center gap-1.5 px-4 py-2.5" data-testid="dc-attention-chips">
        {meta.filter((m) => (summary.by_type || {})[m.type] > 0).map((m) => (
          <RiskChip key={m.type} type={m.type} count={summary.by_type[m.type]}
            active={riskFilter === m.type} testId={`dc-attention-chip-${m.type}`}
            onClick={() => { setShowAll(false); onFilter(riskFilter === m.type ? null : m.type); }} />
        ))}
        {riskFilter ? (
          <button className="ml-1 text-[11.5px] font-semibold text-[#007AFF] hover:underline"
            onClick={() => { setShowAll(false); onFilter(null); }} data-testid="dc-attention-clear">Hapus saringan</button>
        ) : null}
      </div>

      {typeFilter ? (
        <p className="-mt-1 px-4 pb-2 text-[11.5px] text-[#8E8E93]" data-testid="dc-attention-scope">
          Menampilkan <span className="font-semibold tabular-nums text-[#1C1C1E]">{shown.length}</span> dari {items.length} keberangkatan · saringan <span className="font-semibold">{activeLabel}</span>
        </p>
      ) : null}

      {/* Daftar item */}
      {open ? (
        <div className="divide-y divide-[#F4F5F7] border-t border-[#F4F5F7]" data-testid="dc-attention-list">
          {visible.map((it) => {
            const sv = severityStyleOf(it.severity);
            return (
              <div key={it.booking_id} className="flex flex-wrap items-start gap-3 px-4 py-2.5"
                data-testid={`dc-attention-item-${it.code}`} data-severity={it.severity}>
                <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: sv.ring }} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-mono text-[12.5px] font-bold text-[#1C1C1E]">{it.code}</span>
                    <span className="truncate text-[12.5px] font-semibold text-[#3a3f4a]">{it.customer_name || "-"}</span>
                    <span className="text-[11.5px] tabular-nums text-[#8E8E93]">· {whenLabel(it.start_datetime)}</span>
                    {it.vehicle_name ? <span className="text-[11.5px] text-[#8E8E93]">· {it.vehicle_name}</span> : null}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1">
                    {it.risks.map((r) => (
                      <RiskBadge key={r.type} type={r.type} testId={`dc-attention-badge-${it.code}-${r.type}`} />
                    ))}
                  </div>
                  <p className="mt-1 text-[11.5px] leading-snug text-[#6B6B73]">{it.risks[0]?.message}</p>
                </div>
                <button className="secondary-button !py-1 !text-[12px]" onClick={() => onOpen(it)}
                  data-testid={`dc-attention-open-${it.booking_id}`}>
                  Tindak lanjuti <ArrowRight size={13} />
                </button>
              </div>
            );
          })}
          {shown.length > PREVIEW ? (
            <button className="w-full px-4 py-2 text-[12px] font-semibold text-[#007AFF] hover:bg-[#FAFBFD]"
              onClick={() => setShowAll((v) => !v)} data-testid="dc-attention-more">
              {showAll ? "Tampilkan lebih sedikit" : `Lihat ${shown.length - PREVIEW} lainnya`}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
