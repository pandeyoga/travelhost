import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Clock3, TriangleAlert } from "lucide-react";
import { rememberedBookings, forgetBooking, getBookingStatus } from "@/services/bookingApi";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

/**
 * ResumeBookingChip — jalan pintas "Lanjutkan pesanan BK-00xx".
 *
 * KENAPA KOMPONEN INI ADA (keputusan UX, bukan hiasan):
 * Halaman `/booking/status` adalah SATU-SATUNYA tempat tamu mengunggah bukti transfer DP.
 * Setelah menu navbar dirapikan, tautan "Cek Pesanan" tidak lagi memakan slot menu utama —
 * risikonya tamu yang BARU transfer kebingungan mencari tempat unggah, lalu hold-nya hangus
 * otomatis (2 jam pada mode `hold_dp`). Chip ini memakai kode+token yang SUDAH disimpan
 * `rememberBooking()` di localStorage saat pesanan dibuat, jadi tamu kembali ke halaman
 * statusnya dengan SATU klik tanpa mengingat kode apa pun.
 *
 * Aturan tampil (biar tidak jadi sampah visual):
 *   - hanya muncul bila ada pesanan yang MASIH menuntut tindakan (pending / hold / bukti ditolak);
 *   - pesanan yang sudah `confirmed`/`cancelled` TIDAK ditampilkan (tidak ada yang perlu dilanjutkan);
 *   - token yang sudah tidak berlaku (404) DIBUANG dari localStorage — self-healing, bukan chip hantu.
 */
const LABEL = (lang) => ({
  pending: bi("Menunggu ACC admin", "Awaiting admin approval", lang),
  hold: bi("Menunggu bukti DP", "Awaiting deposit proof", lang),
  proof_pending: bi("Bukti sedang diperiksa", "Proof under review", lang),
  proof_rejected: bi("Bukti ditolak — unggah ulang", "Proof rejected — re-upload", lang),
});

function deriveState(d) {
  const status = String(d?.status || "");
  if (!["pending", "hold"].includes(status)) return null;
  const proofs = Array.isArray(d?.proofs) ? d.proofs : [];
  const latest = proofs[0];
  if (latest?.status === "rejected") return { key: "proof_rejected", urgent: true };
  if (latest?.status === "pending") return { key: "proof_pending", urgent: false };
  return { key: status, urgent: status === "hold" };
}

export default function ResumeBookingChip({ variant = "bar", className = "" }) {
  const lang = useLangValue();
  const [item, setItem] = useState(null);

  useEffect(() => {
    let alive = true;
    const list = rememberedBookings();
    if (!list.length) return undefined;
    (async () => {
      for (const b of list.slice(0, 3)) {
        try {
          const d = await getBookingStatus(b.code, b.token);
          const state = deriveState(d);
          if (state) {
            if (alive) setItem({ code: b.code, token: b.token, ...state });
            return;
          }
        } catch (err) {
          if (err?.response?.status === 404) forgetBooking(b.code);
        }
      }
    })();
    return () => { alive = false; };
  }, []);

  if (!item) return null;
  const to = `/booking/status?code=${encodeURIComponent(item.code)}&token=${encodeURIComponent(item.token)}`;
  const Icon = item.urgent ? TriangleAlert : Clock3;

  if (variant === "block") {
    return (
      <Link to={to} data-testid="resume-booking-block"
        className={`group inline-flex items-center gap-3 rounded-2xl border border-border bg-card px-4 py-3 text-left transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)] ${className}`}>
        <span className={`flex h-9 w-9 items-center justify-center rounded-full ${item.urgent ? "bg-[#FDECEA] text-[#A8221A]" : "bg-secondary text-secondary-foreground"}`}>
          <Icon size={16} />
        </span>
        <span className="min-w-0">
          <span className="block text-[13.5px] font-semibold text-foreground">{bi(`Lanjutkan pesanan ${item.code}`, `Resume booking ${item.code}`, lang)}</span>
          <span className="block text-[12px] text-muted-foreground">{LABEL(lang)[item.key]}</span>
        </span>
        <ArrowRight size={16} className="ml-1 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5" />
      </Link>
    );
  }

  return (
    <Link to={to} data-testid="resume-booking-chip" title={`${LABEL(lang)[item.key]} — ${item.code}`}
      className={`inline-flex max-w-[15rem] items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold transition ${item.urgent ? "bg-[#FFD8D2] text-[#7A1912]" : "bg-white/20 text-current hover:bg-white/30"} ${className}`}>
      <Icon size={12} className="shrink-0" />
      <span className="truncate">{bi(`Lanjutkan ${item.code}`, `Resume ${item.code}`, lang)}</span>
    </Link>
  );
}
