import { useEffect, useMemo, useRef, useState } from "react";
import { Upload, Loader2, Copy, Check, Clock, Landmark, AlertTriangle, Image as ImageIcon } from "lucide-react";
import { toast } from "sonner";
import { formatCurrency, formatDateTime } from "@/utils/formatters";
import { uploadPaymentProof } from "@/services/bookingApi";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

// PaymentInstructions — panel pembayaran DP pada halaman status pesanan.
//
// Pembayaran = TRANSFER MANUAL + UNGGAH BUKTI (tanpa payment gateway). Tiga hal yang wajib
// terlihat tanpa disuruh: (1) nominal yang harus dibayar, (2) ke rekening mana, (3) sisa waktu
// sebelum unit dilepas.
function useCountdown(seconds) {
  const [left, setLeft] = useState(Number(seconds) || 0);
  const ref = useRef(null);
  useEffect(() => { setLeft(Number(seconds) || 0); }, [seconds]);
  useEffect(() => {
    if (left <= 0) return undefined;
    ref.current = setInterval(() => setLeft((v) => (v > 0 ? v - 1 : 0)), 1000);
    return () => clearInterval(ref.current);
  }, [left > 0]);
  return left;
}

function pad(n) { return String(n).padStart(2, "0"); }

export function HoldCountdown({ seconds, expiresAt }) {
  const lang = useLangValue();
  const left = useCountdown(seconds);
  if (!expiresAt) return null;
  const h = Math.floor(left / 3600);
  const m = Math.floor((left % 3600) / 60);
  const s = left % 60;
  const urgent = left > 0 && left < 1800;
  return (
    <div data-testid="booking-countdown"
      className={`flex items-center gap-2 rounded-xl border px-4 py-3 ${
        left <= 0 ? "border-border bg-secondary"
          : urgent ? "border-[hsl(var(--destructive))]/40 bg-[hsl(var(--destructive))]/5"
            : "border-border bg-card"}`}>
      <Clock size={16} className={urgent ? "text-[hsl(var(--destructive))]" : "text-primary"} />
      <div>
        <p className="text-[11.5px] uppercase tracking-wide text-muted-foreground">
          {left > 0 ? bi("Batas waktu pembayaran DP", "Deposit payment deadline", lang) : bi("Batas waktu terlewat", "Deadline passed", lang)}
        </p>
        <p className="font-mono text-[15px] font-semibold tabular-nums text-foreground">
          {left > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : formatDateTime(expiresAt)}
        </p>
      </div>
    </div>
  );
}

function BankRow({ acc }) {
  const lang = useLangValue();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(String(acc.number || ""));
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch (e) {
      toast.message(bi("Salin manual: ", "Copy manually: ", lang) + acc.number);
    }
  };
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-border bg-card px-4 py-3"
      data-testid={`booking-bank-${acc.bank || "rek"}`}>
      <div className="min-w-0">
        <p className="text-[12px] uppercase tracking-wide text-muted-foreground">{acc.bank}</p>
        <p className="font-mono text-[15px] font-semibold tabular-nums text-foreground">{acc.number}</p>
        <p className="truncate text-[12px] text-muted-foreground">{bi("a/n", "a/n", lang)} {acc.holder}</p>
      </div>
      <button type="button" onClick={copy} data-testid={`booking-bank-copy-${acc.bank || "rek"}`}
        className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-[12px] font-semibold text-foreground transition hover:-translate-y-0.5">
        {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? bi("Tersalin", "Copied", lang) : bi("Salin", "Copy", lang)}
      </button>
    </div>
  );
}

const PROOF_TONE = {
  pending: { id: "Menunggu verifikasi", en: "Awaiting verification", cls: "bg-secondary text-secondary-foreground" },
  verified: { id: "Terverifikasi", en: "Verified", cls: "bg-primary/10 text-primary" },
  rejected: { id: "Ditolak", en: "Rejected", cls: "bg-[hsl(var(--destructive))]/10 text-[hsl(var(--destructive))]" },
};

export default function PaymentInstructions({ status, code, token, onRefresh }) {
  const lang = useLangValue();
  const [file, setFile] = useState(null);
  const [amount, setAmount] = useState("");
  const [sender, setSender] = useState("");
  const [bank, setBank] = useState("");
  const [busy, setBusy] = useState(false);
  const payment = status?.payment || {};
  const accounts = payment.bank_accounts || [];
  const dpDue = useMemo(() => (
    status?.dp_met ? Math.max((status?.outstanding || 0), 0) : (status?.dp_amount || 0)
  ), [status]);

  useEffect(() => { setAmount(String(dpDue || "")); }, [dpDue]);

  const send = async () => {
    if (!file) { toast.error(bi("Pilih foto bukti transfer dulu", "Choose a transfer proof photo first", lang)); return; }
    setBusy(true);
    try {
      await uploadPaymentProof(code, {
        token, file, amount: Number(amount) || 0, senderName: sender, bank,
        note: "Diunggah dari halaman status pesanan",
      });
      toast.success(bi("Bukti terkirim — tim kami segera memverifikasi", "Proof sent — our team will verify it shortly", lang));
      setFile(null);
      onRefresh?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || bi("Gagal mengunggah bukti", "Failed to upload proof", lang));
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-4" data-testid="booking-payment-panel">
      <div className="rounded-2xl border border-border bg-card p-5">
        <h3 className="flex items-center gap-2 font-fraunces text-xl text-foreground">
          <Landmark size={18} className="text-primary" /> {bi("Pembayaran", "Payment", lang)}
        </h3>
        <div className="mt-3 flex items-center justify-between rounded-xl px-4 py-3.5 text-primary-foreground"
          style={{ background: "var(--gradient-cta)" }}>
          <span className="text-[13px] font-medium opacity-90">
            {status?.dp_met ? bi("Sisa pelunasan", "Remaining balance", lang) : bi(`DP ${status?.dp_percent || 0}% yang harus dibayar`, `${status?.dp_percent || 0}% deposit to pay`, lang)}
          </span>
          <span className="font-mono text-2xl font-semibold tabular-nums" data-testid="booking-amount-due">
            {formatCurrency(dpDue)}
          </span>
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2 text-[12.5px]">
          <div className="rounded-lg border border-border px-3 py-2">
            <p className="text-muted-foreground">{bi("Total pesanan", "Order total", lang)}</p>
            <p className="font-mono font-semibold tabular-nums text-foreground">{formatCurrency(status?.total_amount)}</p>
          </div>
          <div className="rounded-lg border border-border px-3 py-2">
            <p className="text-muted-foreground">{bi("Sudah dibayar", "Paid", lang)}</p>
            <p className="font-mono font-semibold tabular-nums text-foreground">{formatCurrency(status?.paid_amount)}</p>
          </div>
        </div>

        {accounts.length ? (
          <div className="mt-4 space-y-2">{accounts.map((a, i) => <BankRow acc={a} key={i} />)}</div>
        ) : (
          <p className="mt-4 rounded-lg border border-dashed border-border px-4 py-3 text-[12.5px] text-muted-foreground"
            data-testid="booking-bank-empty">
            {bi("Rekening belum dicantumkan. Hubungi kami via WhatsApp untuk instruksi pembayaran.", "No bank account listed yet. Contact us via WhatsApp for payment instructions.", lang)}
          </p>
        )}
        {payment.instructions ? (
          <p className="mt-3 text-[12.5px] leading-relaxed text-muted-foreground">{payment.instructions}</p>
        ) : null}
      </div>

      {status?.can_upload_proof ? (
        <div className="rounded-2xl border border-border bg-card p-5">
          <h4 className="flex items-center gap-2 text-[15px] font-semibold text-foreground">
            <Upload size={16} className="text-primary" /> {bi("Unggah bukti transfer", "Upload transfer proof", lang)}
          </h4>
          <p className="mt-1 text-[12.5px] text-muted-foreground">
            {bi("Foto atau tangkapan layar (jpg/png/webp, maks 5 MB).", "Photo or screenshot (jpg/png/webp, max 5 MB).", lang)}
          </p>
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-border px-3 py-2.5 text-[13px] text-foreground sm:col-span-2">
              <ImageIcon size={15} className="text-muted-foreground" />
              <span className="truncate">{file ? file.name : bi("Pilih berkas bukti transfer…", "Choose transfer proof file…", lang)}</span>
              <input type="file" accept="image/*" className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] || null)} data-testid="booking-proof-file" />
            </label>
            <div>
              <label className="text-[12.5px] font-medium text-foreground/80">{bi("Nominal transfer (Rp)", "Transfer amount (Rp)", lang)}</label>
              <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2.5 text-[14px] tabular-nums text-foreground outline-none"
                data-testid="booking-proof-amount" />
            </div>
            <div>
              <label className="text-[12.5px] font-medium text-foreground/80">{bi("Nama pengirim", "Sender name", lang)}</label>
              <input value={sender} onChange={(e) => setSender(e.target.value)}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2.5 text-[14px] text-foreground outline-none"
                data-testid="booking-proof-sender" />
            </div>
            <div className="sm:col-span-2">
              <label className="text-[12.5px] font-medium text-foreground/80">{bi("Bank pengirim", "Sender bank", lang)}</label>
              <input value={bank} onChange={(e) => setBank(e.target.value)} placeholder="BCA / Mandiri / …"
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2.5 text-[14px] text-foreground outline-none"
                data-testid="booking-proof-bank" />
            </div>
          </div>
          <button type="button" onClick={send} disabled={busy || !file} data-testid="booking-proof-submit"
            className="cta-shine mt-4 flex w-full items-center justify-center gap-2 rounded-lg py-3 text-[14px] font-semibold text-primary-foreground transition hover:-translate-y-0.5 disabled:opacity-60"
            style={{ background: "var(--gradient-cta)" }}>
            {busy ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />} {bi("Kirim bukti transfer", "Send transfer proof", lang)}
          </button>
        </div>
      ) : null}

      <div className="rounded-2xl border border-border bg-card p-5">
        <h4 className="text-[15px] font-semibold text-foreground">{bi("Riwayat bukti pembayaran", "Payment proof history", lang)}</h4>
        {(status?.proofs || []).length === 0 ? (
          <p className="mt-2 text-[12.5px] text-muted-foreground" data-testid="booking-proofs-empty">
            {bi("Belum ada bukti yang diunggah.", "No proof uploaded yet.", lang)}
          </p>
        ) : (
          <ul className="mt-3 space-y-2" data-testid="booking-proofs-list">
            {(status.proofs || []).map((p) => {
              const toneRaw = PROOF_TONE[p.status] || PROOF_TONE.pending;
              const tone = { label: bi(toneRaw.id, toneRaw.en, lang), cls: toneRaw.cls };
              return (
                <li key={p.id} className="flex items-center justify-between gap-3 rounded-xl border border-border px-4 py-3"
                  data-testid={`booking-proof-${p.id}`}>
                  <div className="min-w-0">
                    <p className="font-mono text-[13.5px] font-semibold tabular-nums text-foreground">
                      {formatCurrency(p.amount_claimed)}
                    </p>
                    <p className="text-[11.5px] text-muted-foreground">{formatDateTime(p.created_at)}</p>
                    {p.reject_reason ? (
                      <p className="mt-1 inline-flex items-start gap-1 text-[11.5px] text-[hsl(var(--destructive))]">
                        <AlertTriangle size={12} className="mt-0.5" /> {p.reject_reason}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${tone.cls}`}>{tone.label}</span>
                    {p.media_url ? (
                      <a href={p.media_url} target="_blank" rel="noreferrer"
                        className="rounded-lg border border-border px-2.5 py-1.5 text-[11.5px] font-semibold text-foreground"
                        data-testid={`booking-proof-view-${p.id}`}>{bi("Lihat", "View", lang)}</a>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
