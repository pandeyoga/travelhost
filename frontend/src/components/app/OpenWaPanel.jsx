import { useCallback, useEffect, useRef, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { toast } from "sonner";
import { Loader2, QrCode, RefreshCw, Trash2, CheckCircle2, AlertTriangle, Smartphone } from "lucide-react";
import apiClient from "@/services/apiClient";

const badge = (st) => {
  if (st?.connected) return ["Terhubung", "bg-[#34C759]/15 text-[#127A36]"];
  if (st?.running) return ["Menunggu Scan QR", "bg-[#FF9500]/15 text-[#8C4A00]"];
  if (st?.starting) return ["Memulai…", "bg-[#007AFF]/12 text-[#0058CC]"];
  return ["Mati", "bg-[#FF3B30]/12 text-[#A8221A]"];
};

export const OpenWaPanel = () => {
  const [status, setStatus] = useState(null);
  const [qr, setQr] = useState("");
  const [busy, setBusy] = useState(false);
  const timer = useRef(null);

  const poll = useCallback(async () => {
    try {
      const r = await apiClient.get("/wa/openwa/status");
      setStatus(r.data);
      if (r.data?.running && !r.data?.connected) {
        const q = await apiClient.get("/wa/openwa/qr");
        setQr(q.data?.qr || "");
      } else {
        setQr("");
      }
    } catch { setStatus(null); }
  }, []);

  useEffect(() => {
    poll();
    timer.current = setInterval(poll, 6000);
    return () => clearInterval(timer.current);
  }, [poll]);

  const restart = async (fresh) => {
    if (fresh && !window.confirm("Reset sesi? Nomor akan terputus dan WAJIB scan QR ulang.")) return;
    setBusy(true);
    try {
      const r = await apiClient.post(`/wa/openwa/restart?fresh=${fresh ? "true" : "false"}`);
      setStatus(r.data);
      toast.success(fresh ? "Sesi direset — scan QR baru" : "Sidecar direstart");
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal restart"); }
    finally { setBusy(false); poll(); }
  };

  const [label, cls] = badge(status);
  return (
    <div className="rounded-[10px] border border-[#CDEBD4] bg-[#F2FBF4] p-3" data-testid="wa-openwa-box">
      <p className="mb-2 flex flex-wrap items-center gap-2 text-[12px] font-semibold text-[#127A36]">
        <Smartphone size={13} /> OpenWA — WhatsApp via Scan QR
        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${cls}`} data-testid="wa-openwa-status">
          {status?.connected ? <CheckCircle2 size={11} /> : null}{label}
        </span>
      </p>
      <p className="mb-2 text-[11.5px] text-[#3C3C43]">
        Memakai WhatsApp Web (bukan API resmi Meta). Gunakan <b>nomor khusus bisnis</b> — ada risiko
        diblokir WhatsApp. Tanpa approval template & tanpa batas sesi 24 jam. Pesan masuk otomatis
        menjadi lead + percakapan di Inbox.
      </p>
      {status?.error ? (
        <p className="mb-2 flex items-center gap-1.5 rounded-[8px] bg-[#FF9500]/10 px-2.5 py-1.5 text-[11.5px] font-medium text-[#8C4A00]" data-testid="wa-openwa-error">
          <AlertTriangle size={12} /> {status.error}
        </p>
      ) : null}
      {status?.running && !status?.connected ? (
        <div className="mb-2 flex flex-col items-center gap-2 rounded-[10px] border border-[#E2E2E7] bg-white p-4" data-testid="wa-openwa-qr-wrap">
          {qr ? (
            <>
              <QRCodeSVG value={qr} size={216} data-testid="wa-openwa-qr" />
              <p className="text-center text-[11.5px] text-[#6B6B73]">
                Buka WhatsApp di ponsel → <b>Perangkat Tertaut</b> → <b>Tautkan Perangkat</b> → scan QR ini.
                QR diperbarui otomatis.
              </p>
            </>
          ) : (
            <p className="flex items-center gap-2 py-6 text-[12.5px] text-[#8E8E93]" data-testid="wa-openwa-qr-loading">
              <Loader2 size={14} className="animate-spin" /> Menyiapkan QR code…
            </p>
          )}
        </div>
      ) : null}
      {status?.connected ? (
        <p className="mb-2 rounded-[8px] bg-[#34C759]/10 px-2.5 py-1.5 text-[11.5px] font-medium text-[#127A36]" data-testid="wa-openwa-connected">
          Nomor tertaut & siap kirim-terima. Biarkan sesi hidup minimal 5 menit setelah scan pertama.
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <button className="secondary-button" onClick={() => restart(false)} disabled={busy} data-testid="wa-openwa-restart">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />} Jalankan / Restart
        </button>
        <button className="secondary-button !text-[#A8221A]" onClick={() => restart(true)} disabled={busy} data-testid="wa-openwa-reset">
          <Trash2 size={13} /> Reset Sesi (scan ulang)
        </button>
        <button className="secondary-button" onClick={poll} disabled={busy} data-testid="wa-openwa-refresh">
          <QrCode size={13} /> Muat Ulang Status
        </button>
      </div>
    </div>
  );
};
