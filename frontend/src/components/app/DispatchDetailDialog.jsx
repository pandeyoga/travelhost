import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Phone, Truck, User2, Wallet, Camera, Route } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { LoadingState, ErrorState } from "@/components/shared/DataStates";
import { formatCurrency, formatDateTime } from "@/utils/formatters";

const BK_STATUS = { confirmed: ["Dikonfirmasi", "info"], ongoing: ["Berjalan", "warning"], completed: ["Selesai", "success"], pending: ["Pending", "neutral"], cancelled: ["Batal", "danger"], hold: ["Hold", "warning"] };
const TRIP_STATUS = { standby: ["Terjadwal", "info"], to_pickup: ["Menjemput", "warning"], on_trip: ["Dalam Perjalanan", "warning"], completed: ["Selesai", "success"], cancelled: ["Batal", "neutral"] };
const ACTOR_LABEL = { ops: "Ops/ERP", driver: "Driver", system: "Sistem" };
const ACTOR_TONE = { ops: "bg-[#EAF2FF] text-[#0058CC]", driver: "bg-[#E8F7EC] text-[#126E2C]", system: "bg-[#F1F1F4] text-[#6B6B73]" };

function Row({ label, children, testId }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 text-[12.5px]" data-testid={testId}>
      <span className="shrink-0 text-[#6B6B73]">{label}</span>
      <span className="text-right font-medium text-[#1C1C1E]">{children}</span>
    </div>
  );
}

// DispatchDetailDialog — klik baris papan operasi → detail penuh + TIMELINE gabungan
// aksi ops & driver (kedua sisi menulis dokumen trip yang sama → selalu sinkron).
export default function DispatchDetailDialog({ open, onOpenChange, bookingId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!bookingId) return;
    setLoading(true); setError(null);
    try {
      const r = await apiClient.get(`/dispatch/${bookingId}/detail`);
      setData(r.data);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat detail keberangkatan");
    } finally { setLoading(false); }
  }, [bookingId]);

  useEffect(() => { if (open) { setData(null); load(); } }, [open, load]);

  const bk = data?.booking || {};
  const trip = data?.trip || null;
  const bkSt = BK_STATUS[bk.status] || [bk.status, "neutral"];
  const trSt = trip?.status ? (TRIP_STATUS[trip.status] || [trip.status, "neutral"]) : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-xl" data-testid="dispatch-detail-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {bk.code || "Detail Keberangkatan"}
            <button className="icon-button !h-7 !w-7" title="Muat ulang" onClick={load} data-testid="dd-refresh"><RefreshCw size={13} /></button>
          </DialogTitle>
          <DialogDescription>{bk.customer_name || ""} — status di sini identik dengan yang dilihat driver.</DialogDescription>
        </DialogHeader>

        {loading && !data ? <LoadingState testId="dd-loading" /> : error ? <ErrorState message={error} onRetry={load} /> : data ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-1.5" data-testid="dd-status">
              <span className={`status-pill tone-${bkSt[1]}`}>Booking: {bkSt[0]}</span>
              {trSt ? <span className={`status-pill tone-${trSt[1]}`}>Trip: {trSt[0]}</span> : <span className="status-pill tone-neutral">Belum ada trip</span>}
              {bk.source === "web_booking" ? <span className="rounded-full bg-[#EAF2FF] px-2 py-0.5 text-[10.5px] font-semibold text-[#0058CC]">Online</span>
                : <span className="rounded-full bg-[#F1F1F4] px-2 py-0.5 text-[10.5px] font-semibold text-[#6B6B73]">Manual</span>}
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <section className="rounded-[12px] border border-[#EFF0F2] px-3 py-2" data-testid="dd-trip-info">
                <h4 className="mb-1 flex items-center gap-1.5 text-[12px] font-bold text-[#1C1C1E]"><Route size={13} className="text-[#007AFF]" /> Perjalanan</h4>
                <Row label="Rute">{bk.origin || "-"} → {bk.destination || "-"}</Row>
                <Row label="Mulai">{formatDateTime(bk.start_datetime)}</Row>
                <Row label="Selesai">{formatDateTime(bk.end_datetime)}</Row>
                {trip?.distance_km ? <Row label="Jarak">{trip.distance_km} km ({trip.distance_basis || "-"})</Row> : null}
                {trip?.odometer_start != null ? <Row label="Odometer">{trip.odometer_start} → {trip.odometer_end ?? "…"}</Row> : null}
              </section>
              <section className="rounded-[12px] border border-[#EFF0F2] px-3 py-2" data-testid="dd-crew-info">
                <h4 className="mb-1 flex items-center gap-1.5 text-[12px] font-bold text-[#1C1C1E]"><Truck size={13} className="text-[#007AFF]" /> Unit & Kontak</h4>
                <Row label="Armada">{bk.vehicle_name || "Belum di-assign"}</Row>
                <Row label="Driver"><span className="inline-flex items-center gap-1"><User2 size={11} /> {bk.driver_name || "Belum ada"}</span></Row>
                {data.driver?.phone ? <Row label="HP Driver"><span className="inline-flex items-center gap-1"><Phone size={11} /> {data.driver.phone}</span></Row> : null}
                {data.customer?.phone ? <Row label="HP Customer"><span className="inline-flex items-center gap-1"><Phone size={11} /> {data.customer.phone}</span></Row> : null}
                {trip?.driver_fee_total ? (
                  <Row label="Fee driver" testId="dd-fee">
                    <span className="inline-flex items-center gap-1"><Wallet size={11} /> {formatCurrency(trip.driver_fee_total)} ({formatCurrency(trip.driver_fee_rate)}/hari × {trip.driver_fee_days})</span>
                  </Row>
                ) : null}
              </section>
            </div>

            {trip?.pod ? (
              <section className="rounded-[12px] border border-[#D9F0E1] bg-[#F3FBF5] px-3 py-2" data-testid="dd-pod">
                <h4 className="mb-1 flex items-center gap-1.5 text-[12px] font-bold text-[#126E2C]"><Camera size={13} /> Bukti Layanan (POD)</h4>
                <p className="text-[12px] text-[#3C3C43]">Penerima: {trip.pod.recipient_name || "-"} · {formatDateTime(trip.pod.at)}</p>
                {trip.pod.note ? <p className="text-[12px] text-[#6B6B73]">{trip.pod.note}</p> : null}
                {trip.pod.photo_url ? <a className="text-[12px] font-semibold text-[#007AFF] hover:underline" href={trip.pod.photo_url} target="_blank" rel="noreferrer" data-testid="dd-pod-photo">Lihat foto POD</a> : null}
              </section>
            ) : null}

            <section data-testid="dd-timeline">
              <h4 className="mb-1.5 text-[12px] font-bold text-[#1C1C1E]">Timeline (Ops ↔ Driver)</h4>
              {(data.timeline || []).length === 0 ? (
                <p className="rounded-[10px] border border-dashed border-[#E5E5EA] px-3 py-2.5 text-[12px] text-[#8E8E93]" data-testid="dd-timeline-empty">
                  Belum ada aktivitas — timeline terisi setelah assign/konfirmasi/aksi driver.
                </p>
              ) : (
                <ol className="space-y-0">
                  {data.timeline.map((t, i) => (
                    <li key={i} className="relative flex items-start gap-2.5 pb-2.5 pl-4" data-testid={`dd-timeline-${i}`}>
                      <span className="absolute left-0 top-1.5 h-2 w-2 rounded-full bg-[#007AFF]" />
                      {i < data.timeline.length - 1 ? <span className="absolute left-[3.5px] top-4 h-full w-px bg-[#E5E5EA]" /> : null}
                      <div className="flex-1 text-[12.5px]">
                        <span className="font-medium text-[#1C1C1E]">{t.label}</span>
                        <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${ACTOR_TONE[t.actor] || ACTOR_TONE.system}`}>{ACTOR_LABEL[t.actor] || t.actor}</span>
                        <span className="block text-[11px] tabular-nums text-[#8E8E93]">{formatDateTime(t.at)}</span>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
