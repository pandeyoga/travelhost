import { useState } from "react";
import { CalendarRange, Plus, Wallet, Pencil, CalendarClock, ShieldCheck, Users, Clock, MessageCircle } from "lucide-react";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/context/AuthContext";
import apiClient from "@/services/apiClient";
import { toast } from "sonner";
import DataTable from "@/components/shared/DataTable";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { StatusPill, PaymentPill } from "@/components/shared/StatusPill";
import BookingFormDialog from "@/components/app/BookingFormDialog";
import OnlineOrdersPanel from "@/components/app/OnlineOrdersPanel";
import BookingEditDialog from "@/components/app/BookingEditDialog";
import BookingRescheduleDialog from "@/components/app/BookingRescheduleDialog";
import BookingApproveDialog from "@/components/app/BookingApproveDialog";
import GroupBookingDialog from "@/components/app/GroupBookingDialog";
import CancelBookingDialog from "@/components/app/CancelBookingDialog";
import PaymentDialog from "@/components/app/PaymentDialog";
import PaymentProofsPanel from "@/components/app/PaymentProofsPanel";
import { formatCurrency, formatDateTime, formatQty } from "@/utils/formatters";

const STATUS_TONE = { pending: "warning", hold: "warning", confirmed: "info", ongoing: "warning", completed: "success", cancelled: "danger", draft: "neutral" };
const ACTIVE = ["hold", "confirmed", "ongoing"];

export default function Bookings() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useResource("/bookings");
  const [createOpen, setCreateOpen] = useState(false);
  const [groupOpen, setGroupOpen] = useState(false);
  const [editBooking, setEditBooking] = useState(null);
  const [rescheduleBooking, setRescheduleBooking] = useState(null);
  const [approveBooking, setApproveBooking] = useState(null);
  const [payBooking, setPayBooking] = useState(null);
  const [cancelBooking, setCancelBooking] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [srcFilter, setSrcFilter] = useState("all"); // all | online | manual
  const rows = Array.isArray(data) ? data : [];
  const canManage = user && (user.role === "owner" || user.role === "ops_admin");
  // Pesanan website yang menunggu keputusan → panel inbox di atas (bukan baris tabel biasa).
  const onlinePending = canManage ? rows.filter((r) => r.status === "pending" && r.source === "web_booking") : [];
  const tableRows = rows
    .filter((r) => !(canManage && r.status === "pending" && r.source === "web_booking"))
    .filter((r) => srcFilter === "all" ? true
      : srcFilter === "online" ? r.source === "web_booking" : r.source !== "web_booking");

  const ACTION_MSG = { cancel: "Booking dibatalkan", complete: "Booking diselesaikan", reject: "Permintaan booking ditolak" };
  const act = async (id, action) => {
    setBusyId(id);
    try {
      await apiClient.post(`/bookings/${id}/${action}`);
      toast.success(ACTION_MSG[action] || "Aksi berhasil");
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Aksi gagal");
    } finally {
      setBusyId(null);
    }
  };

  const sendInvoiceWa = async (id) => {
    setBusyId(id);
    try {
      const r = await apiClient.post(`/bookings/${id}/send-invoice-wa`);
      toast.success(`Invoice ${r.data?.number || ""} terkirim via WhatsApp`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengirim invoice via WhatsApp");
    } finally { setBusyId(null); }
  };

  // Mode "ACC ops dulu": permintaan dari web disetujui lalu unit DITAHAN + DP diminta
  // (bukan langsung confirmed) — pelanggan bayar dulu, baru pesanan berlaku.
  const approveHold = async (r) => {
    if (!r.vehicle_id && !window.confirm(
      `Permintaan ${r.code} belum punya armada. Gunakan tombol "Setujui" untuk memilih armada dulu.`)) return;
    if (!r.vehicle_id) return;
    setBusyId(r.id);
    try {
      const { data } = await apiClient.post(`/bookings/${r.id}/approve-hold`, { vehicle_id: r.vehicle_id });
      toast.success(`Unit ditahan — DP ${formatCurrency(data?.dp_amount)} diminta ke pelanggan`);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menahan unit");
    } finally { setBusyId(null); }
  };

  const canPay = (r) => !["cancelled", "pending"].includes(r.status) && !["lunas", "selesai"].includes(r.payment_status);

  const columns = [
    { key: "code", label: "Kode", mono: true, render: (r) => (
      <div className="flex items-center gap-1.5">
        <span className="font-semibold text-[#1C1C1E]">{r.code}</span>
        {r.group_id ? (
          <span className="status-pill tone-info !py-0 !px-1.5 !text-[10px]" title={`Grup ${r.group_index}/${r.group_size}`}>
            <Users size={9} /> Grup {r.group_index}/{r.group_size}
          </span>
        ) : null}
      </div>
    ) },
    { key: "customer_name", label: "Customer", render: (r) => (
      <div className="min-w-0">
        <span className="block truncate text-[#1C1C1E]" title={r.customer_name}>{r.customer_name}</span>
        {/* Sumber pesanan menentukan SOP: pesanan online menunggu DP & bisa hangus sendiri,
            pesanan buatan ops tidak. Label WAJIB di kedua sisi agar tak ada ambiguitas. */}
        {r.source === "web_booking" ? (
          <span className="mt-0.5 inline-block rounded-full bg-[#EAF2FF] px-1.5 py-0.5 text-[10px] font-semibold text-[#0058CC]">Online</span>
        ) : (
          <span className="mt-0.5 inline-block rounded-full bg-[#F1F1F4] px-1.5 py-0.5 text-[10px] font-semibold text-[#6B6B73]">Manual</span>
        )}
      </div>
    ) },
    { key: "vehicle_name", label: "Armada & sopir", render: (r) => (
      <div className="min-w-0">
        <span className="block truncate text-[#1C1C1E]">{r.vehicle_name || "—"}</span>
        {/* Sopir wajib terlihat di daftar: "belum ada sopir" adalah temuan operasional
            paling sering dan sebelumnya hanya bisa dilihat dengan membuka detail satu-satu. */}
        <span className={`block text-[11px] ${r.driver_name ? "text-[#8E8E93]" : "text-[#A8221A]"}`}>
          {r.driver_name || "Belum ada sopir"}
        </span>
      </div>
    ) },
    { key: "trip", label: "Perjalanan", render: (r) => (
      <div className="min-w-0">
        {/* Pesanan online sewa harian tidak mengisi asal/tujuan (tamu hanya memberi titik
            jemput), jadi jatuhkan ke `pickup_address` daripada menampilkan "—" yang menyesatkan. */}
        <span className="block truncate text-[#1F1F25]"
          title={r.route_name || (r.origin || r.destination ? `${r.origin || "-"} → ${r.destination || "-"}` : r.pickup_address || "")}>
          {r.route_name
            || (r.origin || r.destination ? `${r.origin || "-"} → ${r.destination || "-"}` : (r.pickup_address || "—"))}
        </span>
        <span className="block text-[11px] text-[#8E8E93]">
          {r.pax ? `${r.pax} pax` : ""}{r.service_label ? `${r.pax ? " · " : ""}${r.service_label}` : ""}
        </span>
      </div>
    ) },
    { key: "start_datetime", label: "Mulai", render: (r) => (
      <div>
        <span className="block">{formatDateTime(r.start_datetime)}</span>
        {r.end_datetime ? (
          <span className="block text-[11px] text-[#8E8E93]">s/d {formatDateTime(r.end_datetime)}</span>
        ) : null}
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
    { key: "payment_status", label: "Pembayaran", render: (r) => <PaymentPill value={r.payment_status} /> },
    { key: "status", label: "Status", render: (r) => <StatusPill value={r.status} tone={STATUS_TONE[r.status] || "neutral"} /> },
  ];
  if (canManage) {
    columns.push({
      key: "aksi", label: "Aksi", align: "right",
      render: (r) => {
        if (r.status === "pending") {
          return (
            <div className="flex justify-end gap-1.5">
              {r.source === "web_booking" ? (
                <button className="secondary-button !px-2 !py-1 !text-[12px] !text-[#0A5BD3]" disabled={busyId === r.id}
                  onClick={() => approveHold(r)} data-testid={`booking-approve-hold-${r.id}`}
                  title="Setujui & tahan unit, lalu minta DP ke pelanggan">
                  <Clock size={13} /> ACC + Minta DP
                </button>
              ) : null}
              <button className="secondary-button !px-2 !py-1 !text-[12px] !text-[#126E2C]" disabled={busyId === r.id} onClick={() => setApproveBooking(r)} data-testid={`booking-approve-${r.id}`}><ShieldCheck size={13} /> Setujui</button>
              <button className="secondary-button !px-2 !py-1 !text-[12px] !text-[#A8221A]" disabled={busyId === r.id} onClick={() => act(r.id, "reject")} data-testid={`booking-reject-${r.id}`}>Tolak</button>
            </div>
          );
        }
        return (
          <div className="flex justify-end gap-1.5">
            {["confirmed", "ongoing", "completed"].includes(r.status) ? (
              <button className="icon-button !h-8 !w-8 !text-[#127A36]" title="Kirim invoice via WhatsApp" disabled={busyId === r.id} onClick={() => sendInvoiceWa(r.id)} data-testid={`booking-invoice-wa-${r.id}`}><MessageCircle size={13} /></button>
            ) : null}
            {canPay(r) ? (
              <button className="secondary-button !px-2 !py-1 !text-[12px]" onClick={() => setPayBooking(r)} data-testid={`booking-pay-${r.id}`}><Wallet size={13} /> Bayar</button>
            ) : null}
            {ACTIVE.includes(r.status) ? (
              <>
                <button className="icon-button !h-8 !w-8" title="Edit" onClick={() => setEditBooking(r)} data-testid={`booking-edit-${r.id}`}><Pencil size={13} /></button>
                <button className="icon-button !h-8 !w-8" title="Jadwal ulang" onClick={() => setRescheduleBooking(r)} data-testid={`booking-reschedule-${r.id}`}><CalendarClock size={13} /></button>
                <button className="secondary-button !px-2 !py-1 !text-[12px]" disabled={busyId === r.id} onClick={() => act(r.id, "complete")} data-testid={`booking-complete-${r.id}`}>Selesai</button>
                <button className="secondary-button !px-2 !py-1 !text-[12px] !text-[#A8221A]" disabled={busyId === r.id} onClick={() => setCancelBooking(r)} data-testid={`booking-cancel-${r.id}`}>Batal</button>
              </>
            ) : !canPay(r) ? <span className="text-[12px] text-[#B0B1B8]">—</span> : null}
          </div>
        );
      },
    });
  }

  const createBtn = canManage ? (
    <div className="flex gap-2">
      <button className="secondary-button" onClick={() => setGroupOpen(true)} data-testid="booking-group-open"><Users size={14} /> Buat Rombongan</button>
      <button className="primary-button" onClick={() => setCreateOpen(true)} data-testid="booking-create-open"><Plus size={14} /> Buat Booking</button>
    </div>
  ) : null;

  const filterChips = (
    <div className="flex items-center gap-1.5" data-testid="booking-source-filter">
      {[["all", "Semua"], ["online", "Online"], ["manual", "Manual"]].map(([k, l]) => (
        <button key={k} onClick={() => setSrcFilter(k)}
          className={`rounded-full border px-3 py-1 text-[12px] font-semibold transition-colors ${srcFilter === k ? "border-[#007AFF] bg-[#EAF2FF] text-[#0058CC]" : "border-[#E2E3E7] bg-white text-[#6B6B73] hover:border-[#B9D5FF]"}`}
          data-testid={`booking-filter-${k}`}>{l}</button>
      ))}
    </div>
  );

  return (
    <div className="space-y-4" data-testid="bookings-page">
      {canManage ? (
        <OnlineOrdersPanel rows={onlinePending} busyId={busyId}
          onApproveHold={approveHold} onApprove={(r) => setApproveBooking(r)} onReject={(r) => act(r.id, "reject")} />
      ) : null}
      {canManage ? <PaymentProofsPanel onChanged={reload} /> : null}
      {loading ? (
        <LoadingState testId="bookings-loading" />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : rows.length === 0 ? (
        <div className="space-y-3">
          <div className="flex justify-end">{createBtn}</div>
          <EmptyState title="Belum ada booking" description="Pemesanan akan muncul di sini setelah dibuat." testId="bookings-empty" action={createBtn} />
        </div>
      ) : tableRows.length === 0 ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between">{filterChips}{createBtn}</div>
          <EmptyState title="Tidak ada booking pada filter ini" description="Ubah filter sumber (Semua / Online / Manual) untuk melihat booking lain." testId="bookings-filter-empty" />
        </div>
      ) : (
        <DataTable title="Booking & Trip" icon={CalendarRange} columns={columns} rows={tableRows}
          actions={<div className="flex items-center gap-3">{filterChips}{createBtn}</div>}
          footer={`${formatQty(tableRows.length)} booking`} testId="bookings-table" />
      )}
      <BookingFormDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={reload} />
      <GroupBookingDialog open={groupOpen} onOpenChange={setGroupOpen} onCreated={reload} />
      <BookingEditDialog open={Boolean(editBooking)} onOpenChange={(v) => !v && setEditBooking(null)} booking={editBooking} onSaved={reload} />
      <BookingRescheduleDialog open={Boolean(rescheduleBooking)} onOpenChange={(v) => !v && setRescheduleBooking(null)} booking={rescheduleBooking} onSaved={reload} />
      <BookingApproveDialog open={Boolean(approveBooking)} onOpenChange={(v) => !v && setApproveBooking(null)} booking={approveBooking} onSaved={reload} />
      <CancelBookingDialog open={Boolean(cancelBooking)} onOpenChange={(v) => !v && setCancelBooking(null)} booking={cancelBooking} onSaved={reload} />
      <PaymentDialog open={Boolean(payBooking)} onOpenChange={(v) => !v && setPayBooking(null)} booking={payBooking} onSaved={reload} />
    </div>
  );
}
