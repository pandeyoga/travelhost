// ScheduleAgenda.jsx — daftar keberangkatan per tanggal untuk halaman jadwal publik (read-only).
import { Bus, ChevronRight, User, Users } from "lucide-react";
import { bi } from "@/lib/i18n";
import { STATUS_TONE, dayKeyOfIso, statusLabel, timeOfIso } from "@/components/app/calendar/calendarCore";

export const dayTitle = (dk, lang) => {
  const [y, m, d] = String(dk).split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(lang === "en" ? "en-GB" : "id-ID",
    { weekday: "long", day: "numeric", month: "long", year: "numeric" });
};

const shortDate = (iso, lang) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString(lang === "en" ? "en-GB" : "id-ID", { day: "numeric", month: "short" });
};

export function SchedulePill({ status, lang, testId }) {
  return <span className={`status-pill tone-${STATUS_TONE[status] || "neutral"}`} data-testid={testId}>{statusLabel(status, lang)}</span>;
}

export function groupByDay(items) {
  const m = {};
  items.forEach((it) => { const k = dayKeyOfIso(it.start_datetime); if (k) (m[k] = m[k] || []).push(it); });
  return Object.keys(m).sort().map((k) => [k, m[k]]);
}

export default function ScheduleAgenda({ items, lang, todayKey, onOpen, loading = false, emptyText }) {
  if (loading) {
    return (
      <div className="space-y-2" data-testid="schedule-agenda-loading">
        {[0, 1, 2].map((i) => <div key={i} className="h-[76px] animate-pulse rounded-xl bg-white" />)}
      </div>
    );
  }
  const groups = groupByDay(items);
  if (groups.length === 0) {
    return (
      <div className="rounded-[14px] border border-dashed border-[#E5E5EA] bg-white px-4 py-10 text-center text-[13px] text-[#8E8E93]" data-testid="public-schedule-empty">
        {emptyText || bi("Tidak ada keberangkatan.", "No departures.", lang)}
      </div>
    );
  }
  return (
    <div className="space-y-5" data-testid="schedule-agenda">
      {groups.map(([dk, list]) => (
        <section key={dk} data-testid={`schedule-day-${dk}`} className={dk < todayKey ? "opacity-70" : ""}>
          <h3 className="mb-2 flex items-center gap-2 text-[12.5px] font-bold text-[#1C1C1E]">
            {dayTitle(dk, lang)}
            {dk === todayKey ? <span className="status-pill tone-info">{bi("Hari ini", "Today", lang)}</span> : null}
            <span className="text-[11.5px] font-semibold text-[#8E8E93]">· {list.length} {bi("jadwal", list.length === 1 ? "trip" : "trips", lang)}</span>
          </h3>
          <div className="space-y-2">
            {list.map((it) => {
              const multiDay = dayKeyOfIso(it.end_datetime) && dayKeyOfIso(it.end_datetime) !== dk;
              return (
                <button key={it.ref} type="button" onClick={() => onOpen(it)} data-testid={`schedule-item-${it.ref}`}
                  className="flex w-full items-center gap-3 rounded-xl border border-[#EFF0F2] bg-white p-3 text-left shadow-sm transition hover:border-[#007AFF]">
                  <span className="grid w-16 shrink-0 place-items-center rounded-lg bg-[#EAF2FF] py-2 text-center text-[#0058CC]">
                    <span className="text-[13px] font-bold tabular-nums">{timeOfIso(it.start_datetime)}</span>
                    <span className="text-[10px] font-semibold tabular-nums opacity-80">
                      {multiDay ? `${bi("s/d", "to", lang)} ${shortDate(it.end_datetime, lang)}` : timeOfIso(it.end_datetime)}
                    </span>
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-1.5">
                      <span className="font-mono text-[12px] font-bold text-[#1C1C1E]">{it.ref}</span>
                      <SchedulePill status={it.status} lang={lang} />
                    </span>
                    <span className="mt-0.5 block truncate text-[13.5px] font-semibold text-[#1C1C1E]">
                      {it.origin || "-"} → {it.destination || "-"}
                    </span>
                    <span className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[12px] text-[#6B6B73]">
                      <span className="inline-flex items-center gap-1"><Bus size={11} />{it.vehicle_name || bi("Armada belum ditetapkan", "Vehicle not assigned yet", lang)}{it.plate_number ? ` · ${it.plate_number}` : ""}</span>
                      {"driver_name" in it ? <span className="inline-flex items-center gap-1"><User size={11} />{it.driver_name || bi("Sopir belum ditugaskan", "Driver not assigned yet", lang)}</span> : null}
                      {it.customer_name ? <span className="inline-flex items-center gap-1"><Users size={11} />{it.customer_name}</span> : null}
                    </span>
                  </span>
                  <ChevronRight size={16} className="shrink-0 text-[#C7C7CC]" />
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
