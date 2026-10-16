// CalendarWeekTimeline.jsx — timeline mingguan (kolom hari x baris jam) + penanda risiko.
import { CalendarRange } from "lucide-react";
import {
  WEEKDAYS, HOUR_PX, dayKey, pad, timeOfIso, severityStyleOf,
} from "./calendarCore";

export default function CalendarWeekTimeline({
  week, weekDays, selectedDay, todayKey, colorOf, riskOf, onSelectDay, onOpenEvent, loading,
}) {
  if (loading) {
    return (
      <div data-testid="dc-week-loading">
        <div className="mb-1 grid gap-1" style={{ gridTemplateColumns: "48px repeat(7, 1fr)" }}>
          <div />
          {WEEKDAYS.map((w) => <div key={w} className="h-8 animate-pulse rounded-lg bg-[#F5F6F8]" />)}
        </div>
        <div className="h-[420px] animate-pulse rounded-xl bg-[#F5F6F8]" />
      </div>
    );
  }
  if (!week) return null;
  const bodyHeight = (week.maxH - week.minH) * HOUR_PX;

  return (
    <div data-testid="dc-week">
      <div className="grid" style={{ gridTemplateColumns: "48px repeat(7, 1fr)" }}>
        <div />
        {weekDays.map((d) => {
          const dk = dayKey(d);
          const isToday = dk === todayKey;
          const isSel = dk === selectedDay;
          return (
            <button key={dk} onClick={() => onSelectDay(dk)} data-testid={`dc-weekhead-${dk}`}
              className={`mx-0.5 mb-1 rounded-lg px-1 py-1.5 text-center transition ${isSel ? "bg-[#EAF2FF]" : "hover:bg-[#F5F7FB]"}`}>
              <p className="text-[10.5px] font-bold uppercase tracking-wide text-[#9A9AA0]">{WEEKDAYS[(d.getDay() + 6) % 7]}</p>
              <p className={`mx-auto mt-0.5 grid h-6 w-6 place-items-center rounded-full text-[12px] font-bold ${isToday ? "bg-[#007AFF] text-white" : "text-[#1C1C1E]"}`}>{d.getDate()}</p>
            </button>
          );
        })}
      </div>

      <div className="relative grid overflow-hidden rounded-xl border border-[#EFF0F2]"
        style={{ gridTemplateColumns: "48px repeat(7, 1fr)", height: bodyHeight }}>
        <div className="relative border-r border-[#EFF0F2]">
          {week.hours.slice(0, -1).map((h, i) => (
            <div key={h} className="absolute right-1 -translate-y-1/2 text-[10px] font-medium tabular-nums text-[#9A9AA0]" style={{ top: i * HOUR_PX }}>{pad(h)}:00</div>
          ))}
        </div>
        {week.columns.map((col) => {
          const dk = dayKey(col.day);
          const isToday = dk === todayKey;
          return (
            <div key={dk} className={`relative border-r border-[#F2F3F5] ${isToday ? "bg-[#F5F9FF]" : ""}`}
              data-testid={`dc-weekcol-${dk}`} onClick={() => onSelectDay(dk)}>
              {week.hours.slice(0, -1).map((h, i) => (
                <div key={h} className="absolute left-0 right-0 border-t border-[#F2F3F5]" style={{ top: i * HOUR_PX }} />
              ))}
              {col.segs.map((sg, si) => {
                const color = colorOf(sg.e);
                const risk = riskOf(sg.e);
                const sv = risk ? severityStyleOf(risk.severity) : null;
                const top = (sg.startH - week.minH) * HOUR_PX;
                const height = Math.max((sg.endH - sg.startH) * HOUR_PX - 2, 18);
                const widthPct = 100 / sg.laneCount;
                const leftPct = sg.lane * widthPct;
                return (
                  <button key={`${sg.e.id}-${si}`}
                    onClick={(ev) => { ev.stopPropagation(); onOpenEvent(dk, sg.e.id); }}
                    data-testid={`dc-weekevent-${sg.e.id}`}
                    data-risk={risk ? risk.risk_types.join(",") : undefined}
                    data-severity={risk ? risk.severity : undefined}
                    title={`${sg.e.code} · ${sg.e.customer_name || ""} · ${sg.e.vehicle_name || ""}${risk ? ` · ⚠ ${risk.risks.map((r) => r.label).join(", ")}` : ""}`}
                    className="absolute overflow-hidden rounded-md px-1.5 py-0.5 text-left text-white shadow-sm transition hover:brightness-105"
                    style={{
                      top, height, left: `calc(${leftPct}% + 2px)`, width: `calc(${widthPct}% - 4px)`,
                      background: color, borderLeft: "3px solid rgba(0,0,0,0.18)",
                      boxShadow: sv ? `0 0 0 2px ${sv.ring}` : undefined,
                    }}>
                    <p className="truncate text-[10px] font-bold leading-tight tabular-nums">{risk ? "⚠ " : ""}{timeOfIso(sg.e.start_datetime)}{sg.crossStart ? " ‹" : ""}</p>
                    <p className="truncate text-[10.5px] font-semibold leading-tight">{sg.e.customer_name || sg.e.code}</p>
                    {height > 40 ? <p className="truncate text-[9.5px] leading-tight opacity-90">{sg.e.vehicle_name || ""}</p> : null}
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>
      {week.count === 0 ? (
        <div className="mt-3 flex flex-col items-center gap-1.5 rounded-xl border border-dashed border-[#E5E5EA] py-6 text-center" data-testid="dc-week-empty">
          <CalendarRange size={20} className="text-[#C7C7CC]" />
          <p className="text-[12.5px] text-[#8E8E93]">Tidak ada keberangkatan pada minggu / saringan ini.</p>
        </div>
      ) : null}
      <p className="mt-2 text-center text-[11px] text-[#8E8E93]">Blok berdampingan pada kolom yang sama menandakan jadwal yang tumpang-tindih.</p>
    </div>
  );
}
