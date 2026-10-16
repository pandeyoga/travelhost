import { useEffect, useState } from "react";
import { Route, CheckCircle2, Gauge, Wallet, Wrench, ClipboardList, CalendarClock } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import { formatCurrency, formatDate, formatQty } from "@/utils/formatters";

function Stat({ icon: Icon, label, value, tone = "#007AFF" }) {
  return (
    <div className="rounded-[12px] border border-[#EFF0F2] bg-white p-3">
      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#6B6B73]"><Icon size={13} style={{ color: tone }} /> {label}</div>
      <div className="mt-0.5 text-[18px] font-bold tabular-nums text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>{value}</div>
    </div>
  );
}

const TONE = { completed: "success", on_trip: "info", to_pickup: "warning", standby: "neutral" };
const TYPE_LABEL = { servis: "Servis", kir: "KIR", pajak: "Pajak", perbaikan: "Perbaikan", lainnya: "Lainnya" };
const TYPE_TONE = { servis: "info", kir: "warning", pajak: "warning", perbaikan: "danger", lainnya: "neutral" };
const MT_STATUS_LABEL = { scheduled: "Terjadwal", in_progress: "Berlangsung", done: "Selesai", cancelled: "Dibatalkan" };
const MT_STATUS_TONE = { scheduled: "info", in_progress: "warning", done: "success", cancelled: "neutral" };

const prettyType = (t) => TYPE_LABEL[t] || String(t || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export default function VehicleDetailDrawer({ open, vehicle, onOpenChange }) {
  const [tab, setTab] = useState("trips");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [svc, setSvc] = useState(null);
  const [svcLoading, setSvcLoading] = useState(false);

  // Reset to trips tab whenever a new vehicle opens
  useEffect(() => {
    if (open) setTab("trips");
  }, [open, vehicle?.id]);

  // Trip history (E9)
  useEffect(() => {
    if (!open || !vehicle?.id) return;
    setLoading(true); setData(null);
    apiClient.get(`/vehicles/${vehicle.id}/trips`)
      .then((r) => setData(r.data))
      .catch(() => setData({ totals: {}, trips: [] }))
      .finally(() => setLoading(false));
  }, [open, vehicle]);

  // Service history (E10) — lazy load on first open of Service tab
  useEffect(() => {
    if (!open || !vehicle?.id || tab !== "service" || svc !== null) return;
    setSvcLoading(true);
    apiClient.get(`/vehicles/${vehicle.id}/maintenance`)
      .then((r) => setSvc(r.data))
      .catch(() => setSvc({ totals: {}, records: [] }))
      .finally(() => setSvcLoading(false));
  }, [open, vehicle, tab, svc]);

  // Clear service cache when vehicle changes
  useEffect(() => { setSvc(null); }, [vehicle?.id]);

  const t = data?.totals || {};
  const trips = data?.trips || [];
  const st = svc?.totals || {};
  const records = svc?.records || [];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl" data-testid="vehicle-detail-drawer">
        <SheetHeader>
          <SheetTitle>{vehicle?.name || "Armada"} <span className="text-[#8E8E93]">{vehicle?.code}</span></SheetTitle>
          <SheetDescription className="flex flex-wrap items-center gap-3 text-[12.5px]">
            {vehicle?.plate_number ? <span className="tabular-nums">{vehicle.plate_number}</span> : null}
            {vehicle?.odometer != null ? <span className="tabular-nums">Odometer: {formatQty(vehicle.odometer)} km</span> : null}
          </SheetDescription>
        </SheetHeader>

        <div className="tab-bar mt-4" data-testid="vd-tabs">
          <button className={`tab-button ${tab === "trips" ? "active" : ""}`} onClick={() => setTab("trips")} data-testid="vd-tab-trips">
            <Route size={14} /> Riwayat Trip
          </button>
          <button className={`tab-button ${tab === "service" ? "active" : ""}`} onClick={() => setTab("service")} data-testid="vd-tab-service">
            <Wrench size={14} /> Riwayat Service
          </button>
        </div>

        {/* ---- TAB: Riwayat Trip ---- */}
        {tab === "trips" ? (
          loading ? (
            <div className="py-10 text-center text-[13px] text-[#8E8E93]" data-testid="vd-loading">Memuat riwayat trip…</div>
          ) : (
            <div className="mt-4 space-y-4">
              <div className="grid grid-cols-2 gap-2.5" data-testid="vd-totals">
                <Stat icon={Route} label="Total Trip" value={formatQty(t.trips || 0)} />
                <Stat icon={CheckCircle2} label="Selesai" value={formatQty(t.completed || 0)} tone="#34C759" />
                <Stat icon={Gauge} label="Total KM" value={`${formatQty(t.distance_km || 0)} km`} tone="#FF9500" />
                <Stat icon={Wallet} label="Total Revenue" value={formatCurrency(t.revenue || 0)} tone="#5856D6" />
              </div>

              <div>
                <h3 className="mb-2 text-[12px] font-bold uppercase tracking-wide text-[#6B6B73]">Riwayat Trip</h3>
                {trips.length === 0 ? (
                  <div className="rounded-[12px] border border-dashed border-[#E2E3E6] bg-[#FAFAFB] p-6 text-center text-[13px] text-[#8E8E93]" data-testid="vd-empty">Belum ada trip.</div>
                ) : (
                  <div className="overflow-hidden rounded-[12px] border border-[#EFF0F2]" data-testid="vd-trips">
                    <table className="w-full text-[12px]">
                      <thead className="bg-[#FAFAFB] text-[10px] uppercase tracking-wide text-[#6B6B73]">
                        <tr><th className="px-3 py-2 text-left">Trip</th><th className="px-3 py-2 text-left">Driver</th><th className="px-3 py-2 text-right">KM</th><th className="px-3 py-2 text-right">Revenue</th><th className="px-3 py-2 text-left">Tanggal</th></tr>
                      </thead>
                      <tbody>
                        {trips.map((tr) => (
                          <tr key={tr.id} className="border-t border-[#F2F2F5]">
                            <td className="px-3 py-2"><div className="font-semibold text-[#1C1C1E]">{tr.code || "-"}</div><span className={`status-pill tone-${TONE[tr.status] || "neutral"}`}>{tr.status}</span></td>
                            <td className="px-3 py-2 text-[#3A3A3C]">{tr.driver_name || "-"}</td>
                            <td className="px-3 py-2 text-right tabular-nums">{formatQty(tr.distance_km || 0)}</td>
                            <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(tr.revenue || 0)}</td>
                            <td className="px-3 py-2 tabular-nums text-[#6B6B73]">{formatDate(tr.end_at || tr.start_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )
        ) : null}

        {/* ---- TAB: Riwayat Service ---- */}
        {tab === "service" ? (
          svcLoading ? (
            <div className="py-10 text-center text-[13px] text-[#8E8E93]" data-testid="vd-svc-loading">Memuat riwayat service…</div>
          ) : (
            <div className="mt-4 space-y-4">
              <div className="grid grid-cols-2 gap-2.5" data-testid="vd-svc-totals">
                <Stat icon={ClipboardList} label="Total Catatan" value={formatQty(st.count || 0)} />
                <Stat icon={CheckCircle2} label="Selesai" value={formatQty(st.done || 0)} tone="#34C759" />
                <Stat icon={Wallet} label="Total Biaya" value={formatCurrency(st.total_cost || 0)} tone="#5856D6" />
                <Stat icon={CalendarClock} label="Servis Berikutnya" value={st.next_service_date ? formatDate(st.next_service_date) : "—"} tone="#FF9500" />
              </div>

              {st.last_service_date ? (
                <div className="rounded-[12px] border border-[#EFF0F2] bg-[#FAFAFB] px-3 py-2 text-[12px] text-[#6B6B73]" data-testid="vd-svc-last">
                  Servis terakhir tercatat: <span className="font-semibold text-[#1C1C1E] tabular-nums">{formatDate(st.last_service_date)}</span>
                </div>
              ) : null}

              <div>
                <h3 className="mb-2 text-[12px] font-bold uppercase tracking-wide text-[#6B6B73]">Riwayat Service</h3>
                {records.length === 0 ? (
                  <div className="rounded-[12px] border border-dashed border-[#E2E3E6] bg-[#FAFAFB] p-6 text-center text-[13px] text-[#8E8E93]" data-testid="vd-svc-empty">Belum ada catatan perawatan untuk armada ini.</div>
                ) : (
                  <div className="overflow-hidden rounded-[12px] border border-[#EFF0F2]" data-testid="vd-svc-records">
                    <table className="w-full text-[12px]">
                      <thead className="bg-[#FAFAFB] text-[10px] uppercase tracking-wide text-[#6B6B73]">
                        <tr>
                          <th className="px-3 py-2 text-left">Jenis</th>
                          <th className="px-3 py-2 text-left">Pekerjaan</th>
                          <th className="px-3 py-2 text-left">Tanggal</th>
                          <th className="px-3 py-2 text-right">Biaya</th>
                          <th className="px-3 py-2 text-left">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {records.map((m) => (
                          <tr key={m.id} className="border-t border-[#F2F2F5]" data-testid={`vd-svc-row-${m.id}`}>
                            <td className="px-3 py-2"><span className={`status-pill tone-${TYPE_TONE[m.type] || "neutral"}`}>{prettyType(m.type)}</span></td>
                            <td className="px-3 py-2">
                              <div className="font-semibold text-[#1C1C1E]">{m.title}</div>
                              {m.workshop ? <span className="block text-[11px] text-[#8E8E93]">{m.workshop}</span> : null}
                            </td>
                            <td className="px-3 py-2 tabular-nums text-[#6B6B73]">
                              {m.start_date && m.end_date ? `${formatDate(m.start_date)} → ${formatDate(m.end_date)}` : formatDate(m.scheduled_date)}
                            </td>
                            <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(m.cost || 0)}</td>
                            <td className="px-3 py-2"><span className={`status-pill tone-${MT_STATUS_TONE[m.status] || "neutral"}`}>{MT_STATUS_LABEL[m.status] || m.status}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
