import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Send, Loader2, MapPin, Users, Phone, Mail, User, MessageSquare, CalendarClock } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import PageHero from "@/components/public/PageHero";
import SelectField from "@/components/shared/SelectField";
import { getAttribution } from "@/utils/attribution";
import { getBookingConfig } from "@/services/bookingApi";
import { trackBeginCheckout, trackLead } from "@/lib/tracking";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

// Pilihan preferensi unit diambil dari DATA lewat /api/public/booking/config.
// Daftar statis sebelumnya menawarkan "Hiace Commuter" & "Alphard" yang TIDAK ADA tarifnya
// maupun unitnya, sehingga permintaan masuk dengan tipe yang tak bisa dipenuhi ops dan harga
// jatuh diam-diam ke tarif default. Satu-satunya sumber kebenaran = armada yang benar-benar ada.

function toIso(localValue) {
  if (!localValue) return "";
  const d = new Date(localValue);
  return Number.isNaN(d.getTime()) ? "" : d.toISOString();
}

export default function BookingRequest() {
  const lang = useLangValue();
  const noPref = { value: "", label: bi("— Tanpa preferensi —", "— No preference —", lang) };
  const location = useLocation();
  const [prefs, setPrefs] = useState([noPref]);
  // Daftar tipe unit datang dari API. Kalau panggilan itu gagal/kosong, dropdown dulu hanya
  // menyisakan "— Tanpa preferensi —" TANPA penjelasan apa pun — tamu menyangka pilihannya
  // hilang. `prefsReady` memisahkan "sedang dimuat" dari "memang tidak ada".
  const [prefsReady, setPrefsReady] = useState(false);
  const navigate = useNavigate();
  const st = location.state || {};
  const [form, setForm] = useState({
    name: "", phone: "", email: "", origin: st.origin || "", destination: st.destination || "",
    start: "", end: "", pax: st.pax || "", vehicle_type: st.vehicle_type || "", message: "", hp: "",
  });
  const [consent, setConsent] = useState(true);
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  // Pengunjung mulai mengisi formulir = tahap checkout pada funnel iklan.
  useEffect(() => { trackBeginCheckout({ value: 0 }); }, []);
  useEffect(() => {
    getBookingConfig()
      .then((cfg) => setPrefs([noPref, ...(cfg?.vehicle_types || []).map((t) => ({
        value: t.value, label: `${t.label} · ${bi("s/d", "up to", lang)} ${t.max_capacity} ${bi("orang", "people", lang)}`,
      }))]))
      .catch(() => setPrefs([noPref]))
      .finally(() => setPrefsReady(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.phone.trim()) { toast.error(bi("Nama & nomor WhatsApp wajib diisi", "Name & WhatsApp number are required", lang)); return; }
    if (!form.start || !form.end) { toast.error(bi("Tanggal mulai & selesai wajib diisi", "Start & end dates are required", lang)); return; }
    if (toIso(form.end) <= toIso(form.start)) { toast.error(bi("Tanggal selesai harus setelah tanggal mulai", "End date must be after the start date", lang)); return; }
    setSaving(true);
    try {
      const res = await apiClient.post("/public/booking", {
        name: form.name.trim(), phone: form.phone.trim(), email: form.email,
        origin: form.origin, destination: form.destination,
        start_datetime: toIso(form.start), end_datetime: toIso(form.end),
        pax: Number(form.pax) || 1, vehicle_type: form.vehicle_type, message: form.message, hp: form.hp,
        attribution: getAttribution(), marketing_consent: consent,
      });
      // event_id memakai ID bisnis yang SAMA dengan konversi server-side (Meta men-dedup 48 jam).
      trackLead({ eventKey: `lead_${res.data.id || res.data.code}`, source: "booking_request" });
      navigate("/thank-you", { state: { name: form.name.trim(), code: res.data.code, kind: "booking" } });
    } catch (err) {
      toast.error(err?.response?.data?.detail || bi("Gagal mengirim permintaan. Coba lagi.", "Failed to send your request. Please try again.", lang));
    } finally { setSaving(false); }
  };

  const field = "mt-1 flex items-center gap-2 rounded-lg border border-[#dfe1e8] px-3";
  const input = "w-full bg-transparent py-2.5 text-[14px] outline-none";

  return (
    <div>
      <PageHero eyebrow={bi("Pesan Sekarang", "Book Now", lang)} title={bi("Ajukan pemesanan armada", "Submit a vehicle booking", lang)}
        subtitle={bi("Untuk paket wisata, sewa lepas kunci, atau kebutuhan khusus. Ingin langsung dapat kode booking & harga final? Gunakan Pesan Online.", "For tour packages, self-drive rentals or special needs. Want an instant booking code & final price? Use Book Online.", lang)}
        image="https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?q=80&w=2000&auto=format&fit=crop"
        breadcrumb={[{ label: bi("Beranda", "Home", lang), to: "/" }, { label: bi("Pesan Sekarang", "Book Now", lang) }]} />
      <section className="mx-auto max-w-2xl px-5 py-14">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border bg-card px-4 py-3">
          <p className="text-[12.5px] text-muted-foreground">
            {bi("Butuh unit sekarang dengan harga final & ketersediaan nyata?", "Need a unit now with a final price & real availability?", lang)}
          </p>
          <a href="/booking" data-testid="br-to-wizard"
            className="rounded-lg border border-border px-3 py-1.5 text-[12.5px] font-semibold text-foreground">
            {bi("Pesan Online", "Book online", lang)}
          </a>
        </div>
        <form onSubmit={submit} className="rounded-2xl border border-[#e7e9ef] bg-white p-6 sm:p-8" data-testid="booking-request-form">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2"><label className="text-[13px] font-medium text-[#3a3f4a]">{bi("Nama Lengkap *", "Full Name *", lang)}</label><div className={field}><User size={15} className="text-[#9aa0ad]" /><input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder={bi("Nama / instansi", "Name / organisation", lang)} className={input} data-testid="br-name" /></div></div>
            <div><label className="text-[13px] font-medium text-[#3a3f4a]">{bi("No. WhatsApp *", "WhatsApp No. *", lang)}</label><div className={field}><Phone size={15} className="text-[#9aa0ad]" /><input value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="0812xxxx" className={input} data-testid="br-phone" /></div></div>
            <div><label className="text-[13px] font-medium text-[#3a3f4a]">Email</label><div className={field}><Mail size={15} className="text-[#9aa0ad]" /><input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} placeholder="email@domain.id" className={input} data-testid="br-email" /></div></div>
            <div><label className="text-[13px] font-medium text-[#3a3f4a]">{bi("Asal", "Origin", lang)}</label><div className={field}><MapPin size={15} className="text-[#9aa0ad]" /><input value={form.origin} onChange={(e) => set("origin", e.target.value)} placeholder="Bandung" className={input} data-testid="br-origin" /></div></div>
            <div><label className="text-[13px] font-medium text-[#3a3f4a]">{bi("Tujuan", "Destination", lang)}</label><div className={field}><MapPin size={15} className="text-[#9aa0ad]" /><input value={form.destination} onChange={(e) => set("destination", e.target.value)} placeholder="Bali, Bromo…" className={input} data-testid="br-destination" /></div></div>
            <div><label className="text-[13px] font-medium text-[#3a3f4a]">{bi("Mulai *", "Start *", lang)}</label><div className={field}><CalendarClock size={15} className="text-[#9aa0ad]" /><input type="datetime-local" value={form.start} onChange={(e) => set("start", e.target.value)} className={input} data-testid="br-start" /></div></div>
            <div><label className="text-[13px] font-medium text-[#3a3f4a]">{bi("Selesai *", "End *", lang)}</label><div className={field}><CalendarClock size={15} className="text-[#9aa0ad]" /><input type="datetime-local" value={form.end} onChange={(e) => set("end", e.target.value)} className={input} data-testid="br-end" /></div></div>
            <div><label className="text-[13px] font-medium text-[#3a3f4a]">{bi("Pax", "Pax", lang)}</label><div className={field}><Users size={15} className="text-[#9aa0ad]" /><input type="number" min="1" value={form.pax} onChange={(e) => set("pax", e.target.value)} placeholder="10" className={input} data-testid="br-pax" /></div></div>
            <div><label className="text-[13px] font-medium text-[#3a3f4a]">{bi("Preferensi Unit", "Vehicle preference", lang)}</label><div className="mt-1"><SelectField value={form.vehicle_type} onChange={(v) => set("vehicle_type", v)} testId="br-vehicle-type" className="h-[46px] w-full rounded-lg border-[#dfe1e8] text-[14px]" placeholder={bi("— Tanpa preferensi —", "— No preference —", lang)} ariaLabel={bi("Preferensi unit", "Vehicle preference", lang)} options={prefs} /></div>
              {prefsReady && prefs.length <= 1 ? (
                <p className="mt-1.5 text-[11.5px] leading-relaxed text-[#8089a0]" data-testid="br-vehicle-type-empty">
                  {bi("Belum ada daftar tipe unit yang bisa dimuat. Anda tetap bisa mengirim permintaan — tim kami akan menyarankan unit yang cocok.", "No vehicle types could be loaded yet. You can still send your request — our team will suggest a suitable unit.", lang)}
                </p>
              ) : null}</div>
            <div className="sm:col-span-2"><label className="text-[13px] font-medium text-[#3a3f4a]">{bi("Pesan / kebutuhan", "Message / needs", lang)}</label><div className="mt-1 flex items-start gap-2 rounded-lg border border-[#dfe1e8] px-3"><MessageSquare size={15} className="mt-3 text-[#9aa0ad]" /><textarea value={form.message} onChange={(e) => set("message", e.target.value)} rows={3} placeholder={bi("Itinerary, titik jemput, dll.", "Itinerary, pickup point, etc.", lang)} className="w-full resize-none bg-transparent py-2.5 text-[14px] outline-none" data-testid="br-message" /></div></div>
          </div>
          <div aria-hidden="true" style={{ position: "absolute", left: "-9999px", height: 0, width: 0, overflow: "hidden" }}>
            <label>{bi("Jangan isi kolom ini", "Do not fill this field", lang)}<input type="text" tabIndex={-1} autoComplete="off" value={form.hp} onChange={(e) => set("hp", e.target.value)} data-testid="br-hp" /></label>
          </div>
          <label className="mt-5 flex cursor-pointer items-start gap-2.5 rounded-lg bg-[#f6f7fb] p-3 text-[12.5px] text-[#3a3f4a]" data-testid="br-consent-wrap">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5 h-4 w-4 accent-[#101935]" data-testid="br-consent" />
            <span>{bi("Saya setuju dihubungi via WhatsApp/email untuk konfirmasi pemesanan & promosi dari RahazaTrans.", "I agree to be contacted via WhatsApp/email for booking confirmation & promotions from RahazaTrans.", lang)}</span>
          </label>
          <button type="submit" disabled={saving} className="cta-shine glow-focus mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-[#101935] py-3.5 text-[14px] font-semibold text-white transition hover:bg-[#1c2a52] disabled:opacity-60" data-testid="br-submit">
            {saving ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />} {bi("Kirim Permintaan Pesanan", "Send Booking Request", lang)}
          </button>
          <p className="mt-3 text-center text-[12px] text-[#8089a0]">{bi("Permintaan Anda akan ditinjau tim ops. Konfirmasi final via WhatsApp.", "Your request will be reviewed by our ops team. Final confirmation via WhatsApp.", lang)}</p>
        </form>
      </section>
    </div>
  );
}
