// DepartureCalendar.jsx — Kalender Keberangkatan (orchestrator).
//
// Tanggung jawab file ini: state, pengambilan data, saringan, toolbar, dan layout.
// Presentasi dipecah ke components/app/calendar/* agar tiap file < 500 baris
// (batas guardrail validate_compliance) dan mudah diuji terpisah.
//
// Lapisan "Perlu Perhatian" (risiko) DIHITUNG DI BACKEND: GET /api/departures/attention.
// Alasan: deteksi lama di FE memakai `vehicle_name` (bukan identitas armada) dan hanya
// mengenal 1 kelas risiko (bentrok armada) yang praktis mustahil terjadi karena INV-4
// sudah dikunci di semua jalur tulis → banner selalu 0. Sekarang 8 kelas risiko nyata.
import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Plus, LayoutGrid, Columns3, CalendarRange } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import apiClient from "@/services/apiClient";
import { toast } from "sonner";
import { ErrorState } from "@/components/shared/DataStates";
import SelectField from "@/components/shared/SelectField";
import BookingFormDialog from "@/components/app/BookingFormDialog";
import BookingEditDialog from "@/components/app/BookingEditDialog";
import BookingRescheduleDialog from "@/components/app/BookingRescheduleDialog";
import BookingApproveDialog from "@/components/app/BookingApproveDialog";
import CancelBookingDialog from "@/components/app/CancelBookingDialog";
import PaymentDialog from "@/components/app/PaymentDialog";
import AttentionPanel from "@/components/app/calendar/AttentionPanel";
import CalendarMonthGrid from "@/components/app/calendar/CalendarMonthGrid";
import CalendarWeekTimeline from "@/components/app/calendar/CalendarWeekTimeline";
import CalendarExportPanel from "@/components/app/calendar/CalendarExportPanel";
import DayListPanel from "@/components/app/calendar/DayListPanel";
import DepartureDetailPanel from "@/components/app/calendar/DepartureDetailPanel";
import {
  STATUS_TONE, TONE_DOT, STATUS_LEGEND, VEHICLE_PALETTE, MONTHS, STATUS_FILTERS,
  buildGrid, dayKey, dayKeyOfIso, packLanes, startOfDay, startOfWeek, weekLabelOf, ymOf,
} from "@/components/app/calendar/calendarCore";

function Dot({ color }) {
  return <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: color }} aria-hidden="true" />;
}

function Segmented({ value, onChange, options, testId }) {
  return (
    <div className="inline-flex rounded-lg border border-[#E5E5EA] bg-[#F2F3F5] p-0.5" data-testid={testId}>
      {options.map((o) => (
        <button key={o.v} onClick={() => onChange(o.v)} data-testid={`${testId}-${o.v}`}
          className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-[12px] font-semibold transition ${value === o.v ? "bg-white text-[#1C1C1E] shadow-sm" : "text-[#6B6B73] hover:text-[#1C1C1E]"}`}>
          {o.icon ? <o.icon size={13} /> : null}{o.l}
        </button>
      ))}
    </div>
  );
}

export default function DepartureCalendar() {
  const { user } = useAuth();
  const canManage = user && (user.role === "owner" || user.role === "ops_admin");

  const [view, setView] = useState("month");          // month | week
  const [colorMode, setColorMode] = useState("status"); // status | vehicle
  const [viewDate, setViewDate] = useState(() => new Date());

  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = () => setReloadKey((k) => k + 1);

  const [attention, setAttention] = useState(null);
  const [attentionLoading, setAttentionLoading] = useState(true);
  const [riskFilter, setRiskFilter] = useState(null); // null | "any" | <risk_type>

  const [statusFilter, setStatusFilter] = useState("all");
  const [vehicleFilter, setVehicleFilter] = useState("all");
  const [query, setQuery] = useState("");

  const [selectedDay, setSelectedDay] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [maps, setMaps] = useState({ vehicles: {}, customers: {}, drivers: [], vehicleNames: [] });

  const [createOpen, setCreateOpen] = useState(false);
  const [createStart, setCreateStart] = useState("");
  const [editBooking, setEditBooking] = useState(null);
  const [rescheduleBooking, setRescheduleBooking] = useState(null);
  const [approveBooking, setApproveBooking] = useState(null);
  const [payBooking, setPayBooking] = useState(null);
  const [cancelBooking, setCancelBooking] = useState(null);
  const [busy, setBusy] = useState(false);
  const [assignDriverId, setAssignDriverId] = useState("");

  const [exportOpen, setExportOpen] = useState(false);
  const [exportScope, setExportScope] = useState("active");
  const [exportStart, setExportStart] = useState("");
  const [exportEnd, setExportEnd] = useState("");
  const [exportGroup, setExportGroup] = useState(false);
  const [exporting, setExporting] = useState("");

  // Rentang tanggal yang terlihat (menentukan bulan mana yang perlu di-fetch).
  const range = useMemo(() => {
    if (view === "week") {
      const s = startOfWeek(viewDate);
      const e = new Date(s); e.setDate(s.getDate() + 6);
      return { start: s, end: e };
    }
    const cells = buildGrid(viewDate);
    return { start: cells[0], end: cells[41] };
  }, [view, viewDate]);

  useEffect(() => {
    let active = true;
    Promise.all([
      apiClient.get("/vehicles").catch(() => ({ data: [] })),
      apiClient.get("/customers").catch(() => ({ data: [] })),
      apiClient.get("/drivers").catch(() => ({ data: [] })),
    ]).then(([v, c, d]) => {
      if (!active) return;
      const vs = Array.isArray(v.data) ? v.data : [];
      const cs = Array.isArray(c.data) ? c.data : [];
      const ds = Array.isArray(d.data) ? d.data : [];
      const vm = {}; vs.forEach((x) => { vm[x.id] = x; });
      const cm = {}; cs.forEach((x) => { cm[x.id] = x; });
      setMaps({ vehicles: vm, customers: cm, drivers: ds, vehicleNames: vs.map((x) => x.name).filter(Boolean) });
    });
    return () => { active = false; };
  }, []);

  // Ambil semua bulan yang tersentuh rentang tampilan, gabung unik by id.
  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    const months = new Set();
    const cur = new Date(range.start.getFullYear(), range.start.getMonth(), 1);
    const last = new Date(range.end.getFullYear(), range.end.getMonth(), 1);
    while (cur <= last) { months.add(ymOf(cur)); cur.setMonth(cur.getMonth() + 1); }
    Promise.all([...months].map((m) => apiClient.get(`/bookings/calendar?month=${m}`).then((r) => r.data).catch(() => [])))
      .then((results) => {
        if (!active) return;
        const merged = {};
        results.flat().forEach((e) => { if (e && e.id) merged[e.id] = e; });
        setEvents(Object.values(merged));
      })
      .catch(() => { if (active) setError("Gagal memuat jadwal keberangkatan"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [range.start.getTime(), range.end.getTime(), reloadKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Lapisan risiko dari backend (satu sumber kebenaran).
  useEffect(() => {
    let active = true;
    setAttentionLoading(true);
    apiClient.get(`/departures/attention?start=${dayKey(range.start)}&end=${dayKey(range.end)}`)
      .then((r) => { if (active) setAttention(r.data); })
      .catch(() => { if (active) setAttention(null); })
      .finally(() => { if (active) setAttentionLoading(false); });
    return () => { active = false; };
  }, [range.start.getTime(), range.end.getTime(), reloadKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const riskMap = useMemo(() => {
    const m = {};
    (attention?.items || []).forEach((it) => { m[it.booking_id] = it; });
    return m;
  }, [attention]);
  const riskOf = useCallback((e) => (e ? riskMap[e.id] : null) || null, [riskMap]);

  const vehicleColors = useMemo(() => {
    const names = maps.vehicleNames.length ? maps.vehicleNames : [...new Set(events.map((e) => e.vehicle_name).filter(Boolean))];
    const m = {}; names.forEach((n, i) => { m[n] = VEHICLE_PALETTE[i % VEHICLE_PALETTE.length]; });
    return m;
  }, [maps.vehicleNames, events]);

  const colorOf = useCallback((e) => (colorMode === "vehicle"
    ? (vehicleColors[e.vehicle_name] || TONE_DOT.neutral)
    : (TONE_DOT[STATUS_TONE[e.status] || "neutral"])), [colorMode, vehicleColors]);

  const filtered = useMemo(() => events.filter((e) => {
    const risk = riskMap[e.id];
    if (riskFilter === "any" && !risk) return false;
    if (riskFilter && riskFilter !== "any" && !(risk && risk.risk_types.includes(riskFilter))) return false;
    if (statusFilter !== "all" && e.status !== statusFilter) return false;
    if (vehicleFilter !== "all" && e.vehicle_name !== vehicleFilter) return false;
    if (query) {
      const q = query.toLowerCase();
      if (!`${e.code || ""} ${e.customer_name || ""} ${e.vehicle_name || ""}`.toLowerCase().includes(q)) return false;
    }
    return true;
  }), [events, statusFilter, vehicleFilter, query, riskFilter, riskMap]);

  const byDay = useMemo(() => {
    const m = {};
    filtered.forEach((e) => { const k = dayKeyOfIso(e.start_datetime); if (!k) return; (m[k] = m[k] || []).push(e); });
    Object.values(m).forEach((list) => list.sort((a, b) => (a.start_datetime || "").localeCompare(b.start_datetime || "")));
    return m;
  }, [filtered]);

  const cells = useMemo(() => buildGrid(viewDate), [viewDate]);
  const weekDays = useMemo(() => Array.from({ length: 7 }, (_, i) => {
    const d = new Date(range.start); d.setDate(range.start.getDate() + i); return d;
  }), [range.start]);
  const todayKey = dayKey(new Date());
  const monthTotal = filtered.length;

  const week = useMemo(() => {
    if (view !== "week") return null;
    const wStart = startOfDay(weekDays[0]).getTime();
    const wEnd = startOfDay(weekDays[6]).getTime() + 86400000;
    const inWeek = filtered.filter((e) => {
      const s = new Date(e.start_datetime).getTime(); const en = new Date(e.end_datetime).getTime();
      if (Number.isNaN(s)) return false;
      const end = Number.isNaN(en) ? s + 3600000 : en;
      return end > wStart && s < wEnd;
    });
    let minH = 6, maxH = 20;
    inWeek.forEach((e) => {
      const s = new Date(e.start_datetime); const en = new Date(e.end_datetime);
      if (!Number.isNaN(s.getTime())) minH = Math.min(minH, s.getHours());
      if (!Number.isNaN(en.getTime())) maxH = Math.max(maxH, en.getHours() + (en.getMinutes() > 0 || (en.getHours() === s.getHours() && en.getDate() === s.getDate()) ? 1 : 0));
    });
    minH = Math.max(0, Math.min(minH, 8));
    maxH = Math.min(24, Math.max(maxH, 18));
    if (maxH <= minH) maxH = minH + 6;
    const hours = Array.from({ length: maxH - minH + 1 }, (_, i) => minH + i);
    const columns = weekDays.map((day) => {
      const ds = startOfDay(day).getTime(); const de = ds + 86400000;
      const segs = [];
      inWeek.forEach((e) => {
        const s = new Date(e.start_datetime).getTime();
        const enRaw = new Date(e.end_datetime).getTime();
        const en = Number.isNaN(enRaw) ? s + 3600000 : enRaw;
        const os = Math.max(s, ds); const oe = Math.min(en, de);
        if (oe <= os) return;
        let startH = (os - ds) / 3600000;
        let endH = (oe - ds) / 3600000;
        startH = Math.max(startH, minH); endH = Math.min(endH, maxH);
        if (endH - startH < 0.4) endH = Math.min(startH + 0.4, maxH);
        if (endH <= startH) return;
        segs.push({ e, startH, endH, crossStart: s < os, crossEnd: en > oe });
      });
      return { day, segs: packLanes(segs) };
    });
    return { minH, maxH, hours, columns, count: inWeek.length };
  }, [view, weekDays, filtered]); // eslint-disable-line react-hooks/exhaustive-deps

  const openDetail = useCallback(async (id) => {
    setSelectedId(id); setDetail(null); setDetailLoading(true);
    try {
      const res = await apiClient.get(`/bookings/${id}`);
      setDetail(res.data); setAssignDriverId(res.data?.driver_id || "");
    } catch {
      toast.error("Gagal memuat detail keberangkatan"); setSelectedId(null);
    } finally { setDetailLoading(false); }
  }, []);

  const backToDay = () => { setSelectedId(null); setDetail(null); };
  const selectDay = (dk) => { setSelectedDay(dk); backToDay(); };
  const openEvent = (dk, id) => { setSelectedDay(dk); setSelectedId(null); openDetail(id); };

  // Dari panel "Perlu Perhatian": lompat ke tanggalnya + buka detail (pindah bulan bila perlu).
  const openFromAttention = (item) => {
    const d = new Date(item.start_datetime);
    if (!Number.isNaN(d.getTime())) {
      if (d.getMonth() !== viewDate.getMonth() || d.getFullYear() !== viewDate.getFullYear()) setViewDate(d);
      setSelectedDay(dayKey(d));
    }
    setSelectedId(null);
    openDetail(item.booking_id);
  };

  const step = (delta) => {
    setViewDate((d) => {
      const x = new Date(d);
      if (view === "week") x.setDate(x.getDate() + delta * 7);
      else { x.setDate(1); x.setMonth(x.getMonth() + delta); }
      return x;
    });
    setSelectedDay(null); backToDay();
  };
  const gotoToday = () => { const now = new Date(); setViewDate(now); setSelectedDay(dayKey(now)); backToDay(); };

  const afterMutation = () => { reload(); if (selectedId) openDetail(selectedId); };

  const act = async (id, action) => {
    setBusy(true);
    try {
      await apiClient.post(`/bookings/${id}/${action}`);
      toast.success(action === "complete" ? "Keberangkatan diselesaikan" : action === "reject" ? "Permintaan ditolak" : "Aksi berhasil");
      afterMutation();
    } catch (e) { toast.error(e?.response?.data?.detail || "Aksi gagal"); }
    finally { setBusy(false); }
  };

  const openCreate = (dk) => { setCreateStart(dk ? `${dk}T08:00` : ""); setCreateOpen(true); };

  const assignDriver = async () => {
    if (!detail) return;
    setBusy(true);
    try {
      await apiClient.patch(`/bookings/${detail.id}`, { driver_id: assignDriverId });
      toast.success(assignDriverId ? "Sopir berhasil ditugaskan" : "Penugasan sopir dilepas");
      afterMutation();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menugaskan sopir"); }
    finally { setBusy(false); }
  };

  const monthLabel = `${MONTHS[viewDate.getMonth()]} ${viewDate.getFullYear()}`;
  const weekLabel = weekLabelOf(weekDays);
  const hasFilter = Boolean(query || statusFilter !== "all" || vehicleFilter !== "all" || riskFilter);
  const resetFilters = () => { setQuery(""); setStatusFilter("all"); setVehicleFilter("all"); setRiskFilter(null); };
  const exportScopeText = exportScope === "custom"
    ? (exportStart && exportEnd ? `${exportStart} s/d ${exportEnd}` : "Pilih tanggal mulai & selesai")
    : (view === "week" ? `Minggu ${weekLabel}` : `Bulan ${monthLabel}`);

  const doExport = async (fmt) => {
    if (exportScope === "custom" && (!exportStart || !exportEnd)) { toast.error("Lengkapi tanggal mulai & selesai"); return; }
    setExporting(fmt);
    try {
      const rng = exportScope === "custom" && exportStart && exportEnd
        ? { start: exportStart, end: exportEnd }
        : (view === "week" ? { start: dayKey(weekDays[0]), end: dayKey(weekDays[6]) } : { month: ymOf(viewDate) });
      const params = new URLSearchParams();
      Object.entries(rng).forEach(([k, v]) => params.set(k, v));
      if (exportGroup) params.set("group", "vehicle");
      params.set("format", fmt);
      const tag = rng.month || rng.start || "semua";
      const res = await apiClient.get(`/bookings/calendar/export?${params.toString()}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = `kalender-keberangkatan-${tag}${exportGroup ? "-per-armada" : ""}.${fmt === "pdf" ? "pdf" : "xlsx"}`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Ekspor ${fmt.toUpperCase()} diunduh`);
      setExportOpen(false);
    } catch { toast.error("Gagal mengekspor jadwal"); }
    finally { setExporting(""); }
  };

  return (
    <div className="space-y-4" data-testid="departure-calendar-page">
      {/* Baris 1: navigasi + view + ekspor + buat */}
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <button className="icon-button !h-9 !w-9" onClick={() => step(-1)} aria-label="Sebelumnya" data-testid="dc-prev"><ChevronLeft size={16} /></button>
          <div className="min-w-[168px] text-center text-[15px] font-bold text-[#1C1C1E]" data-testid="dc-month-label">{view === "week" ? weekLabel : monthLabel}</div>
          <button className="icon-button !h-9 !w-9" onClick={() => step(1)} aria-label="Berikutnya" data-testid="dc-next"><ChevronRight size={16} /></button>
          <button className="secondary-button" onClick={gotoToday} data-testid="dc-today">Hari ini</button>
          <Segmented value={view} onChange={(v) => { setView(v); backToDay(); }} testId="dc-view"
            options={[{ v: "month", l: "Bulan", icon: LayoutGrid }, { v: "week", l: "Minggu", icon: Columns3 }]} />
          <span className="ml-1 hidden text-[12px] tabular-nums text-[#8E8E93] sm:inline" data-testid="dc-month-total">{monthTotal} keberangkatan</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <CalendarExportPanel
            open={exportOpen} onToggle={() => setExportOpen((o) => !o)} onClose={() => setExportOpen(false)}
            scope={exportScope} setScope={setExportScope} scopeText={exportScopeText}
            start={exportStart} setStart={setExportStart} end={exportEnd} setEnd={setExportEnd}
            group={exportGroup} setGroup={setExportGroup} exporting={exporting} onExport={doExport} />
          {canManage ? (
            <button className="primary-button" onClick={() => openCreate(selectedDay)} data-testid="dc-create-open">
              <Plus size={14} /> Buat Keberangkatan
            </button>
          ) : null}
        </div>
      </div>

      {/* Baris 2: saringan + mode warna */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Cari kode / pelanggan…" data-testid="dc-search"
            className="h-9 w-[180px] rounded-lg border border-[#E5E5EA] bg-white px-3 text-[13px] outline-none focus:border-[#007AFF]" />
          <SelectField
            value={statusFilter} onChange={setStatusFilter} testId="dc-filter-status"
            className="w-[150px]" ariaLabel="Saring status"
            options={STATUS_FILTERS.map((s) => ({ value: s.v, label: s.l }))} />
          <SelectField
            value={vehicleFilter} onChange={setVehicleFilter} testId="dc-filter-vehicle"
            className="w-[160px]" ariaLabel="Saring armada"
            options={[{ value: "all", label: "Semua armada" }, ...maps.vehicleNames.map((n) => ({ value: n, label: n }))]} />
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-semibold text-[#9A9AA0]">Warna:</span>
          <Segmented value={colorMode} onChange={setColorMode} testId="dc-color"
            options={[{ v: "status", l: "Status" }, { v: "vehicle", l: "Armada" }]} />
        </div>
      </div>

      {/* Legend dinamis */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5" data-testid="dc-legend">
        {colorMode === "status"
          ? STATUS_LEGEND.map((l) => <span key={l.label} className="inline-flex items-center gap-1.5 text-[11.5px] text-[#6B6B73]"><Dot color={TONE_DOT[l.tone]} /> {l.label}</span>)
          : (maps.vehicleNames.length ? maps.vehicleNames : Object.keys(vehicleColors)).map((n) => (
            <span key={n} className="inline-flex items-center gap-1.5 text-[11.5px] text-[#6B6B73]"><Dot color={vehicleColors[n]} /> {n}</span>
          ))}
      </div>

      {/* Lapisan "Perlu Perhatian" */}
      <AttentionPanel
        data={attention} loading={attentionLoading} riskFilter={riskFilter} onFilter={setRiskFilter}
        onOpen={openFromAttention} onRefresh={reload}
        periodLabel={view === "week" ? `Minggu ${weekLabel}` : `Bulan ${monthLabel}`} />

      {/* Empty state global: tidak ada hasil (mis. saringan terlalu sempit) */}
      {!loading && monthTotal === 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-dashed border-[#E5E5EA] bg-[#FAFAFB] px-4 py-3"
          data-testid="dc-empty-hint">
          <span className="text-[12.5px] text-[#6B6B73]">
            Tidak ada keberangkatan pada {view === "week" ? `minggu ${weekLabel}` : `bulan ${monthLabel}`}
            {hasFilter ? " dengan saringan aktif" : ""}.
          </span>
          {hasFilter ? (
            <button className="secondary-button !py-1 !text-[12px]" onClick={resetFilters} data-testid="dc-reset-filters">
              Hapus semua saringan
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_360px]">
        <div className="section-card p-3 sm:p-4" data-testid="dc-calendar">
          {error ? <ErrorState message={error} onRetry={reload} />
            : view === "week"
              ? <CalendarWeekTimeline week={week} weekDays={weekDays} selectedDay={selectedDay} todayKey={todayKey}
                colorOf={colorOf} riskOf={riskOf} onSelectDay={selectDay} onOpenEvent={openEvent} loading={loading} />
              : <CalendarMonthGrid cells={cells} viewDate={viewDate} byDay={byDay} selectedDay={selectedDay}
                todayKey={todayKey} colorMode={colorMode} colorOf={colorOf} riskOf={riskOf}
                onSelectDay={selectDay} onOpenEvent={openEvent} loading={loading} total={monthTotal} />}
        </div>
        <div className="section-card p-4 xl:sticky xl:top-4 xl:self-start" data-testid="dc-panel">
          {selectedId ? (
            <DepartureDetailPanel
              detail={detail} loading={detailLoading} maps={maps} vehicleColors={vehicleColors}
              canManage={canManage} risk={detail ? riskMap[detail.id] : null} busy={busy}
              assignDriverId={assignDriverId} setAssignDriverId={setAssignDriverId}
              onAssign={assignDriver} onBack={backToDay}
              onOpenRelated={(id) => openDetail(id)}
              onApprove={() => setApproveBooking(detail)} onReject={() => act(detail.id, "reject")}
              onComplete={() => act(detail.id, "complete")} onEdit={() => setEditBooking(detail)}
              onReschedule={() => setRescheduleBooking(detail)} onPay={() => setPayBooking(detail)}
              onCancel={() => setCancelBooking(detail)} />
          ) : selectedDay ? (
            <DayListPanel selectedDay={selectedDay} list={byDay[selectedDay] || []} colorOf={colorOf}
              riskOf={riskOf} canManage={canManage} onOpenEvent={openEvent} onCreate={openCreate} />
          ) : (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center" data-testid="dc-prompt">
              <span className="grid h-14 w-14 place-items-center rounded-2xl bg-[#F1F2F6] text-[#8E8E93]"><CalendarRange size={26} /></span>
              <div>
                <p className="text-[14px] font-semibold text-[#1C1C1E]">Pilih keberangkatan</p>
                <p className="mt-1 max-w-[240px] text-[12.5px] text-[#8E8E93]">Klik tanggal untuk melihat daftar, atau klik langsung sebuah jadwal untuk membuka detail lengkapnya.</p>
              </div>
            </div>
          )}
        </div>
      </div>

      <BookingFormDialog open={createOpen} onOpenChange={setCreateOpen} initialStart={createStart} onCreated={() => { reload(); }} />
      <BookingEditDialog open={Boolean(editBooking)} onOpenChange={(v) => !v && setEditBooking(null)} booking={editBooking} onSaved={afterMutation} />
      <BookingRescheduleDialog open={Boolean(rescheduleBooking)} onOpenChange={(v) => !v && setRescheduleBooking(null)} booking={rescheduleBooking} onSaved={afterMutation} />
      <BookingApproveDialog open={Boolean(approveBooking)} onOpenChange={(v) => !v && setApproveBooking(null)} booking={approveBooking} onSaved={afterMutation} />
      <CancelBookingDialog open={Boolean(cancelBooking)} onOpenChange={(v) => !v && setCancelBooking(null)} booking={cancelBooking} onSaved={afterMutation} />
      <PaymentDialog open={Boolean(payBooking)} onOpenChange={(v) => !v && setPayBooking(null)} booking={payBooking} onSaved={afterMutation} />
    </div>
  );
}
