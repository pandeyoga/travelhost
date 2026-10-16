import { useCallback, useEffect, useState } from "react";
import {
  CalendarCheck, UserPlus, BellRing, Navigation, Flag, Truck, MapPin, ClipboardCheck,
  CheckCircle2, Clock, AlertCircle, ChevronLeft, ChevronRight,
} from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { useAuth } from "@/context/AuthContext";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import AssignTripDialog from "@/components/app/AssignTripDialog";
import PodDialog from "@/components/app/PodDialog";
import DispatchDetailDialog from "@/components/app/DispatchDetailDialog";
import { formatQty } from "@/utils/formatters";

const BK_STATUS = { confirmed: ["Dikonfirmasi", "info"], ongoing: ["Berjalan", "warning"], completed: ["Selesai", "success"], pending: ["Pending", "neutral"], cancelled: ["Batal", "neutral"] };
const TRIP_STATUS = { standby: ["Terjadwal", "info"], to_pickup: ["Menjemput", "warning"], on_trip: ["Dalam Perjalanan", "warning"], completed: ["Selesai", "success"] };

function Pill({ label, tone }) {
  return <span className={`status-pill tone-${tone || "neutral"}`}>{label}</span>;
}

function Stat({ icon: Icon, label, value, tone = "#007AFF", testId }) {
  return (
    <div className="rounded-[14px] border border-[#EFF0F2] bg-white p-4 shadow-sm" data-testid={testId}>
      <div className="flex items-center gap-2 text-[12px] font-semibold text-[#6B6B73]"><Icon size={14} style={{ color: tone }} /> {label}</div>
      <div className="mt-1 text-[24px] font-bold tabular-nums text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>{value}</div>
    </div>
  );
}

const utcDate = (offset = 0) => { const d = new Date(); d.setUTCDate(d.getUTCDate() + offset); return d.toISOString().slice(0, 10); };
const timeOf = (iso) => { if (!iso) return "-"; const d = new Date(iso); return Number.isNaN(d.getTime()) ? "-" : d.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }); };

export default function Dispatch() {
  const { user } = useAuth();
  const canManage = user && (user.role === "owner" || user.role === "ops_admin");
  const [date, setDate] = useState(utcDate(0));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState("");
  const [assignTarget, setAssignTarget] = useState(null);
  const [podTarget, setPodTarget] = useState(null);
  const [detailId, setDetailId] = useState(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) { setLoading(true); setError(null); }
    try {
      const r = await apiClient.get(`/dispatch/today?date=${date}`);
      setData(r.data);
    } catch (e) {
      if (!silent) setError(e?.response?.data?.detail || "Gagal memuat papan operasi");
    } finally { if (!silent) setLoading(false); }
  }, [date]);

  useEffect(() => { load(); }, [load]);

  // Sinkron dgn aksi DRIVER: papan menyegarkan diri tiap 20 dtk (senyap, tanpa flicker)
  // agar perubahan dari Ruang Kerja Driver terlihat tanpa perlu refresh manual.
  useEffect(() => {
    const t = setInterval(() => { if (!document.hidden) load(true); }, 20000);
    return () => clearInterval(t);
  }, [load]);

  const act = async (key, fn, okMsg) => {
    setBusy(key);
    try { const r = await fn(); toast.success(typeof okMsg === "function" ? okMsg(r) : okMsg); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Aksi gagal"); }
    finally { setBusy(""); }
  };

  const confirmDeparture = (row) => act(`confirm-${row.id}`, () => apiClient.post(`/dispatch/${row.id}/confirm-departure`), "Keberangkatan dikonfirmasi — WA terkirim ke pelanggan");
  const enroute = (row) => act(`enroute-${row.id}`, () => apiClient.post(`/dispatch/trips/${row.trip_id}/enroute`), "Driver ditandai dalam perjalanan — WA terkirim");
  const arrived = (row) => act(`arrived-${row.id}`, () => apiClient.post(`/dispatch/trips/${row.trip_id}/arrived`), "Tiba di tujuan — WA terkirim ke pelanggan");

  if (loading) return <LoadingState testId="dispatch-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const s = data?.summary || {};
  const rows = data?.departures || [];
  const isToday = date === utcDate(0);
  const isTomorrow = date === utcDate(1);

  return (
    <div className="space-y-4" data-testid="dispatch-page">
      {/* Pemilih tanggal */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <button className={`secondary-button ${isToday ? "!border-[#007AFF] !text-[#007AFF]" : ""}`} onClick={() => setDate(utcDate(0))} data-testid="dispatch-today-btn">Hari Ini</button>
          <button className={`secondary-button ${isTomorrow ? "!border-[#007AFF] !text-[#007AFF]" : ""}`} onClick={() => setDate(utcDate(1))} data-testid="dispatch-tomorrow-btn">Besok</button>
          <button className="icon-button !h-9 !w-9" title="Hari sebelumnya" onClick={() => { const d = new Date(date); d.setUTCDate(d.getUTCDate() - 1); setDate(d.toISOString().slice(0, 10)); }}><ChevronLeft size={16} /></button>
          <input type="date" className="h-9 w-[150px] rounded-[10px] border border-[#E2E3E7] bg-white px-3 text-[13px]" value={date} onChange={(e) => setDate(e.target.value)} data-testid="dispatch-date" />
          <button className="icon-button !h-9 !w-9" title="Hari berikutnya" onClick={() => { const d = new Date(date); d.setUTCDate(d.getUTCDate() + 1); setDate(d.toISOString().slice(0, 10)); }}><ChevronRight size={16} /></button>
        </div>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5" data-testid="dispatch-summary">
        <Stat icon={CalendarCheck} label="Berangkat" value={formatQty(s.total)} testId="disp-stat-total" />
        <Stat icon={UserPlus} label="Perlu Assign" value={formatQty(s.to_assign)} tone="#FF3B30" testId="disp-stat-assign" />
        <Stat icon={BellRing} label="Perlu Konfirmasi" value={formatQty(s.to_confirm)} tone="#FF9500" testId="disp-stat-confirm" />
        <Stat icon={Navigation} label="Sedang Jalan" value={formatQty(s.ongoing)} tone="#5856D6" testId="disp-stat-ongoing" />
        <Stat icon={CheckCircle2} label="Selesai" value={formatQty(s.completed)} tone="#34C759" testId="disp-stat-completed" />
      </div>

      {/* Daftar keberangkatan */}
      {rows.length === 0 ? (
        <EmptyState title="Tidak ada keberangkatan" description="Tidak ada trip yang berangkat pada tanggal ini." testId="dispatch-empty" />
      ) : (
        <section className="section-card">
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead><tr className="border-b border-[#EFF0F2] text-left text-[11px] uppercase tracking-wide text-[#8E8E93]">
                <th className="px-4 py-2.5">Booking</th><th className="px-3 py-2.5">Rute &amp; Jam</th>
                <th className="px-3 py-2.5">Driver / Unit</th><th className="px-3 py-2.5">Status</th>
                <th className="px-3 py-2.5 text-right">Aksi</th></tr></thead>
              <tbody data-testid="dispatch-list">
                {rows.map((r) => {
                  const bk = BK_STATUS[r.status] || [r.status, "neutral"];
                  const tr = r.trip_status ? (TRIP_STATUS[r.trip_status] || [r.trip_status, "neutral"]) : null;
                  return (
                    <tr key={r.id} className="cursor-pointer border-b border-[#F6F6F8] align-top hover:bg-[#FAFAFB]"
                      onClick={() => setDetailId(r.id)} title="Klik untuk lihat detail & timeline"
                      data-testid={`dispatch-row-${r.id}`}>
                      <td className="px-4 py-3">
                        <div className="font-bold text-[#1C1C1E]">{r.code}</div>
                        <div className="text-[11.5px] text-[#6B6B73]">{r.customer_name}</div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1 text-[#1C1C1E]"><MapPin size={12} className="text-[#007AFF]" />{r.origin || "-"} <span className="text-[#8E8E93]">→</span> {r.destination || "-"}{r.dest_geocoded ? <span title="Tujuan terpetakan" className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-[#34C759]" /> : null}</div>
                        <div className="mt-0.5 flex items-center gap-1 text-[11.5px] text-[#6B6B73]"><Clock size={11} /> {timeOf(r.start_datetime)}</div>
                      </td>
                      <td className="px-3 py-3">
                        {r.assigned ? (
                          <div>
                            <div className="flex items-center gap-1 font-medium text-[#1C1C1E]"><Truck size={12} className="text-[#6B6B73]" /> {r.vehicle_name}</div>
                            <div className="text-[11.5px] text-[#6B6B73]">{r.driver_name}{r.driver_phone ? ` · ${r.driver_phone}` : ""}</div>
                          </div>
                        ) : <span className="inline-flex items-center gap-1 rounded-full bg-[#FFE5E2] px-2 py-0.5 text-[11px] font-semibold text-[#C0271E]"><AlertCircle size={11} /> Belum di-assign</span>}
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap items-center gap-1">
                          <Pill label={bk[0]} tone={bk[1]} />
                          {tr ? <Pill label={tr[0]} tone={tr[1]} /> : null}
                          {r.departure_confirmed ? <span className="status-pill tone-success" data-testid={`dispatch-confirmed-${r.id}`}><CheckCircle2 size={11} /> Konfirmasi</span> : null}
                          {r.pod ? <span className="status-pill tone-info"><ClipboardCheck size={11} /> POD</span> : null}
                        </div>
                      </td>
                      <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                        {canManage ? (
                          <div className="flex flex-wrap justify-end gap-1.5">
                            <button className="secondary-button !h-8 !px-2.5" onClick={() => setAssignTarget(r)} data-testid={`dispatch-assign-${r.id}`}><UserPlus size={13} /> {r.assigned ? "Ubah" : "Assign"}</button>
                            {r.assigned && !r.departure_confirmed ? (
                              <button className="secondary-button !h-8 !px-2.5" disabled={busy === `confirm-${r.id}`} onClick={() => confirmDeparture(r)} data-testid={`dispatch-confirm-${r.id}`}><BellRing size={13} /> Konfirmasi</button>
                            ) : null}
                            {r.trip_id && r.trip_status === "standby" ? (
                              <button className="secondary-button !h-8 !px-2.5" disabled={busy === `enroute-${r.id}`} onClick={() => enroute(r)} data-testid={`dispatch-enroute-${r.id}`}><Navigation size={13} /> Berangkat</button>
                            ) : null}
                            {r.trip_id && (r.trip_status === "to_pickup" || r.trip_status === "on_trip") ? (
                              <button className="secondary-button !h-8 !px-2.5" disabled={busy === `arrived-${r.id}`} onClick={() => arrived(r)} data-testid={`dispatch-arrived-${r.id}`}><Flag size={13} /> Tiba</button>
                            ) : null}
                            {r.trip_id ? (
                              <button className="secondary-button !h-8 !px-2.5" onClick={() => setPodTarget(r)} data-testid={`dispatch-pod-${r.id}`}><ClipboardCheck size={13} /> POD</button>
                            ) : null}
                          </div>
                        ) : <span className="text-[11px] text-[#8E8E93]">—</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="border-t border-[#EFF0F2] px-4 py-2 text-[11.5px] text-[#8E8E93]">{formatQty(rows.length)} keberangkatan · {data?.date}</div>
        </section>
      )}

      <AssignTripDialog open={Boolean(assignTarget)} onOpenChange={(v) => !v && setAssignTarget(null)} booking={assignTarget} onSaved={load} />
      <PodDialog open={Boolean(podTarget)} onOpenChange={(v) => !v && setPodTarget(null)} trip={podTarget ? { id: podTarget.trip_id, pod: podTarget.pod ? {} : null } : null} onSaved={load} />
      <DispatchDetailDialog open={Boolean(detailId)} onOpenChange={(v) => !v && setDetailId(null)} bookingId={detailId} />
    </div>
  );
}
