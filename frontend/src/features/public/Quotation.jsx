import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Send, Loader2, MapPin, Users, Phone, Mail, User, MessageSquare } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { trackLead } from "@/lib/tracking";
import PageHero from "@/components/public/PageHero";
import { getAttribution } from "@/utils/attribution";
import useSEO from "@/hooks/useSEO";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

export default function Quotation() {
  const lang = useLangValue();
  const location = useLocation();
  const navigate = useNavigate();
  const st = location.state || {};
  const [form, setForm] = useState({
    name: "", phone: "", email: "", destination: st.destination || "",
    trip_date: st.trip_date || "", pax: st.pax || "", message: st.message || "", hp: "",
  });
  // INV-REF-02 batch 3: destinasi form publik = pilihan ber-master (bukan ketik bebas).
  const [destOptions, setDestOptions] = useState([]);
  useEffect(() => {
    apiClient.get("/public/destination-options")
      .then((r) => setDestOptions(Array.isArray(r.data) ? r.data : []))
      .catch(() => setDestOptions([]));
  }, []);
  const [consent, setConsent] = useState(true);
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.phone.trim()) { toast.error(bi("Nama & nomor WhatsApp wajib diisi", "Name & WhatsApp number are required", lang)); return; }
    setSaving(true);
    try {
      const res = await apiClient.post("/public/quotation", {
        name: form.name.trim(), phone: form.phone.trim(), email: form.email,
        destination: form.destination, trip_date: form.trip_date || null,
        pax: Number(form.pax) || 1, message: form.message, hp: form.hp,
        attribution: getAttribution(), marketing_consent: consent,
      });
      trackLead({ eventKey: `lead_${(res && res.data && (res.data.lead_id || res.data.id)) || form.phone.trim()}`, source: "quotation" });
      navigate("/thank-you", { state: { name: form.name.trim() } });
    } catch (err) {
      toast.error(err?.response?.data?.detail || bi("Gagal mengirim permintaan. Coba lagi.", "Failed to send your request. Please try again.", lang));
    } finally { setSaving(false); }
  };

  const field = "mt-1 flex items-center gap-2 rounded-lg border border-[#dfe1e8] px-3";
  const input = "w-full bg-transparent py-2.5 text-[14px] outline-none";

  // CMS-02 SEO: meta dasar halaman Penawaran (Quotation) — dua bahasa.
  useSEO({
    title: bi("Minta Penawaran", "Request a Quote", lang),
    description: bi(
      "Ceritakan rencana trip Anda. Tim RahazaTrans akan menghubungi via WhatsApp dengan penawaran terbaik untuk perjalanan lintas Jawa–Bali.",
      "Tell us your trip plan. The RahazaTrans team will reach out via WhatsApp with the best quote for your journey across Java–Bali.",
      lang,
    ),
    image: "https://images.unsplash.com/photo-1488646953014-85cb44e25828?q=80&w=2000&auto=format&fit=crop",
    keywords: "minta penawaran travel, quotation sewa armada, penawaran paket wisata",
  });

  return (
    <div>
      <PageHero eyebrow={bi("Penawaran", "Quote", lang)} title={bi("Minta penawaran perjalanan", "Request a travel quote", lang)}
        subtitle={bi("Ceritakan rencana trip Anda. Tim kami akan menghubungi via WhatsApp dengan penawaran terbaik.", "Tell us your trip plan. Our team will reach out via WhatsApp with the best offer.", lang)}
        image="https://images.unsplash.com/photo-1488646953014-85cb44e25828?q=80&w=2000&auto=format&fit=crop"
        breadcrumb={[{ label: bi("Beranda", "Home", lang), to: "/" }, { label: bi("Penawaran", "Quote", lang) }]} />
      <section className="mx-auto max-w-2xl px-5 py-14">
        <form onSubmit={submit} className="rounded-2xl border border-[#e7e9ef] bg-white p-6 sm:p-8" data-testid="quotation-form">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2"><label className="text-[13px] font-medium text-[#3a3f4a]">{bi("Nama Lengkap *", "Full Name *", lang)}</label><div className={field}><User size={15} className="text-[#9aa0ad]" /><input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder={bi("Nama / instansi", "Name / organisation", lang)} className={input} data-testid="q-name" /></div></div>
            <div><label className="text-[13px] font-medium text-[#3a3f4a]">{bi("No. WhatsApp *", "WhatsApp No. *", lang)}</label><div className={field}><Phone size={15} className="text-[#9aa0ad]" /><input value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="0812xxxx" className={input} data-testid="q-phone" /></div></div>
            <div><label className="text-[13px] font-medium text-[#3a3f4a]">Email</label><div className={field}><Mail size={15} className="text-[#9aa0ad]" /><input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} placeholder="email@domain.id" className={input} data-testid="q-email" /></div></div>
            <div><label className="text-[13px] font-medium text-[#3a3f4a]">{bi("Destinasi", "Destination", lang)}</label><div className={field}><MapPin size={15} className="text-[#9aa0ad]" /><select value={form.destination} onChange={(e) => set("destination", e.target.value)} className={`${input} bg-transparent`} data-testid="q-destination">
              <option value="">{destOptions.length === 0 ? bi("Memuat destinasi…", "Loading destinations…", lang) : bi("Pilih destinasi…", "Choose destination…", lang)}</option>
              {form.destination && !destOptions.some((o) => o.value === form.destination) ? <option value={form.destination}>{form.destination}</option> : null}
              {destOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select></div></div>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="text-[13px] font-medium text-[#3a3f4a]">{bi("Tanggal", "Date", lang)}</label><input type="date" value={form.trip_date} onChange={(e) => set("trip_date", e.target.value)} className="mt-1 w-full rounded-lg border border-[#dfe1e8] px-3 py-2.5 text-[14px] outline-none" data-testid="q-date" /></div>
              <div><label className="text-[13px] font-medium text-[#3a3f4a]">{bi("Pax", "Pax", lang)}</label><div className={field}><Users size={15} className="text-[#9aa0ad]" /><input type="number" min="1" value={form.pax} onChange={(e) => set("pax", e.target.value)} placeholder="10" className={input} data-testid="q-pax" /></div></div>
            </div>
            <div className="sm:col-span-2"><label className="text-[13px] font-medium text-[#3a3f4a]">{bi("Pesan / kebutuhan", "Message / needs", lang)}</label><div className="mt-1 flex items-start gap-2 rounded-lg border border-[#dfe1e8] px-3"><MessageSquare size={15} className="mt-3 text-[#9aa0ad]" /><textarea value={form.message} onChange={(e) => set("message", e.target.value)} rows={3} placeholder={bi("Itinerary, titik jemput, dll.", "Itinerary, pickup point, etc.", lang)} className="w-full resize-none bg-transparent py-2.5 text-[14px] outline-none" data-testid="q-message" /></div></div>
          </div>
          <div aria-hidden="true" style={{ position: "absolute", left: "-9999px", height: 0, width: 0, overflow: "hidden" }}>
            <label>{bi("Jangan isi kolom ini", "Do not fill this field", lang)}<input type="text" tabIndex={-1} autoComplete="off" value={form.hp} onChange={(e) => set("hp", e.target.value)} data-testid="q-hp" /></label>
          </div>
          <label className="mt-5 flex cursor-pointer items-start gap-2.5 rounded-lg bg-[#f6f7fb] p-3 text-[12.5px] text-[#3a3f4a]" data-testid="q-consent-wrap">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5 h-4 w-4 accent-[#101935]" data-testid="q-consent" />
            <span>{bi("Saya setuju dihubungi via WhatsApp/email untuk penawaran & promosi dari RahazaTrans.", "I agree to be contacted via WhatsApp/email for quotes & promotions from RahazaTrans.", lang)}</span>
          </label>
          <button type="submit" disabled={saving} className="cta-shine glow-focus mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-[#101935] py-3.5 text-[14px] font-semibold text-white transition hover:bg-[#1c2a52] disabled:opacity-60" data-testid="q-submit">
            {saving ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />} {bi("Kirim Permintaan", "Send Request", lang)}
          </button>
          <p className="mt-3 text-center text-[12px] text-[#8089a0]">{bi("Data Anda aman. Kami hanya menghubungi untuk keperluan penawaran.", "Your data is safe. We only contact you regarding your quote.", lang)}</p>
        </form>
      </section>
    </div>
  );
}
