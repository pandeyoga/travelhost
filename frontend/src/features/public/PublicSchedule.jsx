// PublicSchedule.jsx — halaman JADWAL KEBERANGKATAN via share-link (/schedule/:token), TANPA login.
//
// Read-only by design: tidak ada tombol aksi; data & field yang tampil ditentukan backend
// (GET /api/public/schedule/:token → services/schedule_share.public_departure allowlist).
// Tampilan Kalender memakai ulang grid bulan ERP (CalendarMonthGrid) tanpa lapisan risiko.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { AlertTriangle, CalendarDays, ChevronLeft, ChevronRight, LayoutGrid, List, RefreshCw, Search } from "lucide-react";
import apiClient from "@/services/apiClient";
import { Logo } from "@/components/public/Logo";
import LanguageSwitch from "@/components/public/LanguageSwitch";
import SelectField from "@/components/shared/SelectField";
import CalendarMonthGrid from "@/components/app/calendar/CalendarMonthGrid";
import {
  MONTHS, STATUS_TONE, TONE_DOT, buildGrid, dayKey, dayKeyOfIso,
} from "@/components/app/calendar/calendarCore";
import ScheduleAgenda, { dayTitle } from "@/components/public/schedule/ScheduleAgenda";
import ScheduleDetailDialog from "@/components/public/schedule/ScheduleDetailDialog";
import { formatDateTime, formatQty } from "@/utils/formatters";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

const REFRESH_MS = 120000;
const ERROR_EN = {
  404: "This schedule link was not found.",
  403: "This schedule link has been deactivated.",
  410: "This schedule link has expired.",
  429: "Too many requests. Please try again shortly.",
};
const MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

function useNoIndex(title) {
  useEffect(() => {
    const prevTitle = document.title;
    document.title = title;
    const meta = document.createElement("meta");
    meta.name = "robots"; meta.content = "noindex, nofollow";
    document.head.appendChild(meta);
    return () => { document.title = prevTitle; meta.remove(); };
  }, [title]);
}

export default function PublicSchedule() {
  const { token } = useParams();
  const lang = useLangValue();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [company, setCompany] = useState({});
  const [view, setView] = useState("list");
  const [query, setQuery] = useState("");
  const [vehicle, setVehicle] = useState("all");
  const [selected, setSelected] = useState(null);
  const [viewDate, setViewDate] = useState(null);
  const [selectedDay, setSelectedDay] = useState(null);

  const load = useCallback(async (silent = false) => {
    if (silent) setRefreshing(true);
    try {
      const r = await apiClient.get(`/public/schedule/${token}`);
      setData(r.data); setError(null);
    } catch (e) {
      const code = e?.response?.status || 0;
      setError({ code, detail: e?.response?.data?.detail || "Tautan jadwal tidak tersedia." });
      setData(null);
    } finally { setLoading(false); setRefreshing(false); }
  }, [token]);

  useEffect(() => {
    load();
    const t = setInterval(() => load(true), REFRESH_MS);
    return () => clearInterval(t);
  }, [load]);

  useEffect(() => {
    apiClient.get("/public/company").then((r) => setCompany(r.data && typeof r.data === "object" ? r.data : {})).catch(() => {});
  }, []);

  useNoIndex(`${data?.label || bi("Jadwal Keberangkatan", "Departure Schedule", lang)}${company.name ? ` · ${company.name}` : ""}`);

  const items = useMemo(() => (Array.isArray(data?.items) ? data.items : []), [data]);
  const vehicleNames = useMemo(() => [...new Set(items.map((i) => i.vehicle_name).filter(Boolean))].sort(), [items]);
  const filtered = useMemo(() => items.filter((it) => {
    if (vehicle !== "all" && it.vehicle_name !== vehicle) return false;
    if (!query) return true;
    const q = query.toLowerCase();
    return [it.ref, it.origin, it.destination, it.vehicle_name, it.plate_number, it.customer_name, it.driver_name]
      .some((v) => String(v || "").toLowerCase().includes(q));
  }), [items, vehicle, query]);

  const todayKey = dayKey(new Date());
  const upcoming = items.filter((i) => (dayKeyOfIso(i.start_datetime) || "") >= todayKey).length;

  // Bulan awal tampilan kalender: hari ini bila masuk periode, selain itu bulan jadwal pertama.
  useEffect(() => {
    if (!data || viewDate) return;
    const first = items.find((i) => (dayKeyOfIso(i.start_datetime) || "") >= todayKey) || items[0];
    const lo = data.period?.start ? new Date(data.period.start) : null;
    const hi = data.period?.end ? new Date(data.period.end) : null;
    const now = new Date();
    const inPeriod = (!lo || now >= lo) && (!hi || now <= hi);
    setViewDate(inPeriod || !first ? now : new Date(first.start_datetime));
  }, [data, items, todayKey, viewDate]);

  const calEvents = useMemo(() => filtered.map((i) => ({ ...i, id: i.ref, code: i.ref })), [filtered]);
  const byDay = useMemo(() => {
    const m = {};
    calEvents.forEach((e) => { const k = dayKeyOfIso(e.start_datetime); if (k) (m[k] = m[k] || []).push(e); });
    return m;
  }, [calEvents]);
  const cells = useMemo(() => (viewDate ? buildGrid(viewDate) : []), [viewDate]);
  const monthLabel = viewDate ? `${(lang === "en" ? MONTHS_EN : MONTHS)[viewDate.getMonth()]} ${viewDate.getFullYear()}` : "";
  const stepMonth = (d) => { setViewDate((v) => new Date(v.getFullYear(), v.getMonth() + d, 1)); setSelectedDay(null); };
  const openRef = (ref) => setSelected(items.find((i) => i.ref === ref) || null);
  const dayItems = selectedDay ? filtered.filter((i) => dayKeyOfIso(i.start_datetime) === selectedDay) : [];

  const errorText = error ? (lang === "en" ? ERROR_EN[error.code] || "The schedule link is unavailable." : error.detail) : "";

  return (
    <div style={{ minHeight: "100vh", background: "#F2F3F7" }} data-testid="public-schedule-page">
      <header className="flex items-center justify-between gap-3 border-b border-[#E6E7EB] bg-white px-4 py-3 sm:px-5">
        <div className="flex min-w-0 items-center gap-2.5">
          <Logo showWordmark={false} name={company.name || undefined} logoUrl={company.logo_url} />
          <div className="min-w-0">
            <p className="truncate text-[14px] font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>{company.name || "RahazaTrans"}</p>
            <p className="text-[11px] text-[#8E8E93]">{bi("Jadwal Keberangkatan", "Departure Schedule", lang)}</p>
          </div>
        </div>
        <LanguageSwitch />
      </header>

      <main className="mx-auto max-w-4xl space-y-4 p-4">
        {loading ? (
          <div className="rounded-[14px] border border-[#EFF0F2] bg-white p-10 text-center text-[13px] text-[#8E8E93]" data-testid="public-schedule-loading">
            {bi("Memuat jadwal…", "Loading schedule…", lang)}
          </div>
        ) : error ? (
          <div className="flex flex-col items-center rounded-[14px] border border-[#FFD0CC] bg-[#FFF5F4] px-6 py-14 text-center" data-testid="public-schedule-error">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[#FFE0DC]"><AlertTriangle size={22} className="text-[#FF3B30]" /></div>
            <h3 className="text-base font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>{bi("Tidak dapat memuat jadwal", "Unable to load the schedule", lang)}</h3>
            <p className="mt-1 max-w-sm text-sm text-[#6B6B73]" data-testid="public-schedule-error-text">{errorText}</p>
            {error.code === 429 || error.code === 0 ? (
              <button className="secondary-button mt-4" onClick={() => { setLoading(true); load(); }} data-testid="public-schedule-retry">{bi("Coba lagi", "Try again", lang)}</button>
            ) : null}
          </div>
        ) : (
          <>
            <section className="rounded-[14px] border border-[#EFF0F2] bg-white p-4 shadow-sm" data-testid="public-schedule-info">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h1 className="text-[18px] font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }} data-testid="public-schedule-title">{data.label}</h1>
                  <p className="mt-0.5 flex items-center gap-1.5 text-[12.5px] text-[#6B6B73]" data-testid="public-schedule-period">
                    <CalendarDays size={13} /> {data.period_label}
                  </p>
                </div>
                <button className="secondary-button !h-8" onClick={() => load(true)} disabled={refreshing} data-testid="public-schedule-refresh">
                  <RefreshCw size={13} className={refreshing ? "animate-spin" : ""} /> {bi("Muat ulang", "Refresh", lang)}
                </button>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="rounded-lg bg-[#F0F6FF] p-3">
                  <p className="text-[11px] text-[#6B6B73]">{bi("Total keberangkatan", "Total departures", lang)}</p>
                  <p className="mt-0.5 text-[20px] font-bold tabular-nums text-[#0058CC]" data-testid="public-schedule-total">{formatQty(data.total)}</p>
                </div>
                <div className="rounded-lg bg-[#F1FBF3] p-3">
                  <p className="text-[11px] text-[#6B6B73]">{bi("Hari ini & mendatang", "Today & upcoming", lang)}</p>
                  <p className="mt-0.5 text-[20px] font-bold tabular-nums text-[#126E2C]">{formatQty(upcoming)}</p>
                </div>
              </div>
            </section>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                <label className="relative">
                  <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[#8E8E93]" />
                  <input value={query} onChange={(e) => setQuery(e.target.value)} data-testid="public-schedule-search"
                    placeholder={bi("Cari kode / rute / armada…", "Search code / route / vehicle…", lang)}
                    aria-label={bi("Cari jadwal", "Search schedule", lang)}
                    className="h-9 w-[230px] rounded-lg border border-[#E5E5EA] bg-white pl-8 pr-3 text-[13px] outline-none focus:border-[#007AFF]" />
                </label>
                {vehicleNames.length > 1 ? (
                  <SelectField value={vehicle} onChange={setVehicle} testId="public-schedule-vehicle" className="w-[180px]"
                    ariaLabel={bi("Saring armada", "Filter vehicle", lang)}
                    options={[{ value: "all", label: bi("Semua armada", "All vehicles", lang) }, ...vehicleNames.map((n) => ({ value: n, label: n }))]} />
                ) : null}
              </div>
              <div className="inline-flex self-start rounded-lg border border-[#E5E5EA] bg-white p-0.5" data-testid="public-schedule-view">
                {[{ v: "list", l: bi("Daftar", "List", lang), I: List }, { v: "calendar", l: bi("Kalender", "Calendar", lang), I: LayoutGrid }].map((o) => (
                  <button key={o.v} onClick={() => setView(o.v)} data-testid={`public-schedule-view-${o.v}`}
                    className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-[12px] font-semibold ${view === o.v ? "bg-[#EAF2FF] text-[#0058CC]" : "text-[#6B6B73]"}`}>
                    <o.I size={13} /> {o.l}
                  </button>
                ))}
              </div>
            </div>

            {view === "list" ? (
              <ScheduleAgenda items={filtered} lang={lang} todayKey={todayKey} onOpen={setSelected}
                emptyText={items.length ? bi("Tidak ada jadwal yang cocok dengan pencarian.", "No departures match your search.", lang)
                  : bi("Belum ada keberangkatan pada periode ini.", "There are no departures in this period yet.", lang)} />
            ) : viewDate ? (
              <section className="space-y-3 rounded-[14px] border border-[#EFF0F2] bg-white p-3 shadow-sm sm:p-4" data-testid="public-schedule-calendar">
                <div className="flex items-center justify-between">
                  <button className="icon-button !h-8 !w-8" onClick={() => stepMonth(-1)} aria-label={bi("Bulan sebelumnya", "Previous month", lang)} data-testid="public-schedule-prev"><ChevronLeft size={15} /></button>
                  <span className="text-[14px] font-bold text-[#1C1C1E]" data-testid="public-schedule-month">{monthLabel}</span>
                  <button className="icon-button !h-8 !w-8" onClick={() => stepMonth(1)} aria-label={bi("Bulan berikutnya", "Next month", lang)} data-testid="public-schedule-next"><ChevronRight size={15} /></button>
                </div>
                <div className="overflow-x-auto">
                  <div className="min-w-[560px]">
                    <CalendarMonthGrid cells={cells} viewDate={viewDate} byDay={byDay} selectedDay={selectedDay} todayKey={todayKey}
                      colorMode="status" colorOf={(e) => TONE_DOT[STATUS_TONE[e.status] || "neutral"]} riskOf={() => null}
                      onSelectDay={setSelectedDay} onOpenEvent={(dk, ref) => openRef(ref)} loading={false}
                      total={cells.reduce((n, c) => n + (byDay[dayKey(c)]?.length || 0), 0)} riskHint={false} />
                  </div>
                </div>
                {selectedDay ? (
                  <div className="border-t border-[#F0F1F3] pt-3" data-testid="public-schedule-dayview">
                    <ScheduleAgenda items={dayItems} lang={lang} todayKey={todayKey} onOpen={setSelected}
                      emptyText={`${dayTitle(selectedDay, lang)} — ${bi("tidak ada keberangkatan.", "no departures.", lang)}`} />
                  </div>
                ) : null}
              </section>
            ) : null}

            <p className="text-center text-[11px] text-[#A0A0A8]" data-testid="public-schedule-footer">
              {bi("Diperbarui", "Updated", lang)} {formatDateTime(data.generated_at)} · {data.expires_at
                ? bi(`Tautan berlaku s/d ${formatDateTime(data.expires_at)}`, `Link valid until ${formatDateTime(data.expires_at)}`, lang)
                : bi("Tautan tanpa batas waktu", "Link has no expiry", lang)}
              {data.truncated ? ` · ${bi("Hanya sebagian jadwal yang ditampilkan.", "Only part of the schedule is shown.", lang)}` : ""}
            </p>
          </>
        )}
      </main>
      <ScheduleDetailDialog item={selected} lang={lang} onOpenChange={(v) => !v && setSelected(null)} />
    </div>
  );
}
