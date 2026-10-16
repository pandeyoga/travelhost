// DayListPanel.jsx — daftar keberangkatan pada tanggal terpilih (kolom kanan kalender).
import { CalendarRange, ChevronRight, Plus, Bus } from "lucide-react";
import { RiskBadge } from "./RiskIndicators";
import { STATUS_SHORT, timeOfIso, severityStyleOf } from "./calendarCore";
import { formatDate } from "@/utils/formatters";

function Dot({ color }) {
  return <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: color }} aria-hidden="true" />;
}

export default function DayListPanel({
  selectedDay, list, colorOf, riskOf, canManage, onOpenEvent, onCreate,
}) {
  const riskCount = list.filter((e) => riskOf(e)).length;
  return (
    <div className="space-y-3" data-testid="dc-daylist">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-[#9A9AA0]">Keberangkatan</p>
          <p className="text-[15px] font-bold text-[#1C1C1E]">{formatDate(selectedDay)}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="status-pill tone-info">{list.length} jadwal</span>
          {riskCount ? <span className="status-pill tone-warning" data-testid="dc-daylist-riskcount">{riskCount} perlu perhatian</span> : null}
        </div>
      </div>

      {list.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#E5E5EA] px-4 py-8 text-center" data-testid="dc-daylist-empty">
          <CalendarRange size={22} className="mx-auto text-[#C7C7CC]" />
          <p className="mt-2 text-[13px] text-[#8E8E93]">Tidak ada keberangkatan di tanggal ini.</p>
          {canManage ? (
            <button className="primary-button mt-3 !mx-auto" onClick={() => onCreate(selectedDay)} data-testid="dc-daylist-create">
              <Plus size={14} /> Buat di tanggal ini
            </button>
          ) : null}
        </div>
      ) : (
        <div className="space-y-2">
          {list.map((e) => {
            const risk = riskOf(e);
            const sv = risk ? severityStyleOf(risk.severity) : null;
            return (
              <button key={e.id} onClick={() => onOpenEvent(selectedDay, e.id)} data-testid={`dc-daylist-item-${e.id}`}
                className="flex w-full items-center gap-3 rounded-xl border bg-white p-3 text-left transition hover:border-[#007AFF] hover:shadow-[0_2px_10px_rgba(0,0,0,0.05)]"
                style={{ borderColor: sv ? sv.border : "#EFF0F2", background: sv ? sv.bg : "#fff" }}>
                <span className="grid h-10 w-14 shrink-0 place-items-center rounded-lg text-[12px] font-bold tabular-nums"
                  style={{ background: "rgba(0,122,255,0.08)", color: "#0058CC" }}>{timeOfIso(e.start_datetime)}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-[12px] font-bold text-[#1C1C1E]">{e.code}</span>
                    <Dot color={colorOf(e)} />
                    <span className="truncate text-[11px] text-[#8E8E93]">{STATUS_SHORT[e.status] || e.status}</span>
                  </div>
                  <p className="mt-0.5 truncate text-[13px] font-semibold text-[#1C1C1E]">{e.customer_name || "-"}</p>
                  <p className="truncate text-[12px] text-[#8E8E93]"><Bus size={11} className="mr-1 inline" />{e.vehicle_name || "Armada belum ditetapkan"}</p>
                  {risk ? (
                    <div className="mt-1 flex flex-wrap items-center gap-1" data-testid={`dc-daylist-risk-${e.id}`}>
                      {risk.risks.map((r) => (
                        <RiskBadge key={r.type} type={r.type} testId={`dc-daylist-badge-${e.id}-${r.type}`} />
                      ))}
                    </div>
                  ) : null}
                </div>
                <ChevronRight size={16} className="text-[#C7C7CC]" />
              </button>
            );
          })}
          {canManage ? (
            <button className="secondary-button w-full justify-center" onClick={() => onCreate(selectedDay)} data-testid="dc-daylist-create-more">
              <Plus size={14} /> Tambah keberangkatan
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}
