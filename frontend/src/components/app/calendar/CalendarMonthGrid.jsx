// CalendarMonthGrid.jsx — grid bulan (6x7) dengan chip keberangkatan + penanda risiko.
import { CalendarRange } from "lucide-react";
import { RiskIcon } from "./RiskIndicators";
import {
  WEEKDAYS, dayKey, timeOfIso, severityStyleOf, CONFLICT_TYPES,
} from "./calendarCore";

function Dot({ color }) {
  return <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: color }} aria-hidden="true" />;
}

export default function CalendarMonthGrid({
  cells, viewDate, byDay, selectedDay, todayKey, colorMode, colorOf, riskOf,
  onSelectDay, onOpenEvent, loading, total,
}) {
  if (loading) {
    return (
      <div data-testid="dc-month-loading">
        <div className="mb-1.5 grid grid-cols-7 gap-1.5">
          {WEEKDAYS.map((w) => <div key={w} className="pb-1 text-center text-[11px] font-bold uppercase tracking-wide text-[#9A9AA0]">{w}</div>)}
        </div>
        <div className="grid grid-cols-7 gap-1.5">
          {Array.from({ length: 42 }, (_, i) => (
            <div key={i} className="min-h-[104px] animate-pulse rounded-xl bg-[#F5F6F8]" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="dc-month">
      <div className="mb-1.5 grid grid-cols-7 gap-1.5">
        {WEEKDAYS.map((w) => (
          <div key={w} className="pb-1 text-center text-[11px] font-bold uppercase tracking-wide text-[#9A9AA0]">{w}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1.5">
        {cells.map((cell) => {
          const dk = dayKey(cell);
          const inMonth = cell.getMonth() === viewDate.getMonth();
          const isToday = dk === todayKey;
          const isSel = dk === selectedDay;
          const list = byDay[dk] || [];
          const dayRisk = list.some((e) => riskOf(e));
          return (
            <button key={dk} type="button" onClick={() => onSelectDay(dk)} data-testid={`dc-cell-${dk}`}
              className={`flex min-h-[104px] flex-col rounded-xl border p-1.5 text-left transition ${isSel ? "border-[#007AFF] ring-1 ring-[#007AFF]" : "border-[#EFF0F2] hover:border-[#C7D6F5]"} ${inMonth ? "bg-white" : "bg-[#FAFAFB]"}`}>
              <div className="mb-1 flex items-center justify-between">
                <span className={`grid h-6 min-w-6 place-items-center rounded-full px-1 text-[12px] font-semibold ${isToday ? "bg-[#007AFF] text-white" : inMonth ? "text-[#1C1C1E]" : "text-[#C7C7CC]"}`}>{cell.getDate()}</span>
                <span className="flex items-center gap-1">
                  {dayRisk ? <span className="h-1.5 w-1.5 rounded-full bg-[#FF9500]" title="Ada jadwal yang perlu perhatian" /> : null}
                  {list.length ? <span className="rounded-full bg-[#F1F2F6] px-1.5 text-[10px] font-bold tabular-nums text-[#6B6B73]">{list.length}</span> : null}
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-1 overflow-hidden">
                {list.slice(0, 3).map((e) => {
                  const risk = riskOf(e);
                  const sv = risk ? severityStyleOf(risk.severity) : null;
                  const isConflict = Boolean(risk && risk.risk_types.some((t) => CONFLICT_TYPES.includes(t)));
                  return (
                    <span key={e.id} role="button" tabIndex={0}
                      onClick={(ev) => { ev.stopPropagation(); onOpenEvent(dk, e.id); }}
                      onKeyDown={(ev) => { if (ev.key === "Enter") { ev.stopPropagation(); onOpenEvent(dk, e.id); } }}
                      data-testid={`dc-event-${e.id}`}
                      data-risk={risk ? risk.risk_types.join(",") : undefined}
                      data-severity={risk ? risk.severity : undefined}
                      data-conflict={isConflict ? "1" : undefined}
                      title={`${e.code} · ${e.customer_name || ""} · ${e.vehicle_name || ""}${risk ? ` · ⚠ ${risk.risks.map((r) => r.label).join(", ")}` : ""}`}
                      className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10.5px] font-medium text-[#1C1C1E] transition hover:brightness-95"
                      style={{
                        background: sv ? sv.bg : "rgba(60,60,67,0.05)",
                        borderLeft: `3px solid ${colorOf(e)}`,
                        boxShadow: sv ? `inset 0 0 0 1.5px ${sv.ring}` : undefined,
                      }}>
                      {risk ? <RiskIcon type={risk.risk_types[0]} size={9} color={sv.fg} /> : null}
                      <span className="tabular-nums text-[#6B6B73]">{timeOfIso(e.start_datetime)}</span>
                      <span className="truncate">{colorMode === "vehicle" ? (e.vehicle_name || e.customer_name) : (e.customer_name || e.code)}</span>
                    </span>
                  );
                })}
                {list.length > 3 ? <span className="px-1 text-[10px] font-semibold text-[#007AFF]">+{list.length - 3} lagi</span> : null}
              </div>
            </button>
          );
        })}
      </div>
      {total === 0 ? (
        <div className="mt-3 flex flex-col items-center gap-1.5 rounded-xl border border-dashed border-[#E5E5EA] py-6 text-center" data-testid="dc-month-empty">
          <CalendarRange size={20} className="text-[#C7C7CC]" />
          <p className="text-[12.5px] text-[#8E8E93]">Tidak ada keberangkatan pada periode / saringan ini.</p>
        </div>
      ) : null}
      <p className="mt-2 flex items-center justify-center gap-1.5 text-[11px] text-[#8E8E93]">
        <Dot color="#FF9500" /> Titik jingga pada tanggal = ada jadwal yang perlu perhatian.
      </p>
    </div>
  );
}
