import { useCallback, useEffect, useState } from "react";
import { Wallet, Loader2, Banknote, History } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { formatCurrency, formatDateTime } from "@/utils/formatters";

const WD_STATUS = {
  requested: ["Diajukan", "warning"],
  paid: ["Dicairkan", "success"],
  rejected: ["Ditolak", "danger"],
};

// DriverFeeCard — saldo fee driver (per keberangkatan) + pengajuan pencairan.
// Saldo = fee trip selesai − dicairkan − sedang diajukan. Pembayaran diproses finance
// (wajib bukti transfer) di menu Keuangan → Fee Driver.
export default function DriverFeeCard({ driverId = "", isManager = false }) {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ amount: "", bank_name: "", account_number: "", account_name: "", note: "" });
  const [saving, setSaving] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const qs = driverId ? `?driver_id=${encodeURIComponent(driverId)}` : "";

  const load = useCallback(async () => {
    try {
      const r = await apiClient.get(`/driver/fees${qs}`);
      setData(r.data);
    } catch {
      setData(null);
    }
  }, [qs]);

  useEffect(() => { load(); }, [load]);

  if (!data || data.is_driver === false) return null;

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const submit = async () => {
    const amount = Number(form.amount);
    if (!(amount > 0)) { toast.error("Nominal pencairan harus lebih dari 0"); return; }
    if (amount > Number(data.available || 0)) { toast.error(`Maksimal ${formatCurrency(data.available)}`); return; }
    if (!form.bank_name.trim() || !form.account_number.trim() || !form.account_name.trim()) {
      toast.error("Lengkapi bank, nomor rekening & nama pemilik rekening"); return;
    }
    setSaving(true);
    try {
      await apiClient.post("/driver/fees/withdraw", {
        amount, bank_name: form.bank_name.trim(), account_number: form.account_number.trim(),
        account_name: form.account_name.trim(), note: form.note || "",
        ...(isManager && driverId ? { driver_id: driverId } : {}),
      });
      toast.success("Pengajuan pencairan terkirim — menunggu pembayaran finance");
      setOpen(false);
      setForm({ amount: "", bank_name: "", account_number: "", account_name: "", note: "" });
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengajukan pencairan");
    } finally { setSaving(false); }
  };

  const wds = data.withdrawals || [];
  const entries = data.entries || [];

  return (
    <section className="rounded-[14px] border border-[#D9F0E1] bg-gradient-to-br from-[#F3FBF5] to-[#EAF7EE] p-4" data-testid="driver-fee-card">
      <div className="flex flex-wrap items-center gap-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#1B7F3B] text-white"><Wallet size={16} /></span>
        <div>
          <p className="text-[11.5px] font-semibold uppercase tracking-wide text-[#4C7C5C]">Saldo Fee Bisa Dicairkan</p>
          <p className="text-[22px] font-bold tabular-nums text-[#0F5227]" style={{ fontFamily: "Outfit, sans-serif" }} data-testid="fee-available">
            {formatCurrency(data.available)}
          </p>
        </div>
        <div className="ml-auto flex flex-col items-end gap-1 text-[11.5px] text-[#4C7C5C]">
          <span>Total fee: <b className="tabular-nums" data-testid="fee-earned">{formatCurrency(data.earned_total)}</b></span>
          <span>Dicairkan: <b className="tabular-nums">{formatCurrency(data.paid_total)}</b>{Number(data.requested_total) > 0 ? <> · Diajukan: <b className="tabular-nums">{formatCurrency(data.requested_total)}</b></> : null}</span>
        </div>
        <button className="primary-button !bg-[#1B7F3B]" disabled={Number(data.available) <= 0}
          onClick={() => setOpen(true)} data-testid="fee-withdraw-open">
          <Banknote size={14} /> Cairkan Fee
        </button>
      </div>

      <button className="mt-3 flex items-center gap-1.5 text-[12px] font-semibold text-[#0F5227]" onClick={() => setShowHistory((s) => !s)} data-testid="fee-history-toggle">
        <History size={13} /> Riwayat fee & pencairan {showHistory ? "▾" : "▸"}
      </button>
      {showHistory ? (
        <div className="mt-2 grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div data-testid="fee-entries">
            <p className="mb-1 text-[11.5px] font-semibold text-[#4C7C5C]">Fee per keberangkatan</p>
            {entries.length === 0 ? (
              <p className="rounded-[10px] border border-dashed border-[#CBE7D4] px-3 py-2 text-[11.5px] text-[#6B8F79]" data-testid="fee-entries-empty">Belum ada fee — fee masuk otomatis saat trip selesai.</p>
            ) : entries.slice(0, 6).map((e) => (
              <div key={e.id} className="flex items-center justify-between rounded-[10px] bg-white/70 px-2.5 py-1.5 text-[12px]" data-testid={`fee-entry-${e.id}`}>
                <span className="font-semibold text-[#1C1C1E]">{e.booking_code || e.trip_id}</span>
                <span className="text-[#6B6B73]">{formatCurrency(e.rate)}/hr × {e.days}</span>
                <span className="font-semibold tabular-nums text-[#0F5227]">{formatCurrency(e.amount)}</span>
              </div>
            ))}
          </div>
          <div data-testid="fee-withdrawals">
            <p className="mb-1 text-[11.5px] font-semibold text-[#4C7C5C]">Pencairan</p>
            {wds.length === 0 ? (
              <p className="rounded-[10px] border border-dashed border-[#CBE7D4] px-3 py-2 text-[11.5px] text-[#6B8F79]" data-testid="fee-withdrawals-empty">Belum ada pengajuan pencairan.</p>
            ) : wds.slice(0, 6).map((w) => {
              const st = WD_STATUS[w.status] || [w.status, "neutral"];
              return (
                <div key={w.id} className="flex items-center justify-between gap-2 rounded-[10px] bg-white/70 px-2.5 py-1.5 text-[12px]" data-testid={`fee-wd-${w.id}`}>
                  <span className="tabular-nums font-semibold text-[#1C1C1E]">{formatCurrency(w.amount)}</span>
                  <span className="text-[11px] text-[#8E8E93]">{formatDateTime(w.created_at)}</span>
                  <span className={`status-pill tone-${st[1]} !text-[10.5px]`}>{st[0]}</span>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md" data-testid="fee-withdraw-dialog">
          <DialogHeader>
            <DialogTitle>Cairkan Fee Driver</DialogTitle>
            <DialogDescription>
              Saldo tersedia {formatCurrency(data.available)}. Dana ditransfer finance ke rekening di bawah (dengan bukti transfer).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2.5">
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Nominal (Rp)</label>
              <Input type="number" value={form.amount} onChange={(e) => set("amount", e.target.value)} placeholder={String(data.available)} data-testid="fee-wd-amount" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Bank</label>
                <Input value={form.bank_name} onChange={(e) => set("bank_name", e.target.value)} placeholder="BCA" data-testid="fee-wd-bank" />
              </div>
              <div>
                <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">No. Rekening</label>
                <Input value={form.account_number} onChange={(e) => set("account_number", e.target.value)} placeholder="1234567890" data-testid="fee-wd-account" />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Nama Pemilik Rekening</label>
              <Input value={form.account_name} onChange={(e) => set("account_name", e.target.value)} placeholder="Sesuai buku tabungan" data-testid="fee-wd-name" />
            </div>
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Catatan (opsional)</label>
              <Input value={form.note} onChange={(e) => set("note", e.target.value)} placeholder="—" data-testid="fee-wd-note" />
            </div>
          </div>
          <DialogFooter className="mt-2">
            <button className="secondary-button" onClick={() => setOpen(false)} data-testid="fee-wd-cancel">Batal</button>
            <button className="primary-button !bg-[#1B7F3B]" disabled={saving} onClick={submit} data-testid="fee-wd-submit">
              {saving ? <Loader2 size={14} className="animate-spin" /> : null} Ajukan Pencairan
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
