import { useCallback, useEffect, useRef, useState } from "react";
import {
  MapPin, RefreshCw, Navigation, Clock, Gauge, Route, History, Share2, Radio,
  Cpu, Smartphone, Zap, AlertTriangle, Trash2, Save, X, Wifi, WifiOff, Power,
} from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { useAuth } from "@/context/AuthContext";
import LiveMap from "@/components/app/LiveMap";
import ShareLinkPanel from "@/components/app/ShareLinkPanel";
import DriverCheckin from "@/features/app/DriverCheckin";
import { StatusPill } from "@/components/shared/StatusPill";
import { LoadingState, ErrorState } from "@/components/shared/DataStates";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { formatDateTime, formatQty } from "@/utils/formatters";

const TRIP_TONE = { standby: "neutral", to_pickup: "warning", on_trip: "info", completed: "success" };
const TRIP_LABEL = { standby: "Standby", to_pickup: "Menuju Penjemputan", on_trip: "Dalam Perjalanan", completed: "Selesai" };
const LIVE_DOT = { moving: "#34C759", idle: "#FF9500", offline: "#8E8E93" };
const LIVE_LABEL = { moving: "Bergerak", idle: "Diam", offline: "Offline" };

// E15: sumber posisi (device fisik vs HP driver)
const SOURCE_META = {
  device: { label: "Device", icon: Radio, color: "#5856D6" },
  phone: { label: "HP", icon: Smartphone, color: "#34C759" },
};

const MODES = [
  { v: "live", l: "Live", icon: Radio },
  { v: "history", l: "Riwayat", icon: History },
  { v: "devices", l: "Perangkat", icon: Cpu },
  { v: "share", l: "Bagikan", icon: Share2 },
];

function StatCard({ icon: Icon, label, value, tone = "#007AFF", testId }) {
  return (
    <div className="flex items-center gap-3 rounded-[14px] border border-[#EFF0F2] bg-white p-3.5 shadow-sm" data-testid={testId}>
      <div className="flex h-9 w-9 items-center justify-center rounded-[10px]" style={{ background: `${tone}1A` }}>
        <Icon size={16} style={{ color: tone }} />
      </div>
      <div className="min-w-0">
        <p className="truncate text-[11px] font-medium text-[#8E8E93]">{label}</p>
        <p className="text-[17px] font-bold tabular-nums text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>{value}</p>
      </div>
    </div>
  );
}

function StaleDot({ status }) {
  const color = LIVE_DOT[status] || "#8E8E93";
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-semibold" style={{ color }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, display: "inline-block" }} />
      {LIVE_LABEL[status] || status}
    </span>
  );
}

function SourceBadge({ source }) {
  const m = SOURCE_META[source] || SOURCE_META.phone;
  const Icon = m.icon;
  return (
    <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold"
      style={{ background: `${m.color}1A`, color: m.color }} data-testid={`gps-source-${source}`}>
      <Icon size={10} /> {m.label}
    </span>
  );
}

function LiveView({ live, trips, error }) {
  const [tripId, setTripId] = useState("");
  const [track, setTrack] = useState([]);
  const [eta, setEta] = useState(null);

  useEffect(() => {
    if (!tripId && trips.length) {
      const active = trips.find((t) => t.status === "on_trip") || trips[0];
      if (active) setTripId(active.id);
    }
  }, [trips, tripId]);

  useEffect(() => {
    if (!tripId) { setTrack([]); setEta(null); return; }
    let active = true;
    apiClient.get(`/trips/${tripId}/track`).then((r) => { if (active) setTrack(Array.isArray(r.data) ? r.data : []); }).catch(() => {});
    apiClient.get(`/trips/${tripId}/eta`).then((r) => { if (active) setEta(r.data); }).catch(() => { if (active) setEta(null); });
    return () => { active = false; };
  }, [tripId, live]);

  const selectedTrip = trips.find((t) => t.id === tripId);
  const destination = selectedTrip && selectedTrip.dest_lat != null
    ? { lat: selectedTrip.dest_lat, lng: selectedTrip.dest_lng, name: selectedTrip.dest_name }
    : null;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3" data-testid="gps-live-view">
      <div className="lg:col-span-2" style={{ height: 480 }}>
        <LiveMap live={live} track={track} destination={destination} testId="gps-live-map" />
      </div>
      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Pilih Trip (jejak &amp; ETA)</label>
          <Select value={tripId} onValueChange={setTripId}>
            <SelectTrigger data-testid="gps-trip-select"><SelectValue placeholder="Pilih trip" /></SelectTrigger>
            <SelectContent>
              {trips.map((t) => (
                <SelectItem key={t.id} value={t.id}>{(t.dest_name || "Trip")} — {TRIP_LABEL[t.status] || t.status}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="rounded-[14px] border border-[#EFF0F2] bg-white p-4 shadow-sm" data-testid="gps-eta-panel">
          <div className="mb-2 flex items-center gap-2 text-[12px] font-semibold text-[#6B6B73]">
            <Route size={14} className="text-[#007AFF]" /> Estimasi ke Tujuan
          </div>
          {selectedTrip ? (
            <div className="flex items-center gap-1 text-[13px]">
              <StatusPill value={selectedTrip.status} tone={TRIP_TONE[selectedTrip.status] || "neutral"} />
              <span className="ml-1 text-[#1C1C1E]">{selectedTrip.dest_name || "-"}</span>
            </div>
          ) : null}
          {eta && eta.available ? (
            <div className="mt-3 grid grid-cols-2 gap-2">
              <div className="rounded-lg bg-[#F0F6FF] p-3">
                <div className="flex items-center gap-1 text-[11px] text-[#6B6B73]"><Clock size={12} /> ETA</div>
                <div className="mt-1 text-[18px] font-bold tabular-nums text-[#0058CC]" style={{ fontFamily: "Outfit, sans-serif" }}>{formatQty(Math.round(eta.eta_minutes))} mnt</div>
              </div>
              <div className="rounded-lg bg-[#F1FBF3] p-3">
                <div className="flex items-center gap-1 text-[11px] text-[#6B6B73]"><Gauge size={12} /> Jarak</div>
                <div className="mt-1 text-[18px] font-bold tabular-nums text-[#126E2C]" style={{ fontFamily: "Outfit, sans-serif" }}>{formatQty(eta.distance_km)} km</div>
              </div>
              {eta.approx ? <p className="col-span-2 text-[11px] text-[#FF9500]">*estimasi (provider rute tak tersedia)</p> : null}
            </div>
          ) : (
            <p className="mt-2 text-[12px] text-[#8E8E93]">{(eta && eta.reason) || "Pilih trip yang memiliki lokasi & tujuan."}</p>
          )}
        </div>

        <div className="rounded-[14px] border border-[#EFF0F2] bg-white shadow-sm">
          <div className="flex items-center gap-2 border-b border-[#F2F2F5] px-4 py-3 text-[12px] font-semibold text-[#6B6B73]">
            <Navigation size={14} className="text-[#34C759]" /> Armada Aktif ({formatQty(live.length)})
          </div>
          {error ? (
            <p className="px-4 py-6 text-center text-[12px] text-[#FF3B30]">{error}</p>
          ) : live.length === 0 ? (
            <p className="px-4 py-6 text-center text-[12px] text-[#8E8E93]" data-testid="gps-live-empty">Belum ada armada mengirim lokasi.</p>
          ) : (
            <ul className="divide-y divide-[#F2F2F5]" data-testid="gps-vehicle-list">
              {live.map((v) => (
                <li key={v.vehicle_id} className="flex items-center justify-between px-4 py-3" data-testid={`gps-vehicle-${v.vehicle_id}`}>
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-semibold text-[#1C1C1E]">{v.vehicle_name || v.vehicle_id}</p>
                    <div className="mt-0.5 flex flex-wrap items-center gap-2">
                      <StaleDot status={v.live_status} />
                      <SourceBadge source={v.source} />
                      {v.power_v != null ? (
                        <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-[#6B6B73]"><Zap size={10} /> {v.power_v}V</span>
                      ) : null}
                      {v.alarm ? (
                        <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-[#FF3B30]"><AlertTriangle size={10} /> {v.alarm}</span>
                      ) : null}
                    </div>
                  </div>
                  <div className="text-right text-[11px] tabular-nums text-[#6B6B73]">
                    <div>{formatQty(Math.round(v.speed || 0))} km/j</div>
                    <div>{v.stale ? "—" : formatDateTime(v.timestamp)}</div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function HistoryView() {
  const [vehicles, setVehicles] = useState([]);
  const [vehicleId, setVehicleId] = useState("");
  const [track, setTrack] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiClient.get("/vehicles").then((r) => setVehicles(Array.isArray(r.data) ? r.data : [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (!vehicleId) { setTrack([]); return; }
    let active = true;
    setLoading(true);
    apiClient.get(`/locations/history?vehicle_id=${vehicleId}`)
      .then((r) => { if (active) setTrack(Array.isArray(r.data) ? r.data : []); })
      .catch(() => { if (active) setTrack([]); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [vehicleId]);

  const selected = vehicles.find((v) => v.id === vehicleId);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3" data-testid="gps-history-view">
      <div className="space-y-3 lg:order-2">
        <div>
          <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Pilih Armada</label>
          <Select value={vehicleId} onValueChange={setVehicleId}>
            <SelectTrigger data-testid="gps-history-vehicle"><SelectValue placeholder="Pilih armada" /></SelectTrigger>
            <SelectContent>
              {vehicles.map((v) => <SelectItem key={v.id} value={v.id}>{v.code} · {v.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="rounded-[14px] border border-[#EFF0F2] bg-white p-4 text-[12px] text-[#6B6B73] shadow-sm">
          <div className="mb-1 flex items-center gap-2 font-semibold text-[#1C1C1E]"><History size={14} className="text-[#007AFF]" /> Riwayat Jejak (lintas-trip)</div>
          {!vehicleId ? (
            <p className="mt-2">Pilih armada untuk melihat jejak perjalanan terekam.</p>
          ) : loading ? (
            <p className="mt-2">Memuat jejak…</p>
          ) : (
            <p className="mt-2 tabular-nums">{selected ? `${selected.name}: ` : ""}{formatQty(track.length)} titik lokasi terekam.</p>
          )}
        </div>
      </div>
      <div className="lg:col-span-2 lg:order-1" style={{ height: 480 }}>
        {track.length === 0 ? (
          <div className="flex h-full items-center justify-center rounded-[14px] border border-dashed border-[#D9DAE0] bg-[#FAFAFB] text-[13px] text-[#8E8E93]" data-testid="gps-history-empty">
            {vehicleId ? "Belum ada jejak lokasi untuk armada ini." : "Pilih armada untuk menampilkan riwayat track."}
          </div>
        ) : (
          <LiveMap live={[]} track={track} destination={null} testId="gps-history-map" />
        )}
      </div>
    </div>
  );
}

// E15: manajemen perangkat GPS fisik (Traccar) — pasang IMEI ke armada, status device.
function DevicesView() {
  const [devices, setDevices] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(null);
  const [imeiInput, setImeiInput] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [d, s] = await Promise.all([
        apiClient.get("/gps/devices"),
        apiClient.get("/gps/summary"),
      ]);
      setDevices(Array.isArray(d.data) ? d.data : []);
      setSummary(s.data || {});
      setError(null);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat perangkat GPS");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const startEdit = (row) => { setEditing(row.vehicle_id); setImeiInput(row.imei || ""); };
  const cancelEdit = () => { setEditing(null); setImeiInput(""); };

  const save = async (vid) => {
    const imei = (imeiInput || "").trim();
    if (imei.length < 3) { toast.error("IMEI tidak valid"); return; }
    setBusy(true);
    try {
      await apiClient.post(`/gps/devices/${vid}/assign`, { imei, enabled: true });
      toast.success("Perangkat GPS terpasang");
      cancelEdit();
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memasang perangkat");
    } finally { setBusy(false); }
  };

  const remove = async (vid) => {
    if (!window.confirm("Lepas perangkat GPS dari armada ini?")) return;
    setBusy(true);
    try {
      await apiClient.delete(`/gps/devices/${vid}`);
      toast.success("Perangkat GPS dilepas");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal melepas perangkat");
    } finally { setBusy(false); }
  };

  if (loading) return <LoadingState testId="gps-devices-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-4" data-testid="gps-devices-view">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard icon={Cpu} label="Device Terpasang" value={formatQty(summary.with_device || 0)} tone="#5856D6" testId="gps-stat-with-device" />
        <StatCard icon={Wifi} label="Online" value={formatQty(summary.online || 0)} tone="#34C759" testId="gps-stat-online" />
        <StatCard icon={WifiOff} label="Offline" value={formatQty(summary.offline || 0)} tone="#8E8E93" testId="gps-stat-offline" />
        <StatCard icon={AlertTriangle} label="Alarm Aktif" value={formatQty(summary.alarms || 0)} tone="#FF3B30" testId="gps-stat-alarms" />
      </div>

      <div className="rounded-[14px] border border-[#EFF0F2] bg-white shadow-sm">
        <div className="flex items-center gap-2 border-b border-[#F2F2F5] px-4 py-3 text-[12px] font-semibold text-[#6B6B73]">
          <Cpu size={14} className="text-[#5856D6]" /> Perangkat GPS Fisik (Traccar) — backup pelacakan
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12.5px]">
            <thead>
              <tr className="border-b border-[#F2F2F5] text-[11px] uppercase tracking-wide text-[#8E8E93]">
                <th className="px-4 py-2.5 font-semibold">Armada</th>
                <th className="px-4 py-2.5 font-semibold">IMEI Device</th>
                <th className="px-4 py-2.5 font-semibold">Status</th>
                <th className="px-4 py-2.5 font-semibold">Voltase</th>
                <th className="px-4 py-2.5 font-semibold">Mesin</th>
                <th className="px-4 py-2.5 font-semibold">Alarm</th>
                <th className="px-4 py-2.5 text-right font-semibold">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F5F5F7]">
              {devices.map((row) => {
                const isEditing = editing === row.vehicle_id;
                return (
                  <tr key={row.vehicle_id} data-testid={`gps-device-row-${row.vehicle_id}`}>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-[#1C1C1E]">{row.name}</p>
                      <p className="text-[11px] text-[#8E8E93]">{row.code} · {row.plate_number}</p>
                    </td>
                    <td className="px-4 py-3">
                      {isEditing ? (
                        <input
                          autoFocus value={imeiInput} onChange={(e) => setImeiInput(e.target.value)}
                          placeholder="mis. 353123456789012"
                          className="w-44 rounded-lg border border-[#D9DAE0] px-2.5 py-1.5 text-[12.5px] outline-none focus:border-[#007AFF]"
                          data-testid={`gps-device-imei-input-${row.vehicle_id}`}
                        />
                      ) : row.imei ? (
                        <span className="font-mono tabular-nums text-[#1C1C1E]">{row.imei}</span>
                      ) : (
                        <span className="text-[#C7C7CC]">Belum terpasang</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {!row.has_device ? (
                        <span className="text-[11px] text-[#8E8E93]">—</span>
                      ) : row.online ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#34C759]"><Wifi size={11} /> Online</span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#8E8E93]"><WifiOff size={11} /> Offline{row.last_seen ? ` · ${formatDateTime(row.last_seen)}` : ""}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 tabular-nums text-[#1C1C1E]">{row.power_v != null ? `${row.power_v} V` : "—"}</td>
                    <td className="px-4 py-3">
                      {row.ignition == null ? "—" : (
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold" style={{ color: row.ignition ? "#34C759" : "#8E8E93" }}>
                          <Power size={11} /> {row.ignition ? "ON" : "OFF"}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {row.last_alarm ? (
                        <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10.5px] font-semibold" style={{ background: "#FF3B301A", color: "#FF3B30" }}>
                          <AlertTriangle size={10} /> {row.last_alarm}
                        </span>
                      ) : <span className="text-[#C7C7CC]">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-2">
                        {isEditing ? (
                          <>
                            <button onClick={() => save(row.vehicle_id)} disabled={busy}
                              className="inline-flex items-center gap-1 rounded-lg bg-[#007AFF] px-2.5 py-1.5 text-[11.5px] font-semibold text-white disabled:opacity-50"
                              data-testid={`gps-device-save-${row.vehicle_id}`}>
                              <Save size={12} /> Simpan
                            </button>
                            <button onClick={cancelEdit} disabled={busy}
                              className="inline-flex items-center gap-1 rounded-lg border border-[#E5E5EA] px-2.5 py-1.5 text-[11.5px] font-semibold text-[#6B6B73]"
                              data-testid={`gps-device-cancel-${row.vehicle_id}`}>
                              <X size={12} /> Batal
                            </button>
                          </>
                        ) : (
                          <>
                            <button onClick={() => startEdit(row)} disabled={busy}
                              className="inline-flex items-center gap-1 rounded-lg border border-[#E5E5EA] px-2.5 py-1.5 text-[11.5px] font-semibold text-[#007AFF]"
                              data-testid={`gps-device-edit-${row.vehicle_id}`}>
                              <Cpu size={12} /> {row.has_device ? "Ubah IMEI" : "Pasang"}
                            </button>
                            {row.has_device ? (
                              <button onClick={() => remove(row.vehicle_id)} disabled={busy}
                                className="inline-flex items-center gap-1 rounded-lg border border-[#FFD8D6] px-2.5 py-1.5 text-[11.5px] font-semibold text-[#FF3B30]"
                                data-testid={`gps-device-remove-${row.vehicle_id}`}>
                                <Trash2 size={12} /> Lepas
                              </button>
                            ) : null}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-[14px] border border-[#EFF0F2] bg-[#F7F8FA] p-4 text-[12px] leading-relaxed text-[#6B6B73]">
        <p className="mb-1 font-semibold text-[#1C1C1E]">Cara menghubungkan perangkat (Teltonika + Traccar)</p>
        <ol className="ml-4 list-decimal space-y-1">
          <li>Pasang device (mis. <b>Teltonika FMC130</b>) di kendaraan, arahkan ke server Traccar Anda (port <b>5027</b>).</li>
          <li>Di Traccar, aktifkan <b>Position Forwarding</b> ke webhook aplikasi ini (URL &amp; token disediakan admin).</li>
          <li>Masukkan <b>IMEI</b> device pada armada yang sesuai di tabel ini. Data lokasi/voltase/alarm akan otomatis masuk & jadi <b>backup</b> pelacakan (prioritas device di atas HP).</li>
        </ol>
      </div>
    </div>
  );
}

function OpsTracking() {
  const { user } = useAuth();
  const canManage = user && (user.role === "owner" || user.role === "ops_admin");
  const [mode, setMode] = useState("live");
  const [live, setLive] = useState([]);
  const [error, setError] = useState(null);
  const [trips, setTrips] = useState([]);
  const timer = useRef(null);

  const loadLive = useCallback(async () => {
    try {
      const res = await apiClient.get("/locations/live");
      setLive(Array.isArray(res.data) ? res.data : []);
      setError(null);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat posisi live");
    }
  }, []);

  useEffect(() => {
    loadLive();
    apiClient.get("/trips").then((r) => setTrips(Array.isArray(r.data) ? r.data : [])).catch(() => {});
    timer.current = setInterval(loadLive, 7000);
    return () => clearInterval(timer.current);
  }, [loadLive]);

  const modes = MODES.filter((m) => (["share", "devices"].includes(m.v) ? canManage : true));

  return (
    <div className="space-y-4" data-testid="gps-ops">
      <section className="section-card">
        <div className="section-head">
          <div className="flex min-w-0 items-center gap-2">
            <MapPin size={16} className="text-[#007AFF]" />
            <h2 className="truncate">Pelacakan & Perangkat GPS Armada</h2>
          </div>
          <button className="secondary-button flex-shrink-0" onClick={loadLive} data-testid="gps-refresh">
            <RefreshCw size={13} /> Muat ulang
          </button>
        </div>
        <div className="section-body space-y-4">
          <div className="inline-flex rounded-[12px] border border-[#EFF0F2] bg-[#F7F7F9] p-1" data-testid="gps-mode-tabs">
            {modes.map((m) => {
              const Icon = m.icon;
              const activeTab = mode === m.v;
              return (
                <button
                  key={m.v}
                  onClick={() => setMode(m.v)}
                  data-testid={`gps-mode-${m.v}`}
                  className={`flex items-center gap-1.5 rounded-[9px] px-3.5 py-1.5 text-[12px] font-semibold transition ${activeTab ? "bg-white text-[#007AFF] shadow-sm" : "text-[#6B6B73]"}`}
                >
                  <Icon size={13} /> {m.l}
                </button>
              );
            })}
          </div>

          {mode === "live" ? <LiveView live={live} trips={trips} error={error} /> : null}
          {mode === "history" ? <HistoryView /> : null}
          {mode === "devices" && canManage ? <DevicesView /> : null}
          {mode === "share" && canManage ? <ShareLinkPanel trips={trips} /> : null}
        </div>
      </section>
    </div>
  );
}

export default function GpsTracking() {
  const { user } = useAuth();
  if (user && user.role === "driver") return <DriverCheckin />;
  return <OpsTracking />;
}
