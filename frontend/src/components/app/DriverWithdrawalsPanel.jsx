import { useCallback, useEffect, useState } from "react";
import { Banknote, Loader2, Wallet, FileCheck2, XCircle, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { formatCurrency, formatDateTime } from "@/utils/formatters";

const WD_STATUS = { requested: ["Diajukan", "warning"], paid: ["Dicairkan", "success"], rejected: ["Ditolak", "danger"] };
const th = "px-3 py-2.5 text-left text-[11px] uppercase tracking-wide text-[#8E8E93]";
const td = "px-3 py-2.5 text-[12.5px]";

// DriverWithdrawalsPanel — sisi FINANCE: saldo fee per driver + proses pencairan.
// Bayar WAJIB unggah bukti transfer → otomatis tercatat sebagai expense gaji_driver (paid).
export default function DriverWithdrawalsPanel() {
  const [balances, setBalances] = useState([]);
  const [wds, setWds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [payTarget, setPayTarget] = useState(null);
  const [rejectTarget, setRejectTarget] = useState(null);
  const [proofFile, setProofFile] = useState(null);
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [b, w] = await Promise.all([
        apiClient.get("/payroll/fee-balances"),
        apiClient.get("/payroll/withdrawals"),
      ]);
      setBalances(Array.isArray(b.data) ? b.data : []);
      setWds(Array.isArray(w.data) ? w.data : []);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat data fee driver");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const doPay = async () => {
    if (!proofFile) { toast.error("Bukti transfer WAJIB diunggah sebelum menandai dicairkan"); return; }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("proof", proofFile);
      fd.append("note", note || "");
      await apiClient.post(`/payroll/withdrawals/${payTarget.id}/pay`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`Pencairan ${formatCurrency(payTarget.amount)} untuk ${payTarget.driver_name} tercatat (expense gaji_driver)`);
      setPayTarget(null); setProofFile(null); setNote("");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memproses pembayaran");
    } finally { setBusy(false); }
  };

  const doReject = async () => {
    if (!reason.trim()) { toast.error("Alasan penolakan wajib diisi"); return; }
    setBusy(true);
    try {
      await apiClient.post(`/payroll/withdrawals/${rejectTarget.id}/reject`, { reason: reason.trim() });
      toast.success("Pengajuan ditolak — saldo driver kembali tersedia");
      setRejectTarget(null); setReason("");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menolak pengajuan");
    } finally { setBusy(false); }
  };

  if (loading) return <LoadingState testId="fees-panel-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const requested = wds.filter((w) => w.status === "requested");

  return (
    <div className="space-y-4" data-testid="driver-withdrawals-panel">
      {/* Saldo per driver */}
      <section className="section-card">
        <div className="flex items-center gap-2 border-b border-[#EFF0F2] px-4 py-3">
          <Wallet size={15} className="text-[#1B7F3B]" />
          <h3 className="text-[13.5px] font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>Saldo Fee per Driver</h3>
          <span className="ml-auto text-[11.5px] text-[#8E8E93]">Fee /hari ditetapkan saat assign dispatch · masuk saldo saat trip selesai</span>
        </div>
        {balances.length === 0 ? (
          <EmptyState title="Belum ada fee driver" description="Isi 'Fee Driver /hari' saat assign di menu Dispatch — fee masuk saldo otomatis saat trip selesai." testId="fee-balances-empty" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead><tr className="border-b border-[#EFF0F2]">
                <th className={th}>Driver</th><th className={`${th} text-right`}>Total Fee</th>
                <th className={`${th} text-right`}>Dicairkan</th><th className={`${th} text-right`}>Diajukan</th>
                <th className={`${th} text-right`}>Saldo Tersedia</th></tr></thead>
              <tbody data-testid="fee-balances-table">
                {balances.map((b) => (
                  <tr key={b.driver_id} className="border-b border-[#F6F6F8]" data-testid={`fee-balance-${b.driver_id}`}>
                    <td className={`${td} font-semibold text-[#1C1C1E]`}>{b.driver_name}</td>
                    <td className={`${td} text-right tabular-nums`}>{formatCurrency(b.earned_total)}</td>
                    <td className={`${td} text-right tabular-nums text-[#6B6B73]`}>{formatCurrency(b.paid_total)}</td>
                    <td className={`${td} text-right tabular-nums text-[#B8860B]`}>{formatCurrency(b.requested_total)}</td>
                    <td className={`${td} text-right tabular-nums font-bold text-[#0F5227]`}>{formatCurrency(b.available)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Pengajuan pencairan */}
      <section className="section-card">
        <div className="flex items-center gap-2 border-b border-[#EFF0F2] px-4 py-3">
          <Banknote size={15} className="text-[#007AFF]" />
          <h3 className="text-[13.5px] font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>Pencairan Fee</h3>
          {requested.length > 0 ? <span className="rounded-full bg-[#FFF2D9] px-2 py-0.5 text-[11px] font-bold text-[#8C5A00]" data-testid="wd-pending-count">{requested.length} menunggu</span> : null}
        </div>
        {wds.length === 0 ? (
          <EmptyState title="Belum ada pengajuan pencairan" description="Driver mengajukan pencairan dari Ruang Kerja Driver; prosesnya muncul di sini." testId="wd-empty" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead><tr className="border-b border-[#EFF0F2]">
                <th className={th}>Driver</th><th className={`${th} text-right`}>Nominal</th>
                <th className={th}>Rekening Tujuan</th><th className={th}>Diajukan</th>
                <th className={th}>Status</th><th className={`${th} text-right`}>Aksi</th></tr></thead>
              <tbody data-testid="wd-table">
                {wds.map((w) => {
                  const st = WD_STATUS[w.status] || [w.status, "neutral"];
                  return (
                    <tr key={w.id} className="border-b border-[#F6F6F8] align-top" data-testid={`wd-row-${w.id}`}>
                      <td className={`${td} font-semibold text-[#1C1C1E]`}>{w.driver_name}{w.note ? <span className="block text-[11px] font-normal text-[#8E8E93]">{w.note}</span> : null}</td>
                      <td className={`${td} text-right tabular-nums font-semibold`}>{formatCurrency(w.amount)}</td>
                      <td className={td}><span className="block">{w.bank_name} · {w.account_number}</span><span className="block text-[11px] text-[#8E8E93]">a.n. {w.account_name}</span></td>
                      <td className={`${td} tabular-nums text-[#6B6B73]`}>{formatDateTime(w.created_at)}</td>
                      <td className={td}>
                        <span className={`status-pill tone-${st[1]}`}>{st[0]}</span>
                        {w.status === "paid" && w.proof_url ? (
                          <a className="mt-1 flex items-center gap-1 text-[11.5px] font-semibold text-[#007AFF] hover:underline" href={w.proof_url} target="_blank" rel="noreferrer" data-testid={`wd-proof-${w.id}`}>
                            <ExternalLink size={11} /> Bukti transfer
                          </a>
                        ) : null}
                        {w.status === "rejected" && w.reject_reason ? <span className="mt-1 block text-[11px] text-[#A8221A]">{w.reject_reason}</span> : null}
                      </td>
                      <td className={`${td} text-right`}>
                        {w.status === "requested" ? (
                          <div className="flex justify-end gap-1.5">
                            <button className="primary-button !h-8 !px-2.5 !text-[12px] !bg-[#1B7F3B]" onClick={() => setPayTarget(w)} data-testid={`wd-pay-${w.id}`}><FileCheck2 size={13} /> Bayar</button>
                            <button className="secondary-button !h-8 !px-2.5 !text-[12px] !text-[#A8221A]" onClick={() => setRejectTarget(w)} data-testid={`wd-reject-${w.id}`}><XCircle size={13} /> Tolak</button>
                          </div>
                        ) : <span className="text-[12px] text-[#B0B1B8]">—</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Dialog bayar (bukti transfer WAJIB) */}
      <Dialog open={Boolean(payTarget)} onOpenChange={(v) => { if (!v) { setPayTarget(null); setProofFile(null); setNote(""); } }}>
        <DialogContent className="sm:max-w-md" data-testid="wd-pay-dialog">
          <DialogHeader>
            <DialogTitle>Bayar Pencairan Fee</DialogTitle>
            <DialogDescription>
              {payTarget ? `${payTarget.driver_name} · ${formatCurrency(payTarget.amount)} → ${payTarget.bank_name} ${payTarget.account_number} a.n. ${payTarget.account_name}` : ""}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2.5">
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Bukti Transfer (wajib — foto/screenshot JPG/PNG/WebP)</label>
              <input type="file" accept="image/jpeg,image/png,image/webp"
                onChange={(e) => setProofFile(e.target.files?.[0] || null)}
                className="block w-full text-[12.5px] file:mr-3 file:rounded-md file:border-0 file:bg-[#EAF2FF] file:px-3 file:py-1.5 file:text-[12px] file:font-semibold file:text-[#0058CC]"
                data-testid="wd-proof-input" />
            </div>
            <div>
              <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Catatan (opsional)</label>
              <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="No. referensi transfer, dll." data-testid="wd-pay-note" />
            </div>
            <p className="rounded-lg bg-[#F3FBF5] px-3 py-2 text-[11.5px] text-[#0F5227]">
            Setelah dibayar: saldo driver berkurang & otomatis tercatat sebagai pengeluaran kategori <b>Gaji/Komisi Driver</b> (lunas) di P&L.
            </p>
          </div>
          <DialogFooter className="mt-2">
            <button className="secondary-button" onClick={() => setPayTarget(null)} data-testid="wd-pay-cancel">Batal</button>
            <button className="primary-button !bg-[#1B7F3B]" disabled={busy || !proofFile} onClick={doPay} data-testid="wd-pay-confirm">
              {busy ? <Loader2 size={14} className="animate-spin" /> : null} Tandai Dicairkan
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog tolak */}
      <Dialog open={Boolean(rejectTarget)} onOpenChange={(v) => { if (!v) { setRejectTarget(null); setReason(""); } }}>
        <DialogContent className="sm:max-w-md" data-testid="wd-reject-dialog">
          <DialogHeader>
            <DialogTitle>Tolak Pengajuan Pencairan</DialogTitle>
            <DialogDescription>
              {rejectTarget ? `${rejectTarget.driver_name} · ${formatCurrency(rejectTarget.amount)} — saldo akan kembali tersedia.` : ""}
            </DialogDescription>
          </DialogHeader>
          <div>
            <label className="mb-1 block text-[12px] font-semibold text-[#6B6B73]">Alasan penolakan (wajib, terlihat oleh driver)</label>
            <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="mis. Nomor rekening tidak valid" data-testid="wd-reject-reason" />
          </div>
          <DialogFooter className="mt-2">
            <button className="secondary-button" onClick={() => setRejectTarget(null)} data-testid="wd-reject-cancel">Batal</button>
            <button className="primary-button !bg-[#A8221A]" disabled={busy} onClick={doReject} data-testid="wd-reject-confirm">
              {busy ? <Loader2 size={14} className="animate-spin" /> : null} Tolak Pengajuan
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
