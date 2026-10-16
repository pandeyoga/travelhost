import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Navigation, MapPin, Play, Flag, Send, LocateFixed, RefreshCw } from "lucide-react";
import apiClient from "@/services/apiClient";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { StatusPill } from "@/components/shared/StatusPill";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { formatDateTime, formatQty } from "@/utils/formatters";

const TRIP_TONE = { standby: "neutral", to_pickup: "warning", on_trip: "info", completed: "success" };
const TRIP_LABEL = { standby: "Standby", to_pickup: "Menuju Penjemputan", on_trip: "Dalam Perjalanan", completed: "Selesai" };

export default function DriverCheckin() {
  const [trips, setTrips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tripId, setTripId] = useState("");
  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");
  const [lastSent, setLastSent] = useState(null);
  const [sentCount, setSentCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const autoRef = useRef(null);
  const [auto, setAuto] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get("/driver/my-trips");
      const list = Array.isArray(res.data) ? res.data : [];
      setTrips(list);
      setTripId((prev) => prev || (list.find((t) => t.status !== "completed") || list[0] || {}).id || "");
      setError(null);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat tugas");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => () => { if (autoRef.current) clearInterval(autoRef.current); }, []);

  const trip = trips.find((t) => t.id === tripId);

  const sendLocation = useCallback(async (la, ln) => {
    if (!tripId) { toast.error("Pilih trip dulu"); return; }
    if (la == null || ln == null || Number.isNaN(Number(la)) || Number.isNaN(Number(ln))) {
      toast.error("Koordinat tidak valid"); return;
    }
    try {
      const res = await apiClient.post("/locations", { trip_id: tripId, lat: Number(la), lng: Number(ln), speed: 0 });
      setLastSent(res.data);
      setSentCount((c) => c + 1);
      toast.success("Lokasi terkirim");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengirim lokasi");
    }
  }, [tripId]);

  const shareGps = useCallback(() => {
    if (!navigator.geolocation) { toast.error("Perangkat tidak mendukung GPS"); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const la = pos.coords.latitude; const ln = pos.coords.longitude;
        setLat(String(la.toFixed(6))); setLng(String(ln.toFixed(6)));
        sendLocation(la, ln);
      },
      () => toast.error("Tidak bisa mengambil lokasi GPS — gunakan input manual"),
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }, [sendLocation]);

  const setStatus = useCallback(async (action) => {
    if (!tripId) return;
    setBusy(true);
    try {
      if (action === "checkin") await apiClient.post("/driver/checkin", { trip_id: tripId });
      else if (action === "start") await apiClient.post(`/trips/${tripId}/status`, { status: "on_trip" });
      else if (action === "checkout") await apiClient.post("/driver/checkout", { trip_id: tripId });
      toast.success("Status diperbarui");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memperbarui status");
    } finally {
      setBusy(false);
    }
  }, [tripId, load]);

  const toggleAuto = useCallback(() => {
    if (auto) {
      if (autoRef.current) clearInterval(autoRef.current);
      autoRef.current = null; setAuto(false); toast("Auto-share dimatikan");
    } else {
      if (!navigator.geolocation) { toast.error("GPS tidak tersedia"); return; }
      setAuto(true); toast("Auto-share aktif (tiap 10 dtk)");
      autoRef.current = setInterval(shareGps, 10000);
      shareGps();
    }
  }, [auto, shareGps]);

  if (loading) return <LoadingState testId="driver-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (trips.length === 0)
    return <EmptyState title="Belum ada tugas" description="Trip yang ditugaskan ke Anda akan muncul di sini." testId="driver-empty" />;

  return (
    <div className="mx-auto max-w-2xl space-y-4" data-testid="driver-checkin-page">
      <section className="section-card">
        <div className="section-head">
          <div className="flex min-w-0 items-center gap-2">
            <Navigation size={16} className="text-[#007AFF]" />
            <h2 className="truncate">Check-in &amp; Bagikan Lokasi</h2>
          </div>
          <button className="secondary-button flex-shrink-0" onClick={load} data-testid="driver-refresh">
            <RefreshCw size={13} /> Muat ulang
          </button>
        </div>
        <div className="section-body space-y-4">
          <div>
            <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Trip Aktif</label>
            <Select value={tripId} onValueChange={setTripId}>
              <SelectTrigger data-testid="driver-trip-select"><SelectValue placeholder="Pilih trip" /></SelectTrigger>
              <SelectContent>
                {trips.map((t) => (
                  <SelectItem key={t.id} value={t.id}>{(t.dest_name || "Trip")} — {TRIP_LABEL[t.status] || t.status}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {trip ? (
            <div className="rounded-[14px] border border-[#EFF0F2] bg-[#FAFBFC] p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MapPin size={15} className="text-[#FF3B30]" />
                  <span className="text-[14px] font-semibold text-[#1C1C1E]">{trip.dest_name || "Tujuan"}</span>
                </div>
                <StatusPill value={trip.status} tone={TRIP_TONE[trip.status] || "neutral"} />
              </div>
            </div>
          ) : null}

          {/* AKSI STATUS */}
          <div className="flex flex-wrap gap-2">
            <button className="secondary-button" disabled={busy} onClick={() => setStatus("checkin")} data-testid="driver-checkin-btn">
              <MapPin size={14} /> Check-in (Menuju Jemput)
            </button>
            <button className="secondary-button" disabled={busy} onClick={() => setStatus("start")} data-testid="driver-start-btn">
              <Play size={14} /> Mulai Perjalanan
            </button>
            <button className="secondary-button" disabled={busy} onClick={() => setStatus("checkout")} data-testid="driver-checkout-btn">
              <Flag size={14} /> Selesai
            </button>
          </div>
        </div>
      </section>

      {/* BAGIKAN LOKASI */}
      <section className="section-card">
        <div className="section-head"><h2>Bagikan Lokasi</h2></div>
        <div className="section-body space-y-3">
          <div className="flex flex-wrap gap-2">
            <button className="primary-button" onClick={shareGps} data-testid="driver-share-gps">
              <LocateFixed size={14} /> Bagikan Lokasi GPS Sekarang
            </button>
            <button className={`secondary-button ${auto ? "!bg-[#FFF3E8] !text-[#C25400]" : ""}`} onClick={toggleAuto} data-testid="driver-auto-toggle">
              {auto ? "Hentikan Auto-share" : "Auto-share (10 dtk)"}
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Lat (manual)</label>
              <Input value={lat} onChange={(e) => setLat(e.target.value)} placeholder="-6.9147" data-testid="driver-lat-input" />
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Lng (manual)</label>
              <Input value={lng} onChange={(e) => setLng(e.target.value)} placeholder="107.6098" data-testid="driver-lng-input" />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="secondary-button" onClick={() => { setLat("-6.9147"); setLng("107.6098"); }} data-testid="driver-sample-loc">
              Isi lokasi contoh (Bandung)
            </button>
            <button className="primary-button" onClick={() => sendLocation(lat, lng)} data-testid="driver-send-manual">
              <Send size={14} /> Kirim Lokasi Manual
            </button>
          </div>
          {lastSent ? (
            <div className="rounded-lg bg-[#F1FBF3] p-3 text-[12px] text-[#126E2C]" data-testid="driver-last-sent">
              Terkirim {formatQty(sentCount)}× · terakhir {formatDateTime(lastSent.timestamp)} ({Number(lastSent.lat).toFixed(4)}, {Number(lastSent.lng).toFixed(4)})
            </div>
          ) : (
            <p className="text-[12px] text-[#8E8E93]">Belum ada lokasi dikirim sesi ini.</p>
          )}
        </div>
      </section>
    </div>
  );
}
