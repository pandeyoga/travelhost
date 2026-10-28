import { useState } from "react";
import { CalendarRange, Plus, Users } from "lucide-react";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/context/AuthContext";
import apiClient from "@/services/apiClient";
import { toast } from "sonner";
import DataTable from "@/components/shared/DataTable";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import BookingFormDialog from "@/components/app/BookingFormDialog";
import OnlineOrdersPanel from "@/components/app/OnlineOrdersPanel";
import BookingEditDialog from "@/components/app/BookingEditDialog";
import BookingRescheduleDialog from "@/components/app/BookingRescheduleDialog";
import BookingApproveDialog from "@/components/app/BookingApproveDialog";
import GroupBookingDialog from "@/components/app/GroupBookingDialog";
import CancelBookingDialog from "@/components/app/CancelBookingDialog";
import CompleteBookingDialog from "@/components/app/CompleteBookingDialog";
import RejectBookingDialog from "@/components/app/RejectBookingDialog";
import PaymentDialog from "@/components/app/PaymentDialog";
import PaymentProofsPanel from "@/components/app/PaymentProofsPanel";
import { BookingCard, BookingRowActions, buildBookingColumns, hasRowActions } from "@/components/app/bookings/BookingListParts";
import { isWebSource } from "@/lib/bookingRules";
import { formatQty } from "@/utils/formatters";

export default function Bookings() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useResource("/bookings");
  const [createOpen, setCreateOpen] = useState(false);
  const [groupOpen, setGroupOpen] = useState(false);
  const [editBooking, setEditBooking] = useState(null);
  const [rescheduleBooking, setRescheduleBooking] = useState(null);
  const [approve, setApprove] = useState(null); // { booking, mode: "confirm" | "hold" }
  const [payBooking, setPayBooking] = useState(null);
  const [cancelBooking, setCancelBooking] = useState(null);
  const [completeBooking, setCompleteBooking] = useState(null);
  const [rejectBooking, setRejectBooking] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [srcFilter, setSrcFilter] = useState("all"); // all | online | manual
  const rows = Array.isArray(data) ? data : [];
  const canManage = user && (user.role === "owner" || user.role === "ops_admin");
  // Pesanan website (wizard + permintaan khusus) yang menunggu keputusan → panel inbox di atas
  // (bukan baris tabel biasa).
  const isOnlinePending = (r) => r.status === "pending" && isWebSource(r.source);
  const onlinePending = canManage ? rows.filter(isOnlinePending) : [];
  const tableRows = rows
    .filter((r) => !(canManage && isOnlinePending(r)))
    .filter((r) => srcFilter === "all" ? true
      : srcFilter === "online" ? isWebSource(r.source) : !isWebSource(r.source));

  const sendInvoiceWa = async (r) => {
    setBusyId(r.id);
    try {
      const res = await apiClient.post(`/bookings/${r.id}/send-invoice-wa`);
      toast.success(`Invoice ${res.data?.number || ""} terkirim via WhatsApp`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengirim invoice via WhatsApp");
    } finally { setBusyId(null); }
  };

  const handlers = {
    approve: (r, mode) => setApprove({ booking: r, mode }),
    reject: setRejectBooking,
    pay: setPayBooking,
    edit: setEditBooking,
    reschedule: setRescheduleBooking,
    complete: setCompleteBooking,
    cancel: setCancelBooking,
    invoiceWa: sendInvoiceWa,
  };
  const renderActions = (r, compact) => (
    <BookingRowActions row={r} busyId={busyId} on={handlers} compact={compact} testPrefix={compact ? "booking" : "booking-m"} />
  );
  const columns = buildBookingColumns({ canManage, renderActions });

  // Header membungkus (flex-wrap) — di layar 390px tombol "Buat Booking" dulu terdorong ke x=395.
  const createBtn = canManage ? (
    <div className="flex flex-wrap gap-2">
      <button className="secondary-button" onClick={() => setGroupOpen(true)} data-testid="booking-group-open"><Users size={14} /> Buat Rombongan</button>
      <button className="primary-button" onClick={() => setCreateOpen(true)} data-testid="booking-create-open"><Plus size={14} /> Buat Booking</button>
    </div>
  ) : null;

  const filterChips = (
    <div className="flex flex-wrap items-center gap-1.5" data-testid="booking-source-filter">
      {[["all", "Semua"], ["online", "Online"], ["manual", "Manual"]].map(([k, l]) => (
        <button key={k} onClick={() => setSrcFilter(k)}
          className={`rounded-full border px-3 py-1 text-[12px] font-semibold transition-colors ${srcFilter === k ? "border-[#007AFF] bg-[#EAF2FF] text-[#0058CC]" : "border-[#E2E3E7] bg-white text-[#6B6B73] hover:border-[#B9D5FF]"}`}
          data-testid={`booking-filter-${k}`}>{l}</button>
      ))}
    </div>
  );
  const toolbar = <div className="flex flex-wrap items-center gap-2 sm:gap-3">{filterChips}{createBtn}</div>;

  return (
    <div className="space-y-4" data-testid="bookings-page">
      {canManage ? (
        <OnlineOrdersPanel rows={onlinePending} busyId={busyId}
          onApprove={handlers.approve} onReject={setRejectBooking} />
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
          <div className="flex flex-wrap items-center justify-between gap-2">{filterChips}{createBtn}</div>
          <EmptyState title="Tidak ada booking pada filter ini" description="Ubah filter sumber (Semua / Online / Manual) untuk melihat booking lain." testId="bookings-filter-empty" />
        </div>
      ) : (
        <DataTable title="Booking & Trip" icon={CalendarRange} columns={columns} rows={tableRows}
          headClassName="flex-wrap" actions={toolbar} cardBreakpoint="wide"
          renderCard={(r) => <BookingCard row={r} actions={canManage && hasRowActions(r) ? renderActions(r, false) : null} />}
          footer={`${formatQty(tableRows.length)} booking`} testId="bookings-table" />
      )}
      <BookingFormDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={reload} />
      <GroupBookingDialog open={groupOpen} onOpenChange={setGroupOpen} onCreated={reload} />
      <BookingEditDialog open={Boolean(editBooking)} onOpenChange={(v) => !v && setEditBooking(null)} booking={editBooking} onSaved={reload} />
      <BookingRescheduleDialog open={Boolean(rescheduleBooking)} onOpenChange={(v) => !v && setRescheduleBooking(null)} booking={rescheduleBooking} onSaved={reload} />
      <BookingApproveDialog open={Boolean(approve)} onOpenChange={(v) => !v && setApprove(null)} booking={approve?.booking} mode={approve?.mode} onSaved={reload} />
      <RejectBookingDialog open={Boolean(rejectBooking)} onOpenChange={(v) => !v && setRejectBooking(null)} booking={rejectBooking} onSaved={reload} />
      <CompleteBookingDialog open={Boolean(completeBooking)} onOpenChange={(v) => !v && setCompleteBooking(null)} booking={completeBooking} onSaved={reload} />
      <CancelBookingDialog open={Boolean(cancelBooking)} onOpenChange={(v) => !v && setCancelBooking(null)} booking={cancelBooking} onSaved={reload} />
      <PaymentDialog open={Boolean(payBooking)} onOpenChange={(v) => !v && setPayBooking(null)} booking={payBooking} onSaved={reload} />
    </div>
  );
}
