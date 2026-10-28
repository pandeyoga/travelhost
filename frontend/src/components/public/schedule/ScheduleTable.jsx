// ScheduleTable.jsx — tabel keberangkatan di halaman jadwal publik (di bawah kalender).
// Read-only: klik baris hanya membuka detail. Kolom opsional mengikuti `visibility` tautan.
import { ChevronRight } from "lucide-react";
import { PaymentPill } from "@/components/shared/StatusPill";
import { bi } from "@/lib/i18n";
import { STATUS_TONE, dayKeyOfIso, statusLabel, timeOfIso } from "@/components/app/calendar/calendarCore";

export const dayTitle = (dk, lang) => {
  const [y, m, d] = String(dk).split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(lang === "en" ? "en-GB" : "id-ID",
    { weekday: "long", day: "numeric", month: "long", year: "numeric" });
};

const dateShort = (iso, lang) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "-" : d.toLocaleDateString(lang === "en" ? "en-GB" : "id-ID",
    { weekday: "short", day: "numeric", month: "short", year: "numeric" });
};

const dayMonth = (iso, lang) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString(lang === "en" ? "en-GB" : "id-ID", { day: "numeric", month: "short" });
};

export function SchedulePill({ status, lang, testId }) {
  return <span className={`status-pill tone-${STATUS_TONE[status] || "neutral"}`} data-testid={testId}>{statusLabel(status, lang)}</span>;
}

const th = "whitespace-nowrap px-3 py-2.5 text-left text-[11px] font-bold uppercase tracking-wide text-[#8E8E93]";
const td = "px-3 py-2.5 align-top text-[12.5px] text-[#1C1C1E]";

export default function ScheduleTable({ items, lang, visibility = {}, todayKey, onOpen, loading = false, emptyText }) {
  if (loading) {
    return (
      <div className="space-y-2 p-3" data-testid="schedule-table-loading">
        {[0, 1, 2, 3].map((i) => <div key={i} className="h-10 animate-pulse rounded-lg bg-[#F5F6F8]" />)}
      </div>
    );
  }
  if (!items.length) {
    return (
      <p className="px-4 py-10 text-center text-[13px] text-[#8E8E93]" data-testid="public-schedule-empty">
        {emptyText || bi("Tidak ada keberangkatan.", "No departures.", lang)}
      </p>
    );
  }
  const sorted = [...items].sort((a, b) => String(a.start_datetime).localeCompare(String(b.start_datetime)));
  return (
    <>
    {/* Layar kecil: kartu per keberangkatan (tabel 9 kolom tidak terbaca di 375px). */}
    <ul className="divide-y divide-[#F2F2F5] sm:hidden" data-testid="schedule-cards">
      {sorted.map((it) => {
        const dk = dayKeyOfIso(it.start_datetime) || "";
        return (
          <li key={it.ref}>
            <button type="button" onClick={() => onOpen(it)} data-testid={`schedule-card-${it.ref}`}
              className={`flex w-full items-start gap-3 px-4 py-3 text-left ${dk === todayKey ? "bg-[#F0F6FF]" : ""} ${dk && dk < todayKey ? "opacity-60" : ""}`}>
              <span className="grid w-14 shrink-0 place-items-center rounded-lg bg-[#EAF2FF] py-1.5 text-center text-[#0058CC]">
                <span className="text-[13px] font-bold tabular-nums">{timeOfIso(it.start_datetime)}</span>
                <span className="text-[10px] font-semibold">{dayMonth(it.start_datetime, lang)}</span>
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-1.5">
                  <span className="font-mono text-[12px] font-bold">{it.ref}</span>
                  <SchedulePill status={it.status} lang={lang} />
                  {visibility.payment ? <PaymentPill value={it.payment_status} /> : null}
                </span>
                <span className="mt-0.5 block text-[13px] font-semibold text-[#1C1C1E]">{it.origin || "-"} → {it.destination || "-"}</span>
                <span className="block text-[12px] text-[#6B6B73]">
                  {it.vehicle_name || bi("Armada belum ditetapkan", "Vehicle not assigned", lang)}{it.plate_number ? ` · ${it.plate_number}` : ""}
                  {visibility.driver ? ` · ${it.driver_name || bi("sopir -", "driver -", lang)}` : ""}
                </span>
                {visibility.customer && it.customer_name ? <span className="block text-[12px] text-[#6B6B73]">{it.customer_name}</span> : null}
              </span>
              <ChevronRight size={15} className="mt-1 shrink-0 text-[#C7C7CC]" />
            </button>
          </li>
        );
      })}
    </ul>
    <div className="hidden overflow-x-auto sm:block" data-testid="schedule-table">
      <table className="w-full min-w-[760px] border-collapse">
        <thead className="border-b border-[#EFF0F2] bg-[#FAFAFB]">
          <tr>
            <th className={th}>{bi("Berangkat", "Departure", lang)}</th>
            <th className={th}>{bi("Kembali", "Return", lang)}</th>
            <th className={th}>{bi("Kode", "Code", lang)}</th>
            <th className={th}>{bi("Rute", "Route", lang)}</th>
            <th className={th}>{bi("Armada", "Vehicle", lang)}</th>
            {visibility.driver ? <th className={th}>{bi("Sopir", "Driver", lang)}</th> : null}
            {visibility.customer ? <th className={th}>{bi("Pelanggan", "Customer", lang)}</th> : null}
            <th className={th}>Status</th>
            {visibility.payment ? <th className={th}>{bi("Pembayaran", "Payment", lang)}</th> : null}
            <th className={th} aria-label={bi("Detail", "Details", lang)} />
          </tr>
        </thead>
        <tbody className="divide-y divide-[#F2F2F5]">
          {sorted.map((it) => {
            const dk = dayKeyOfIso(it.start_datetime) || "";
            const sameDay = dayKeyOfIso(it.end_datetime) === dk;
            return (
              <tr key={it.ref} onClick={() => onOpen(it)} data-testid={`schedule-row-${it.ref}`}
                tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") onOpen(it); }}
                className={`cursor-pointer transition hover:bg-[#F5F9FF] focus:bg-[#F5F9FF] focus:outline-none ${dk === todayKey ? "bg-[#F0F6FF]" : ""} ${dk && dk < todayKey ? "opacity-60" : ""}`}>
                <td className={td}>
                  <span className="block whitespace-nowrap font-semibold">{dateShort(it.start_datetime, lang)}</span>
                  <span className="tabular-nums text-[#6B6B73]">{timeOfIso(it.start_datetime)}</span>
                  {dk === todayKey ? <span className="status-pill tone-info ml-1.5">{bi("Hari ini", "Today", lang)}</span> : null}
                </td>
                <td className={td}>
                  {sameDay ? null : <span className="block whitespace-nowrap">{dateShort(it.end_datetime, lang)}</span>}
                  <span className="tabular-nums text-[#6B6B73]">{timeOfIso(it.end_datetime)}</span>
                </td>
                <td className={`${td} whitespace-nowrap font-mono font-bold`}>{it.ref}</td>
                <td className={td}>{it.origin || "-"} → {it.destination || "-"}</td>
                <td className={td}>
                  <span className="block">{it.vehicle_name || <span className="text-[#B0B1B8]">{bi("Belum ditetapkan", "Not assigned", lang)}</span>}</span>
                  {it.plate_number ? <span className="text-[11.5px] text-[#8E8E93]">{it.plate_number}</span> : null}
                </td>
                {visibility.driver ? <td className={td}>{it.driver_name || <span className="text-[#B0B1B8]">-</span>}</td> : null}
                {visibility.customer ? <td className={td}>{it.customer_name || "-"}</td> : null}
                <td className={td}><SchedulePill status={it.status} lang={lang} /></td>
                {visibility.payment ? <td className={td}><PaymentPill value={it.payment_status} /></td> : null}
                <td className={`${td} text-right`}><ChevronRight size={15} className="inline text-[#C7C7CC]" /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
    </>
  );
}
