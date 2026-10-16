import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Loader2, Search, RefreshCw, XCircle, MessageCircle, MapPin, CalendarClock, Users, Ticket,
} from "lucide-react";
import { toast } from "sonner";
import PageHero from "@/components/public/PageHero";
import PaymentInstructions, { HoldCountdown } from "@/components/public/booking/PaymentInstructions";
import { formatCurrency, formatDateTime } from "@/utils/formatters";
import {
  cancelBooking, getBookingStatus, lookupBooking, rememberBooking, rememberedBookings,
} from "@/services/bookingApi";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

// BookingStatus — halaman "pesanan saya" TANPA akun pelanggan.
//
// Dua jalan masuk: (1) tautan ber-token yang dibuka otomatis setelah memesan, dan (2) formulir
// kode booking + nomor WhatsApp untuk yang datang kembali di lain hari/peramban.
const TONE = {
  hold: { id: "Unit ditahan — menunggu DP", en: "Unit on hold — awaiting deposit", cls: "bg-[hsl(var(--warning,38_92%_50%))]/15 text-foreground" },
  pending: { id: "Menunggu konfirmasi tim", en: "Awaiting team confirmation", cls: "bg-secondary text-secondary-foreground" },
  confirmed: { id: "Terkonfirmasi", en: "Confirmed", cls: "bg-primary/10 text-primary" },
  ongoing: { id: "Sedang berjalan", en: "In progress", cls: "bg-primary/10 text-primary" },
  completed: { id: "Selesai", en: "Completed", cls: "bg-primary/10 text-primary" },
  cancelled: { id: "Dibatalkan", en: "Cancelled", cls: "bg-[hsl(var(--destructive))]/10 text-[hsl(var(--destructive))]" },
};

export default function BookingStatus() {
  const lang = useLangValue();
  const [params, setParams] = useSearchParams();
  const code = params.get("code") || "";
  const token = params.get("token") || "";
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(Boolean(code && token));
  const [error, setError] = useState("");
  const [form, setForm] = useState({ code: code || "", phone: "" });
  const [looking, setLooking] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const saved = rememberedBookings();

  const load = useCallback(async () => {
    if (!code || !token) return;
    setLoading(true);
    setError("");
    try {
      const data = await getBookingStatus(code, token);
      setStatus(data);
      rememberBooking({ code, token });
    } catch (e) {
      setError(e?.response?.data?.detail || bi("Tautan status pesanan tidak valid atau kedaluwarsa.", "This booking status link is invalid or has expired.", lang));
      setStatus(null);
    } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, token]);

  useEffect(() => { load(); }, [load]);

  const doLookup = async (e) => {
    e.preventDefault();
    if (!form.code.trim() || !form.phone.trim()) {
      toast.error(bi("Isi kode booking & nomor WhatsApp", "Enter the booking code & WhatsApp number", lang)); return;
    }
    setLooking(true);
    try {
      const res = await lookupBooking({ code: form.code.trim().toUpperCase(), phone: form.phone.trim() });
      rememberBooking({ code: res.code, token: res.token });
      setParams({ code: res.code, token: res.token });
    } catch (e) {
      toast.error(e?.response?.data?.detail || bi("Pesanan tidak ditemukan", "Booking not found", lang));
    } finally { setLooking(false); }
  };

  const doCancel = async () => {
    if (!window.confirm(bi("Batalkan pesanan ini? Unit akan dilepas untuk pelanggan lain.", "Cancel this booking? The unit will be released to other customers.", lang))) return;
    setCancelling(true);
    try {
      await cancelBooking(code, { token, reason: "Dibatalkan dari halaman status" });
      toast.success(bi("Pesanan dibatalkan", "Booking cancelled", lang));
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || bi("Gagal membatalkan pesanan", "Failed to cancel the booking", lang));
    } finally { setCancelling(false); }
  };

  const toneRaw = TONE[status?.status] || TONE.pending;
  const tone = { label: bi(toneRaw.id, toneRaw.en, lang), cls: toneRaw.cls };
  const showPayment = status && ["hold", "pending", "confirmed", "ongoing"].includes(status.status);

  return (
    <div>
      <PageHero eyebrow={bi("Status Pesanan", "Booking Status", lang)} title={bi("Lacak pesanan Anda", "Track your booking", lang)}
        subtitle={bi("Tanpa akun — cukup kode booking dan nomor WhatsApp yang Anda pakai saat memesan.", "No account — just the booking code and WhatsApp number you used when booking.", lang)}
        image="https://images.unsplash.com/photo-1521737604893-d14cc237f11d?q=80&w=2000&auto=format&fit=crop"
        breadcrumb={[{ label: bi("Beranda", "Home", lang), to: "/" }, { label: bi("Status Pesanan", "Booking Status", lang) }]} />

      <section className="mx-auto max-w-5xl px-4 py-12 sm:px-6 lg:px-8">
        {!code || !token || error ? (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_.9fr]">
            <form onSubmit={doLookup} className="rounded-2xl border border-border bg-card p-6" data-testid="booking-lookup-form">
              <h2 className="font-fraunces text-2xl text-foreground">{bi("Cek pesanan", "Check booking", lang)}</h2>
              {error ? (
                <p className="mt-2 rounded-lg bg-[hsl(var(--destructive))]/10 px-3 py-2 text-[12.5px] text-[hsl(var(--destructive))]"
                  data-testid="booking-status-error">{error}</p>
              ) : null}
              <div className="mt-4 space-y-4">
                <div>
                  <label className="text-[12.5px] font-medium text-foreground/80">{bi("Kode booking", "Booking code", lang)}</label>
                  <input value={form.code} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}
                    placeholder="BK-0001" data-testid="lookup-code"
                    className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2.5 text-[14px] font-mono tabular-nums text-foreground outline-none focus:border-ring" />
                </div>
                <div>
                  <label className="text-[12.5px] font-medium text-foreground/80">{bi("No. WhatsApp saat memesan", "WhatsApp No. used when booking", lang)}</label>
                  <input value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                    placeholder="0812xxxxxxx" data-testid="lookup-phone"
                    className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2.5 text-[14px] text-foreground outline-none focus:border-ring" />
                </div>
                <button type="submit" disabled={looking} data-testid="lookup-submit"
                  className="cta-shine flex w-full items-center justify-center gap-2 rounded-lg py-3 text-[14px] font-semibold text-primary-foreground transition hover:-translate-y-0.5 disabled:opacity-60"
                  style={{ background: "var(--gradient-cta)" }}>
                  {looking ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />} {bi("Lihat status", "View status", lang)}
                </button>
              </div>
            </form>
            <aside className="glass rounded-2xl p-6">
              <h3 className="font-fraunces text-xl text-foreground">{bi("Pesanan tersimpan di peramban ini", "Bookings saved in this browser", lang)}</h3>
              {saved.length === 0 ? (
                <p className="mt-3 text-[13px] text-muted-foreground" data-testid="booking-saved-empty">
                  {bi("Belum ada. Pesanan yang Anda buat dari perangkat ini akan muncul di sini.", "None yet. Bookings you make from this device will appear here.", lang)}
                </p>
              ) : (
                <ul className="mt-3 space-y-2" data-testid="booking-saved-list">
                  {saved.map((b) => (
                    <li key={b.code}>
                      <Link to={`/booking/status?code=${encodeURIComponent(b.code)}&token=${encodeURIComponent(b.token)}`}
                        data-testid={`booking-saved-${b.code}`}
                        className="flex items-center justify-between rounded-xl border border-border bg-card px-4 py-3 text-[13.5px] transition hover:-translate-y-0.5">
                        <span className="font-mono font-semibold tabular-nums text-foreground">{b.code}</span>
                        <span className="text-muted-foreground">{bi("Lihat status", "View status", lang)}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              <Link to="/booking" className="mt-5 inline-flex items-center gap-1.5 text-[13px] font-semibold text-primary"
                data-testid="booking-status-to-wizard">
                <Ticket size={14} /> {bi("Buat pesanan baru", "Create a new booking", lang)}
              </Link>
            </aside>
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center gap-2 rounded-2xl border border-border bg-card py-24 text-muted-foreground"
            data-testid="booking-status-loading">
            <Loader2 size={18} className="animate-spin" /> {bi("Memuat status pesanan…", "Loading booking status…", lang)}
          </div>
        ) : status ? (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.05fr_.95fr]">
            <div className="space-y-4">
              <div className="rounded-2xl border border-border bg-card p-6" data-testid="booking-status-card">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[12px] uppercase tracking-wide text-muted-foreground">{bi("Kode booking", "Booking code", lang)}</p>
                    <p className="font-mono text-2xl font-semibold tabular-nums text-foreground" data-testid="booking-status-code">
                      {status.code}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-3 py-1.5 text-[12px] font-semibold ${tone.cls}`} data-testid="booking-status-pill">
                      {tone.label}
                    </span>
                    <button onClick={load} className="icon-button rounded-lg border border-border p-2" title={bi("Muat ulang", "Refresh", lang)}
                      data-testid="booking-status-refresh"><RefreshCw size={14} /></button>
                  </div>
                </div>
                <p className="mt-3 text-[13.5px] leading-relaxed text-muted-foreground" data-testid="booking-status-message">
                  {status.message}
                </p>
                {status.status === "hold" ? (
                  <div className="mt-4">
                    <HoldCountdown seconds={status.countdown_seconds} expiresAt={status.hold_expires_at} />
                  </div>
                ) : null}
                <dl className="mt-5 grid grid-cols-1 gap-3 border-t border-border pt-4 text-[13px] sm:grid-cols-2">
                  <div><dt className="text-muted-foreground">{bi("Layanan", "Service", lang)}</dt>
                    <dd className="font-medium text-foreground">{status.service_label}</dd></div>
                  <div><dt className="text-muted-foreground">{bi("Unit", "Unit", lang)}</dt>
                    <dd className="font-medium text-foreground">{status.vehicle_name || bi("Ditetapkan tim kami", "Assigned by our team", lang)}</dd></div>
                  <div><dt className="flex items-center gap-1 text-muted-foreground"><CalendarClock size={12} /> {bi("Mulai", "Start", lang)}</dt>
                    <dd className="font-medium text-foreground">{formatDateTime(status.start_datetime)}</dd></div>
                  <div><dt className="flex items-center gap-1 text-muted-foreground"><CalendarClock size={12} /> {bi("Selesai", "End", lang)}</dt>
                    <dd className="font-medium text-foreground">{formatDateTime(status.end_datetime)}</dd></div>
                  <div><dt className="flex items-center gap-1 text-muted-foreground"><Users size={12} /> {bi("Penumpang", "Passengers", lang)}</dt>
                    <dd className="font-medium text-foreground">{status.pax} {bi("orang", "people", lang)}</dd></div>
                  <div><dt className="flex items-center gap-1 text-muted-foreground"><MapPin size={12} /> {status.route_name ? bi("Rute", "Route", lang) : bi("Perjalanan", "Trip", lang)}</dt>
                    <dd className="font-medium text-foreground">
                      {status.route_name || `${status.origin || "-"} → ${status.destination || "-"}`}
                    </dd></div>
                  {status.pickup_address ? (
                    <div className="sm:col-span-2"><dt className="text-muted-foreground">{bi("Titik jemput", "Pickup point", lang)}</dt>
                      <dd className="font-medium text-foreground">{status.pickup_address}</dd></div>
                  ) : null}
                </dl>
              </div>

              <div className="rounded-2xl border border-border bg-card p-5" data-testid="booking-status-breakdown">
                <h3 className="text-[15px] font-semibold text-foreground">{bi("Rincian harga", "Price breakdown", lang)}</h3>
                {(status.price_breakdown || []).length === 0 ? (
                  <p className="mt-2 text-[12.5px] text-muted-foreground" data-testid="booking-breakdown-empty">
                    {bi("Harga final ditetapkan tim kami setelah ketersediaan dikonfirmasi.", "The final price is set by our team once availability is confirmed.", lang)}
                  </p>
                ) : (
                  <div className="mt-2 divide-y divide-border">
                    {status.price_breakdown.map((b, i) => (
                      <div key={i} className="flex items-center justify-between py-2.5 text-[13.5px]">
                        <span className={b.amount < 0 ? "text-primary" : "text-muted-foreground"}>{b.label}</span>
                        <span className="font-mono font-semibold tabular-nums text-foreground">{formatCurrency(b.amount)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                {status.can_cancel ? (
                  <button onClick={doCancel} disabled={cancelling} data-testid="booking-cancel"
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[hsl(var(--destructive))]/40 px-4 py-2.5 text-[13px] font-semibold text-[hsl(var(--destructive))] transition hover:-translate-y-0.5 disabled:opacity-60">
                    {cancelling ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />} {bi("Batalkan pesanan", "Cancel booking", lang)}
                  </button>
                ) : null}
                <Link to="/contact" className="inline-flex items-center gap-1.5 rounded-lg border border-border px-4 py-2.5 text-[13px] font-semibold text-foreground"
                  data-testid="booking-need-help"><MessageCircle size={14} /> {bi("Butuh bantuan", "Need help", lang)}</Link>
              </div>
            </div>

            <div>
              {showPayment ? (
                <PaymentInstructions status={status} code={code} token={token} onRefresh={load} />
              ) : (
                <div className="rounded-2xl border border-border bg-card p-6" data-testid="booking-payment-closed">
                  <p className="text-[13.5px] text-muted-foreground">
                    {bi("Pesanan ini sudah tidak menerima pembayaran. Hubungi kami bila ada pertanyaan.", "This booking no longer accepts payments. Contact us if you have questions.", lang)}
                  </p>
                </div>
              )}
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
