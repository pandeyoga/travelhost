import { Ban, Clock, Globe, ShieldCheck, Users, MapPin, CalendarDays } from "lucide-react";
import { formatCurrency, formatDateTime } from "@/utils/formatters";
import { vtypeLabel } from "@/components/app/calendar/calendarCore";

// OnlineOrdersPanel — inbox pesanan MASUK dari WEBSITE (wizard `web_booking` + permintaan khusus
// `public`, status pending). User journey ops: pesanan online harus TERLIHAT PERTAMA & bisa
// ditindak 1 klik — dua keputusan yang sama dengan daftar Booking & Kalender (Setujui langsung /
// ACC + Minta DP) atau Tolak (dialog beralasan).
export default function OnlineOrdersPanel({ rows, busyId, onApprove, onReject }) {
  if (!rows || rows.length === 0) return null;
  return (
    <section className="rounded-[14px] border border-[#BBD8FF] bg-gradient-to-br from-[#F2F8FF] to-[#EAF2FF] p-4" data-testid="online-orders-panel">
      <div className="mb-3 flex items-center gap-2">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#0A5BD3] text-white"><Globe size={15} /></span>
        <div className="min-w-0">
          <h3 className="text-[14px] font-bold text-[#0B3B82]" style={{ fontFamily: "Outfit, sans-serif" }}>
            Pesanan Website Masuk
          </h3>
          <p className="text-[11.5px] text-[#4A6B9B]">Permintaan online menunggu keputusan — setujui langsung, ACC + minta DP, atau tolak.</p>
        </div>
        <span className="ml-auto rounded-full bg-[#0A5BD3] px-2.5 py-0.5 text-[12px] font-bold text-white" data-testid="online-orders-count">{rows.length}</span>
      </div>
      <div className="space-y-2">
        {rows.map((r) => {
          const special = r.source === "public";
          return (
            <div key={r.id} className="flex flex-wrap items-center gap-3 rounded-[12px] border border-[#D5E6FF] bg-white px-3.5 py-3 shadow-sm" data-testid={`online-order-${r.id}`}>
              <div className="min-w-[160px]">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="font-bold text-[#1C1C1E]">{r.code}</span>
                  <span className="rounded-full bg-[#EAF2FF] px-1.5 py-0.5 text-[10px] font-semibold text-[#0058CC]">
                    {special ? "Online · Permintaan" : "Online"}
                  </span>
                </div>
                <span className="block text-[12px] text-[#6B6B73]">{r.customer_name}</span>
              </div>
              <div className="min-w-[170px] text-[12px] text-[#3C3C43]">
                <span className="flex items-center gap-1"><MapPin size={11} className="text-[#007AFF]" />
                  {r.route_name || (r.origin || r.destination ? `${r.origin || "-"} → ${r.destination || "-"}` : (r.pickup_address || "—"))}
                </span>
                <span className="mt-0.5 flex items-center gap-1 text-[#6B6B73]"><CalendarDays size={11} /> {formatDateTime(r.start_datetime)}</span>
              </div>
              <div className="text-[12px] text-[#3C3C43]">
                {r.pax || r.vehicle_name || r.requested_vehicle_type ? (
                  <span className="flex items-center gap-1"><Users size={11} />
                    {[r.pax ? `${r.pax} pax` : "", r.vehicle_name || (r.requested_vehicle_type ? vtypeLabel(r.requested_vehicle_type) : "")].filter(Boolean).join(" · ")}
                  </span>
                ) : null}
                {Number(r.total_amount) > 0 ? (
                  <span className="block font-semibold tabular-nums text-[#1C1C1E]">{formatCurrency(r.total_amount)}</span>
                ) : (
                  <span className="block text-[11.5px] text-[#8C4A00]" data-testid={`online-order-noprice-${r.id}`}>Harga & unit ditetapkan saat ACC</span>
                )}
              </div>
              <div className="flex w-full flex-wrap gap-1.5 sm:ml-auto sm:w-auto">
                <button className="primary-button !h-8 !px-2.5 !text-[12px]" disabled={busyId === r.id}
                  onClick={() => onApprove(r, "confirm")} data-testid={`booking-approve-${r.id}`}
                  title="Pilih/konfirmasi armada lalu setujui — pesanan langsung terkonfirmasi">
                  <ShieldCheck size={13} /> Setujui
                </button>
                <button className="secondary-button !h-8 !px-2.5 !text-[12px] !text-[#0A5BD3]" disabled={busyId === r.id}
                  onClick={() => onApprove(r, "hold")} data-testid={`booking-approve-hold-${r.id}`}
                  title="Setujui & tahan unit, lalu minta DP ke pelanggan">
                  <Clock size={13} /> ACC + Minta DP
                </button>
                <button className="secondary-button !h-8 !px-2.5 !text-[12px] !text-[#A8221A]" disabled={busyId === r.id}
                  onClick={() => onReject(r)} data-testid={`booking-reject-${r.id}`}>
                  <Ban size={13} /> Tolak
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
