// ScheduleDetailDialog.jsx — detail satu keberangkatan di halaman jadwal publik.
// SENGAJA tanpa tombol aksi apa pun (read-only): penerima tautan tidak punya akun.
import {
  Bus, CalendarDays, Clock, Lock, MapPin, Phone, Route as RouteIcon, StickyNote, User, Users, Wallet,
} from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import Field from "@/components/app/calendar/DetailField";
import { PaymentPill } from "@/components/shared/StatusPill";
import { formatDateTime } from "@/utils/formatters";
import { bi } from "@/lib/i18n";
import { SchedulePill } from "./ScheduleTable";

export default function ScheduleDetailDialog({ item, lang, onOpenChange }) {
  const it = item || {};
  return (
    <Dialog open={Boolean(item)} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-md" data-testid="schedule-detail">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <span className="font-mono">{it.ref}</span>
            <SchedulePill status={it.status} lang={lang} testId="schedule-detail-status" />
            {"payment_status" in it ? <PaymentPill value={it.payment_status} testId="schedule-detail-payment" /> : null}
          </DialogTitle>
          <DialogDescription>{it.origin || "-"} → {it.destination || "-"}</DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 gap-3.5 rounded-xl border border-[#EFF0F2] bg-[#FBFBFD] p-3.5">
          <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
            <Field icon={CalendarDays} label={bi("Berangkat", "Departure", lang)} testId="sd-start">{formatDateTime(it.start_datetime)}</Field>
            <Field icon={Clock} label={bi("Kembali", "Return", lang)} testId="sd-end">{formatDateTime(it.end_datetime)}</Field>
          </div>
          <Field icon={RouteIcon} label={bi("Rute", "Route", lang)} testId="sd-route">
            <span className="inline-flex flex-wrap items-center gap-1.5"><MapPin size={12} className="text-[#8E8E93]" />{it.origin || "-"} → {it.destination || "-"}</span>
          </Field>
          <Field icon={Bus} label={bi("Armada", "Vehicle", lang)} testId="sd-vehicle">
            <span className="font-semibold">{it.vehicle_name || <span className="text-[#B0B1B8]">{bi("Belum ditetapkan", "Not assigned yet", lang)}</span>}</span>
            <p className="text-[12px] text-[#8E8E93]">
              {[it.plate_number, it.vehicle_type_label, it.capacity ? `${it.capacity} ${bi("kursi", "seats", lang)}` : null].filter(Boolean).join(" · ") || "-"}
            </p>
          </Field>
          {it.pax ? <Field icon={Users} label={bi("Penumpang", "Passengers", lang)} testId="sd-pax">{it.pax} pax</Field> : null}
          {"customer_name" in it ? <Field icon={Users} label={bi("Pelanggan", "Customer", lang)} testId="sd-customer">{it.customer_name || "-"}</Field> : null}
          {"driver_name" in it ? (
            <Field icon={User} label={bi("Sopir", "Driver", lang)} testId="sd-driver">
              {it.driver_name || <span className="text-[#B0B1B8]">{bi("Belum ditugaskan", "Not assigned yet", lang)}</span>}
              {it.driver_phone ? <a href={`tel:${it.driver_phone}`} className="mt-0.5 flex items-center gap-1 text-[12.5px] text-[#007AFF]"><Phone size={12} /> {it.driver_phone}</a> : null}
            </Field>
          ) : null}
          {"payment_status" in it ? (
            <Field icon={Wallet} label={bi("Pembayaran", "Payment", lang)} testId="sd-payment"><PaymentPill value={it.payment_status} /></Field>
          ) : null}
          {it.notes ? <Field icon={StickyNote} label={bi("Catatan", "Notes", lang)} testId="sd-notes"><span className="whitespace-pre-line text-[13px] text-[#3a3f4a]">{it.notes}</span></Field> : null}
        </div>
        <p className="flex items-center gap-1.5 text-[11.5px] text-[#8E8E93]" data-testid="sd-readonly">
          <Lock size={12} /> {bi("Tampilan hanya-baca. Hubungi admin untuk perubahan jadwal.", "Read-only view. Contact the admin to change the schedule.", lang)}
        </p>
      </DialogContent>
    </Dialog>
  );
}
