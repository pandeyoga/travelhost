import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { MapPin, Clock, Gauge, Navigation, AlertTriangle, Wifi, WifiOff } from "lucide-react";
import apiClient from "@/services/apiClient";
import LiveMap from "@/components/app/LiveMap";
import { formatDateTime, formatQty } from "@/utils/formatters";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

const STATUS_LABEL = (lang) => ({
  standby: bi("Standby", "Standby", lang), to_pickup: bi("Menuju Penjemputan", "Heading to Pickup", lang),
  on_trip: bi("Dalam Perjalanan", "On the Trip", lang), completed: bi("Tiba di Tujuan", "Arrived", lang),
});

export default function PublicTrack() {
  const { token } = useParams();
  const lang = useLangValue();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const timer = useRef(null);

  const load = useCallback(async () => {
    try {
      const r = await apiClient.get(`/public/track/${token}`);
      setData(r.data);
      setError(null);
    } catch (e) {
      setError(e?.response?.data?.detail || bi("Tautan pelacakan tidak tersedia.", "The tracking link is unavailable.", lang));
    } finally {
      setLoading(false);
    }
  }, [token, lang]);

  useEffect(() => {
    load();
    timer.current = setInterval(load, 10000);
    return () => clearInterval(timer.current);
  }, [load]);

  const cur = data && data.current;
  const live = cur
    ? [{ vehicle_id: "trk", vehicle_name: data.vehicle_name, plate_number: data.plate_number, ...cur }]
    : [];
  const destination = data && data.destination
    ? { lat: data.destination.lat, lng: data.destination.lng, name: data.dest_name }
    : null;

  return (
    <div style={{ minHeight: "100vh", background: "#F2F3F7" }} data-testid="public-track-page">
      <header className="flex items-center justify-between border-b border-[#E6E7EB] bg-white px-5 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#007AFF]"><Navigation size={16} className="text-white" /></div>
          <div>
            <p className="text-[14px] font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>RahazaTrans</p>
            <p className="text-[11px] text-[#8E8E93]">{bi("Pelacakan Armada Langsung", "Live Vehicle Tracking", lang)}</p>
          </div>
        </div>
        {data ? (
          <span className={`status-pill ${data.stale ? "tone-neutral" : "tone-success"}`}>
            {data.stale ? <WifiOff size={11} /> : <Wifi size={11} />} {data.stale ? "Offline" : "Live"}
          </span>
        ) : null}
      </header>

      <main className="mx-auto max-w-3xl space-y-4 p-4">
        {loading ? (
          <div className="rounded-[14px] border border-[#EFF0F2] bg-white p-10 text-center text-[13px] text-[#8E8E93]" data-testid="public-track-loading">
            {bi("Memuat data pelacakan…", "Loading tracking data…", lang)}
          </div>
        ) : error ? (
          <div className="flex flex-col items-center rounded-[14px] border border-[#FFD0CC] bg-[#FFF5F4] px-6 py-14 text-center" data-testid="public-track-error">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[#FFE0DC]"><AlertTriangle size={22} className="text-[#FF3B30]" /></div>
            <h3 className="text-base font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>{bi("Tidak dapat memuat", "Unable to load", lang)}</h3>
            <p className="mt-1 max-w-sm text-sm text-[#6B6B73]">{error}</p>
          </div>
        ) : (
          <>
            <div className="rounded-[14px] border border-[#EFF0F2] bg-white p-4 shadow-sm" data-testid="public-track-info">
              <div className="flex items-center justify-between">
                <div className="min-w-0">
                  <p className="text-[15px] font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>{data.vehicle_name || bi("Armada", "Vehicle", lang)}</p>
                  <p className="text-[12px] text-[#8E8E93]">{data.plate_number || ""} · {bi("Tujuan", "Destination", lang)}: {data.dest_name || "-"}</p>
                </div>
                <span className="status-pill tone-info">{STATUS_LABEL(lang)[data.status] || data.status}</span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2">
                <div className="rounded-lg bg-[#F0F6FF] p-3">
                  <div className="flex items-center gap-1 text-[11px] text-[#6B6B73]"><Clock size={12} /> ETA</div>
                  <div className="mt-1 text-[18px] font-bold tabular-nums text-[#0058CC]" style={{ fontFamily: "Outfit, sans-serif" }}>
                    {data.eta ? `${formatQty(Math.round(data.eta.eta_minutes))} ${bi("mnt", "min", lang)}` : "-"}
                  </div>
                </div>
                <div className="rounded-lg bg-[#F1FBF3] p-3">
                  <div className="flex items-center gap-1 text-[11px] text-[#6B6B73]"><Gauge size={12} /> {bi("Jarak", "Distance", lang)}</div>
                  <div className="mt-1 text-[18px] font-bold tabular-nums text-[#126E2C]" style={{ fontFamily: "Outfit, sans-serif" }}>
                    {data.eta ? `${formatQty(data.eta.distance_km)} km` : "-"}
                  </div>
                </div>
                <div className="rounded-lg bg-[#F7F7F9] p-3">
                  <div className="flex items-center gap-1 text-[11px] text-[#6B6B73]"><MapPin size={12} /> {bi("Update", "Updated", lang)}</div>
                  <div className="mt-1 text-[12px] font-semibold text-[#1C1C1E]">{cur ? formatDateTime(cur.timestamp) : "-"}</div>
                </div>
              </div>
            </div>

            <div className="overflow-hidden rounded-[14px] border border-[#EFF0F2] bg-white shadow-sm" style={{ height: 460 }}>
              {live.length === 0 ? (
                <div className="flex h-full items-center justify-center text-[13px] text-[#8E8E93]" data-testid="public-track-empty">
                  {bi("Belum ada posisi GPS terkirim untuk perjalanan ini.", "No GPS position has been sent for this trip yet.", lang)}
                </div>
              ) : (
                <LiveMap live={live} track={data.track || []} destination={destination} testId="public-track-map" />
              )}
            </div>
            <p className="text-center text-[11px] text-[#A0A0A8]">{bi(`Diperbarui otomatis setiap 10 detik · Tautan berlaku s/d ${formatDateTime(data.expires_at)}`, `Auto-refreshes every 10 seconds · Link valid until ${formatDateTime(data.expires_at)}`, lang)}</p>
          </>
        )}
      </main>
    </div>
  );
}
