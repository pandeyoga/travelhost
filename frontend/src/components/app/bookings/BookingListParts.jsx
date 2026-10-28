// BookingListParts.jsx — kolom tabel, kartu ponsel, dan tombol aksi daftar Booking & Trip.
// Dipisah dari features/app/Bookings.jsx (batas 500 baris) dan dipakai dua tampilan: tabel
// (layar lebar) dan kartu (layar sempit) — aturan tombol satu tempat (lib/bookingRules).
import {
  Wallet, Pencil, CalendarClock, ShieldCheck, Users, Clock, MessageCircle, CheckCircle2, XCircle, Ban,
} from "lucide-react";
import { bookingStatusLabel, bookingStatusTone, paymentState } from "@/lib/statusLabels";
import { EDITABLE, canComplete, canPay, canSendInvoiceWa, isWebSource } from "@/lib/bookingRules";
import { formatCurrency, formatDateTime } from "@/utils/formatters";

// Sumber pesanan menentukan SOP: pesanan online menunggu ACC/DP & bisa hangus sendiri,
// pesanan buatan ops tidak. Label WAJIB di kedua sisi agar tak ada ambiguitas.
export function SourceBadge({ source }) {
  if (isWebSource(source)) {
    return (
      <span className="inline-block rounded-full bg-[#EAF2FF] px-1.5 py-0.5 text-[10px] font-semibold text-[#0058CC]"
        title={source === "public" ? "Permintaan khusus dari situs publik" : "Pesan online dari situs publik"}>
        {source === "public" ? "Online · Permintaan" : "Online"}
      </span>
    );
  }
  return <span className="inline-block rounded-full bg-[#F1F1F4] px-1.5 py-0.5 text-[10px] font-semibold text-[#6B6B73]">Manual</span>;
}

export function BookingStatusPill({ status, testId }) {
  return (
    <span className={`status-pill tone-${bookingStatusTone(status)}`} title={bookingStatusLabel(status)} data-testid={testId}>
      {bookingStatusLabel(status, { short: true })}
    </span>
  );
}

// Pill pembayaran = SSOT paymentState(): "DP kurang" bila hold belum menutup DP wajib,
// "Denda ditahan" untuk pesanan batal yang uangnya ditahan.
export function PaymentStatePill({ booking, testId }) {
  const ps = paymentState(booking);
  if (ps.label === "—") return <span className="px-1 text-[12px] text-[#B0B1B8]" data-testid={testId}>—</span>;
  return <span className={`status-pill tone-${ps.tone}`} data-testid={testId}>{ps.label}</span>;
}

// Pesanan online sewa harian tidak mengisi asal/tujuan (tamu hanya memberi titik jemput),
// jadi jatuhkan ke `pickup_address` daripada menampilkan "—" yang menyesatkan.
export const tripLabel = (r) => r.route_name
  || (r.origin || r.destination ? `${r.origin || "-"} → ${r.destination || "-"}` : (r.pickup_address || "—"));

const tripMeta = (r) => `${r.pax ? `${r.pax} pax` : ""}${r.service_label ? `${r.pax ? " · " : ""}${r.service_label}` : ""}`;

function GroupPill({ r }) {
  if (!r.group_id) return null;
  return (
    <span className="status-pill tone-info !px-1.5 !py-0 !text-[10px]" title={`Grup ${r.group_index}/${r.group_size}`}>
      <Users size={9} /> Grup {r.group_index}/{r.group_size}
    </span>
  );
}

// Satu tombol aksi: ikon ringkas di tabel (muat di 1360px tanpa geser), ikon + teks di kartu.
function ActionButton({ icon: Icon, label, onClick, disabled, testId, color, compact }) {
  if (compact) {
    return (
      <button type="button" className={`icon-button !h-7 !w-7 shrink-0 ${color || ""}`} title={label} aria-label={label}
        disabled={disabled} onClick={onClick} data-testid={testId}>
        <Icon size={13} />
      </button>
    );
  }
  return (
    <button type="button" className={`secondary-button !px-2.5 !py-1.5 !text-[12px] ${color || ""}`} aria-label={label}
      disabled={disabled} onClick={onClick} data-testid={testId}>
      <Icon size={13} /> {label}
    </button>
  );
}

export const hasRowActions = (r) => r.status === "pending" || canSendInvoiceWa(r) || canPay(r)
  || EDITABLE.includes(r.status) || canComplete(r);

/**
 * Aksi per booking. `on` = { approve(r, mode), reject, pay, edit, reschedule, complete, cancel,
 * invoiceWa }. `testPrefix` membedakan testid tabel ("booking") dan kartu ("booking-m").
 */
export function BookingRowActions({ row: r, busyId, on, compact = true, testPrefix = "booking" }) {
  const busy = busyId === r.id;
  const tid = (k) => `${testPrefix}-${k}-${r.id}`;
  const btn = ({ key, ...props }) => <ActionButton key={key} compact={compact} {...props} />;
  if (r.status === "pending") {
    return (
      <div className={`flex flex-wrap gap-1 ${compact ? "justify-end" : ""}`}>
        {btn({ icon: ShieldCheck, label: "Setujui", color: "!text-[#126E2C]", disabled: busy, onClick: () => on.approve(r, "confirm"), testId: tid("approve") })}
        {btn({ icon: Clock, label: "ACC + Minta DP", color: "!text-[#0A5BD3]", disabled: busy, onClick: () => on.approve(r, "hold"), testId: tid("approve-hold") })}
        {btn({ icon: Ban, label: "Tolak", color: "!text-[#A8221A]", disabled: busy, onClick: () => on.reject(r), testId: tid("reject") })}
      </div>
    );
  }
  const items = [];
  if (canSendInvoiceWa(r)) items.push(btn({ key: "wa", icon: MessageCircle, label: "Kirim invoice WA", color: "!text-[#127A36]", disabled: busy, onClick: () => on.invoiceWa(r), testId: tid("invoice-wa") }));
  if (canPay(r)) items.push(btn({ key: "pay", icon: Wallet, label: "Bayar", onClick: () => on.pay(r), testId: tid("pay") }));
  if (EDITABLE.includes(r.status)) {
    items.push(btn({ key: "edit", icon: Pencil, label: "Edit", onClick: () => on.edit(r), testId: tid("edit") }));
    items.push(btn({ key: "rs", icon: CalendarClock, label: "Jadwal ulang", onClick: () => on.reschedule(r), testId: tid("reschedule") }));
  }
  if (canComplete(r)) items.push(btn({ key: "done", icon: CheckCircle2, label: "Selesai", color: "!text-[#126E2C]", disabled: busy, onClick: () => on.complete(r), testId: tid("complete") }));
  if (EDITABLE.includes(r.status)) items.push(btn({ key: "cancel", icon: XCircle, label: "Batal", color: "!text-[#A8221A]", disabled: busy, onClick: () => on.cancel(r), testId: tid("cancel") }));
  if (!items.length) return <span className="text-[12px] text-[#B0B1B8]">—</span>;
  return <div className={`flex flex-wrap gap-1 ${compact ? "justify-end" : ""}`}>{items}</div>;
}

export function buildBookingColumns({ canManage, renderActions }) {
  const columns = [
    { key: "code", label: "Kode", mono: true, render: (r) => (
      <div className="flex flex-col items-start gap-0.5">
        <span className="font-semibold text-[#1C1C1E]">{r.code}</span>
        <GroupPill r={r} />
      </div>
    ) },
    { key: "customer_name", label: "Customer", render: (r) => (
      <div className="min-w-0 max-w-[150px]">
        <span className="block truncate text-[#1C1C1E]" title={r.customer_name}>{r.customer_name}</span>
        <span className="mt-0.5 block"><SourceBadge source={r.source} /></span>
      </div>
    ) },
    { key: "vehicle_name", label: "Armada & sopir", render: (r) => (
      <div className="min-w-0 max-w-[140px]">
        <span className="block truncate text-[#1C1C1E]" title={r.vehicle_name || ""}>{r.vehicle_name || "—"}</span>
        {/* Sopir wajib terlihat di daftar: "belum ada sopir" adalah temuan operasional
            paling sering dan sebelumnya hanya bisa dilihat dengan membuka detail satu-satu. */}
        <span className={`block truncate text-[11px] ${r.driver_name ? "text-[#8E8E93]" : "text-[#A8221A]"}`}>
          {r.driver_name || "Belum ada sopir"}
        </span>
      </div>
    ) },
    { key: "trip", label: "Perjalanan", render: (r) => (
      <div className="min-w-0 max-w-[160px]">
        <span className="block truncate text-[#1F1F25]" title={tripLabel(r)}>{tripLabel(r)}</span>
        <span className="block truncate text-[11px] text-[#8E8E93]">{tripMeta(r)}</span>
      </div>
    ) },
    { key: "start_datetime", label: "Mulai", render: (r) => (
      <div>
        <span className="block">{formatDateTime(r.start_datetime)}</span>
        {r.end_datetime ? <span className="block text-[11px] text-[#8E8E93]">s/d {formatDateTime(r.end_datetime)}</span> : null}
      </div>
    ) },
    { key: "total_amount", label: "Total & terbayar", align: "right", mono: true, render: (r) => (
      <div className="text-right">
        <span className="block tabular-nums">{formatCurrency(r.total_amount)}</span>
        {/* Angka terbayar adalah dasar keputusan DP/pelunasan — status "belum bayar/DP"
            saja tidak cukup untuk tahu berapa yang sudah masuk. */}
        <span className={`block text-[11px] tabular-nums ${Number(r.paid_amount) > 0 ? "text-[#1B7F3B]" : "text-[#8E8E93]"}`}>
          terbayar {formatCurrency(r.paid_amount || 0)}
        </span>
      </div>
    ) },
    // Status booking + pembayaran ditumpuk satu kolom (dulu 2 kolom → tabel 1406px, kolom Aksi
    // terpotong di layar 1360px).
    { key: "status", label: "Status", render: (r) => (
      <div className="flex flex-col items-start gap-1">
        <BookingStatusPill status={r.status} testId={`booking-status-${r.id}`} />
        <PaymentStatePill booking={r} testId={`booking-payment-${r.id}`} />
      </div>
    ) },
  ];
  if (canManage) columns.push({ key: "aksi", label: "Aksi", align: "right", render: (r) => renderActions(r, true) });
  return columns;
}

// Kartu satu booking untuk layar sempit — informasi sama dengan baris tabel, aksi bertombol teks.
export function BookingCard({ row: r, actions }) {
  return (
    <div data-testid={`booking-card-${r.id}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-semibold tabular-nums text-[#1C1C1E]">{r.code}</span>
            <GroupPill r={r} />
            <SourceBadge source={r.source} />
          </div>
          <p className="truncate text-[13px] text-[#1C1C1E]" title={r.customer_name}>{r.customer_name}</p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1 md:flex-row md:items-center">
          <BookingStatusPill status={r.status} />
          <PaymentStatePill booking={r} />
        </div>
      </div>
      {/* Ponsel: 2 kolom (jadwal | total, lalu rute & armada selebar kartu). Tablet/laptop sempit:
          satu baris 4 kolom agar kartu tidak lowong. */}
      <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1.5 text-[12px] md:grid-cols-[1fr_1.3fr_1.2fr_auto] md:items-start">
        <div className="order-1 min-w-0">
          <span className="block text-[#1F1F25]">{formatDateTime(r.start_datetime)}</span>
          {r.end_datetime ? <span className="block text-[11px] text-[#8E8E93]">s/d {formatDateTime(r.end_datetime)}</span> : null}
        </div>
        <div className="order-2 text-right md:order-4">
          <span className="block font-semibold tabular-nums text-[#1C1C1E]">{formatCurrency(r.total_amount)}</span>
          <span className={`block text-[11px] tabular-nums ${Number(r.paid_amount) > 0 ? "text-[#1B7F3B]" : "text-[#8E8E93]"}`}>terbayar {formatCurrency(r.paid_amount || 0)}</span>
        </div>
        <div className="order-3 col-span-2 min-w-0 truncate text-[#3C3C43] md:order-2 md:col-span-1" title={tripLabel(r)}>
          {tripLabel(r)}{tripMeta(r) ? <span className="text-[#8E8E93]"> · {tripMeta(r)}</span> : null}
        </div>
        <div className="order-4 col-span-2 min-w-0 truncate text-[#3C3C43] md:order-3 md:col-span-1">
          {r.vehicle_name || "—"} · <span className={r.driver_name ? "text-[#8E8E93]" : "text-[#A8221A]"}>{r.driver_name || "Belum ada sopir"}</span>
        </div>
      </div>
      {actions ? <div className="mt-2.5 border-t border-[#F2F2F5] pt-2.5">{actions}</div> : null}
    </div>
  );
}
