import { useEffect, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { useSiteFeatures } from "@/hooks/useSiteFeatures";
import {
  Calculator, Loader2, ArrowRight, Info, CalendarCheck, MessageCircle,
  ServerCog, CalendarClock, BadgePercent, ShieldCheck, Lightbulb,
} from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import CmsPageHero from "@/components/public/CmsPageHero";
import Reveal from "@/components/public/Reveal";
import SectionHeading from "@/components/public/SectionHeading";
import GlassCard from "@/components/public/GlassCard";
import VehicleTypeCompare from "@/components/public/VehicleTypeCompare";
import AirportRouteStrip from "@/components/public/AirportRouteStrip";
import PromoStrip from "@/components/public/PromoStrip";
import FaqBlock from "@/components/public/FaqBlock";
import CtaBand from "@/components/public/CtaBand";
import { formatCurrency } from "@/utils/formatters";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";
import { getBookingConfig } from "@/services/bookingApi";
import useSEO from "@/hooks/useSEO";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

const HERO = "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?q=80&w=2000&auto=format&fit=crop";

export default function TripCalculator() {
  const { ready, tripCalculator } = useSiteFeatures();
  if (ready && !tripCalculator) return <Navigate to="/quotation" replace />;
  return <TripCalculatorPage />;
}

function TripCalculatorPage() {
  const lang = useLangValue();
  const location = useLocation();
  const [form, setForm] = useState({
    vehicle_type: location.state?.vehicle_type || "hiace_premio",
    days: 2, origin: "", destination: location.state?.destination || "", pax: "",
  });
  // Pilihan tipe unit diambil dari DATA (unit yang benar-benar ada & tayang), bukan daftar
  // di dalam kode: dulu kalkulator menawarkan tipe yang tak punya tarif & tak punya unit,
  // sehingga estimasinya jatuh diam-diam ke tarif default.
  const [types, setTypes] = useState([]);
  const [config, setConfig] = useState(null);
  const [cfgLoading, setCfgLoading] = useState(true);
  const [cfgError, setCfgError] = useState("");
  useEffect(() => {
    getBookingConfig()
      .then((cfg) => {
        setConfig(cfg);
        const list = cfg?.vehicle_types || [];
        setTypes(list);
        if (list.length && !list.some((x) => x.value === form.vehicle_type)) {
          set("vehicle_type", list[0].value);
        }
      })
      .catch(() => { setTypes([]); setCfgError("gagal"); })
      .finally(() => setCfgLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const dp = config?.dp_percent || 30;
  const hold = config?.hold_hours || 2;
  const maxDays = config?.max_days || 30;

  const calc = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await apiClient.post("/public/trip-estimate", {
        vehicle_type: form.vehicle_type, days: Number(form.days) || 1,
        origin: form.origin, destination: form.destination,
        pax: Number(form.pax) || 1,
      });
      setResult(data);
    } catch (err) {
      toast.error(bi("Gagal menghitung estimasi. Coba lagi.", "Failed to calculate the estimate. Please try again.", lang));
    } finally { setLoading(false); }
  };

  const inputCls = "mt-1 w-full rounded-lg border border-input bg-background px-3 py-2.5 text-[14px] text-foreground outline-none transition placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/30";

  // Penjelasan mekanisme harga. Angkanya (DP, lama hold, batas hari) DIBACA dari server
  // supaya halaman ini tidak pernah menjanjikan kebijakan yang berbeda dari mesin harga.
  const HOW = [
    { icon: ServerCog, t: bi("Dihitung di server, bukan di browser", "Calculated on the server, not the browser", lang), d: bi("Total selalu dihitung ulang oleh sistem memakai tarif unit yang berlaku. Angka yang Anda lihat = angka yang tersimpan pada pesanan.", "The total is always recomputed by the system using the current unit rates. The number you see equals the number stored on the booking.", lang) },
    { icon: CalendarClock, t: bi("Basis jumlah hari pemakaian", "Based on days of use", lang), d: bi(`Tidak ada komponen "perkiraan kilometer" yang harus Anda tebak. Durasi bisa 1 sampai ${maxDays} hari, dan hari akhir pekan/hari besar dihitung sesuai kebijakan tarif.`, `There is no "estimated kilometre" component to guess. Duration can be 1 to ${maxDays} days, and weekends/holidays are priced per the rate policy.`, lang) },
    { icon: BadgePercent, t: bi("Promo diverifikasi saat memesan", "Promos verified at checkout", lang), d: bi(`Kode promo dinilai ulang oleh server terhadap syaratnya. Jika layak, potongan langsung masuk total sebelum Anda membayar DP ${dp}%.`, `Promo codes are re-evaluated by the server against their terms. If eligible, the discount is applied to the total before you pay the ${dp}% deposit.`, lang) },
  ];

  const FAQS = [
    { q: bi("Apa yang termasuk dalam estimasi ini?", "What is included in this estimate?", lang), a: bi("Estimasi mencakup unit armada beserta driver dan fee operasional dasar sesuai tarif tipe unit yang dipilih. Komponen di luar itu (tiket masuk objek wisata, penginapan driver untuk rute jauh, ferry) dihitung terpisah pada penawaran resmi.", "The estimate covers the vehicle plus its driver and basic operational fees per the chosen unit type's rate. Items beyond that (attraction tickets, driver lodging for long routes, ferries) are quoted separately in the official offer.", lang) },
    { q: bi("Apakah BBM, tol, dan parkir sudah termasuk?", "Are fuel, tolls and parking included?", lang), a: bi("Untuk perjalanan reguler, kebutuhan operasional dasar sudah diperhitungkan pada tarif harian. Untuk rute khusus/luar area layanan, komponen tersebut dirinci di penawaran agar tidak ada kejutan biaya.", "For regular trips, basic operational needs are already factored into the daily rate. For special routes or outside our service area, these items are itemised in the offer so there are no surprises.", lang) },
    { q: bi(`Kenapa harus DP ${dp}%?`, `Why a ${dp}% deposit?`, lang), a: bi(`DP mengunci unit dan tanggal Anda supaya tidak diambil pemesan lain. Setelah pesanan dibuat, jadwal ditahan ${hold} jam untuk penyelesaian DP dan unggah bukti transfer; setelah diverifikasi tim ops, status berubah menjadi terkonfirmasi.`, `The deposit locks your unit and dates so no one else can take them. Once a booking is created, the schedule is held for ${hold} hours to complete the deposit and upload proof of transfer; after the ops team verifies it, the status becomes confirmed.`, lang) },
    { q: bi("Apakah estimasi ini harga final?", "Is this estimate the final price?", lang), a: bi("Estimasi bersifat indikatif untuk perencanaan. Harga final muncul saat Anda memilih unit pada halaman Pesan Online (dengan ketersediaan nyata) atau pada penawaran resmi yang dikirim tim kami.", "The estimate is indicative for planning. The final price appears when you pick a unit on the Book Online page (with real availability) or in the official offer our team sends.", lang) },
    { q: bi("Bagaimana kalau saya butuh lebih dari satu unit?", "What if I need more than one unit?", lang), a: bi("Silakan gunakan Minta Penawaran dan sebutkan jumlah rombongan. Kami akan menyusun kombinasi unit yang paling efisien beserta rinciannya.", "Please use Request a Quote and tell us your group size. We'll put together the most efficient combination of units with a full breakdown.", lang) },
  ];

  useSEO({
    title: bi("Kalkulator Estimasi Biaya Trip", "Trip Cost Estimator", lang),
    description: bi(
      `Hitung perkiraan biaya sewa armada berdasarkan tipe unit dan lama pemakaian. Tarif sama dengan yang dipakai saat memesan, cukup DP ${dp}% untuk mengamankan jadwal.`,
      `Estimate vehicle rental costs based on unit type and length of use. The same rates used at booking, with just a ${dp}% deposit to secure your schedule.`,
      lang,
    ),
    image: HERO,
    keywords: "kalkulator sewa hiace, estimasi biaya sewa bus, hitung biaya trip jawa bali",
  });

  return (
    <div>
      <CmsPageHero slug="trip-calculator" eyebrow={bi("Kalkulator", "Calculator", lang)} title={bi("Estimasi biaya trip, transparan", "Transparent trip cost estimates", lang)}
        subtitle={bi("Hitung perkiraan biaya sewa berdasarkan unit dan lama pemakaian — tarif yang sama dengan yang dipakai saat memesan.", "Estimate rental costs by unit and length of use — the same rates used when you book.", lang)}
        image={HERO}
        breadcrumb={[{ label: bi("Beranda", "Home", lang), to: "/" }, { label: bi("Kalkulator", "Calculator", lang) }]} />

      {/* CARA KERJA — dulu halaman ini langsung menyodorkan form, sehingga separuh layar
          kosong sebelum ada hasil dan pengunjung tidak tahu apakah angkanya bisa dipercaya. */}
      <section className="relative overflow-hidden">
        <div className="glow-orb h-72 w-72 right-[-40px] top-8" style={{ background: "hsla(var(--ring) / 0.12)" }} aria-hidden="true" />
        <div className="relative mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
          <SectionHeading center eyebrow={bi("Cara kerja", "How it works", lang)} title={bi("Kenapa estimasi ini bisa dipegang", "Why you can trust this estimate", lang)}
            subtitle={bi("Tiga aturan yang berlaku sama di kalkulator maupun saat pesanan benar-benar dibuat.", "Three rules that apply the same in the calculator and when a booking is actually made.", lang)} />
          <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3" data-testid="calc-how-it-works">
            {HOW.map((h, i) => (
              <Reveal key={h.t} delay={i * 0.07}>
                <GlassCard variant="premium" className="h-full p-6">
                  <span className="icon-chip h-12 w-12"><h.icon size={20} strokeWidth={1.8} /></span>
                  <h3 className="mt-5 font-fraunces text-lg leading-snug text-foreground">{h.t}</h3>
                  <p className="mt-2 text-[13.5px] leading-relaxed text-muted-foreground">{h.d}</p>
                </GlassCard>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 pb-14 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
          <form onSubmit={calc} className="card-premium rounded-2xl p-6" data-testid="calculator-form">
            <h2 className="flex items-center gap-2 font-fraunces text-2xl text-foreground"><Calculator size={20} /> {bi("Hitung Estimasi", "Calculate Estimate", lang)}</h2>
            <div className="mt-5 space-y-4">
              <div>
                <label className="text-[13px] font-semibold text-foreground">{bi("Tipe Unit", "Vehicle Type", lang)}</label>
                <Select value={form.vehicle_type} onValueChange={(v) => set("vehicle_type", v)}>
                  <SelectTrigger className="mt-1" data-testid="calc-vehicle-type"><SelectValue placeholder={bi("Pilih unit", "Choose a unit", lang)} /></SelectTrigger>
                  <SelectContent>
                    {(types.length ? types : [{ value: form.vehicle_type, label: bi("Memuat…", "Loading…", lang) }])
                      .map((t) => <SelectItem key={t.value} value={t.value} data-testid={`calc-vehicle-type-opt-${t.value}`}>{t.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="text-[13px] font-semibold text-foreground">{bi("Durasi (hari)", "Duration (days)", lang)}</label><input type="number" min="1" max="60" value={form.days} onChange={(e) => set("days", e.target.value)} className={inputCls} data-testid="calc-days" /></div>
                <div><label className="text-[13px] font-semibold text-foreground">{bi("Jumlah penumpang", "Passengers", lang)}</label><input type="number" min="1" max="60" value={form.pax} onChange={(e) => set("pax", e.target.value)} placeholder="10" className={inputCls} data-testid="calc-pax" /></div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="text-[13px] font-semibold text-foreground">{bi("Asal", "Origin", lang)}</label><input value={form.origin} onChange={(e) => set("origin", e.target.value)} placeholder="Bandung" className={inputCls} data-testid="calc-origin" /></div>
                <div><label className="text-[13px] font-semibold text-foreground">{bi("Tujuan", "Destination", lang)}</label><input value={form.destination} onChange={(e) => set("destination", e.target.value)} placeholder="Bromo" className={inputCls} data-testid="calc-destination" /></div>
              </div>
              <button type="submit" disabled={loading} className="cta-shine glow-focus flex w-full items-center justify-center gap-2 rounded-lg py-3 text-[14px] font-semibold text-primary-foreground shadow-[var(--shadow-lift)] transition hover:-translate-y-0.5 disabled:opacity-60" style={{ background: "var(--gradient-cta)" }} data-testid="calc-submit">
                {loading ? <Loader2 size={15} className="animate-spin" /> : <Calculator size={15} />} {bi("Hitung Estimasi", "Calculate Estimate", lang)}
              </button>
              <p className="flex items-start gap-2 text-[12px] leading-relaxed text-muted-foreground">
                <ShieldCheck size={13} className="mt-0.5 shrink-0" /> {bi("Tanpa perlu data pribadi. Nomor Anda baru diminta saat benar-benar memesan.", "No personal data needed. We only ask for your number when you actually book.", lang)}
              </p>
            </div>
          </form>

          <div className="glass rounded-2xl p-6" data-testid="calculator-result">
            <h3 className="font-fraunces text-2xl text-foreground">{bi("Rincian Estimasi", "Estimate Breakdown", lang)}</h3>
            {!result ? (
              /* EMPTY STATE yang tetap berguna: bukan sekadar ikon abu-abu, tapi tarif nyata
                 per tipe + kebijakan DP supaya pengunjung dapat sesuatu sebelum menghitung. */
              <div data-testid="calc-empty">
                <p className="mt-2 text-[13.5px] leading-relaxed text-muted-foreground">
                  {bi("Belum ada hasil — isi formulir lalu klik Hitung. Sementara itu, ini tarif awal yang berlaku hari ini:", "No result yet — fill in the form and click Calculate. Meanwhile, here are today's starting rates:", lang)}
                </p>
                {cfgLoading ? (
                  <div className="mt-4 space-y-2" data-testid="calc-empty-loading">
                    {Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-11 animate-pulse rounded-lg bg-muted" />)}
                  </div>
                ) : types.length === 0 ? (
                  <p className="mt-4 rounded-lg border border-dashed border-border px-3 py-6 text-center text-[13px] text-muted-foreground">
                    {bi("Belum ada tipe unit dengan tarif aktif. Silakan minta penawaran khusus.", "No unit types with active rates yet. Please request a custom quote.", lang)}
                  </p>
                ) : (
                  <div className="mt-4 divide-y divide-border" data-testid="calc-empty-rates">
                    {types.map((t) => (
                      <button
                        key={t.value}
                        type="button"
                        onClick={() => set("vehicle_type", t.value)}
                        data-testid={`calc-rate-${t.value}`}
                        className="flex w-full items-center justify-between gap-3 py-3 text-left transition hover:opacity-80"
                      >
                        <span>
                          <span className="block text-[13.5px] font-semibold text-foreground">{t.label}</span>
                          <span className="block text-[11.5px] tabular-nums text-muted-foreground">{bi("sampai", "up to", lang)} {t.max_capacity} {bi("penumpang", "passengers", lang)} · {t.units} unit</span>
                        </span>
                        <span className="shrink-0 text-right">
                          <span className="block font-mono text-[14px] font-semibold tabular-nums text-foreground">{formatCurrency(t.from_price)}</span>
                          <span className="block text-[11px] text-muted-foreground">/{bi("hari", "day", lang)}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                )}
                <p className="mt-4 flex items-start gap-2 rounded-lg bg-secondary px-3 py-2.5 text-[12px] leading-relaxed text-secondary-foreground">
                  <Lightbulb size={13} className="mt-0.5 shrink-0" /> {bi("Tip: klik salah satu baris untuk memakai tipe itu di formulir.", "Tip: click a row to use that type in the form.", lang)}
                </p>
              </div>
            ) : (
              <div className="mt-4">
                <div className="divide-y divide-border">
                  {result.breakdown.map((b, i) => (
                    <div key={i} className="flex items-center justify-between py-3 text-[14px]"><span className="text-muted-foreground">{b.label}</span><span className="font-mono font-semibold tabular-nums text-foreground">{formatCurrency(b.amount)}</span></div>
                  ))}
                </div>
                <div className="mt-3 flex items-center justify-between rounded-xl px-4 py-3.5 text-primary-foreground" style={{ background: "var(--gradient-cta)" }}><span className="text-[13.5px] font-medium opacity-90">{bi("Estimasi Total", "Estimated Total", lang)}</span><span className="font-mono text-2xl font-semibold tabular-nums" data-testid="calc-total">{formatCurrency(result.total)}</span></div>
                <div className="mt-3 flex items-center justify-between rounded-xl border border-border bg-secondary px-4 py-3 text-[13px]">
                  <span className="font-medium text-secondary-foreground">{bi(`Perkiraan DP ${dp}%`, `Estimated deposit ${dp}%`, lang)}</span>
                  <span className="font-mono font-semibold tabular-nums text-foreground" data-testid="calc-dp">{formatCurrency(Math.round((result.total * dp) / 100))}</span>
                </div>
                <p className="mt-3 flex items-start gap-2 text-[12px] leading-relaxed text-muted-foreground"><Info size={14} className="mt-0.5 flex-shrink-0" /> {result.note}</p>
                <Link to={`/booking?type=${encodeURIComponent(form.vehicle_type)}&destination=${encodeURIComponent(form.destination || "")}`} className="cta-shine mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg py-3 text-[14px] font-semibold text-primary-foreground transition hover:opacity-90" style={{ background: "var(--gradient-cta)" }} data-testid="calc-to-booking">{bi("Cek Ketersediaan & Pesan", "Check Availability & Book", lang)} <ArrowRight size={15} /></Link>
                <Link to="/quotation" state={{ destination: form.destination, message: bi(`Estimasi total ${formatCurrency(result.total)} untuk ${result.days} hari`, `Estimated total ${formatCurrency(result.total)} for ${result.days} days`, lang) }} className="mt-2 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-card py-2.5 text-[13px] font-semibold text-foreground" data-testid="calc-to-quote">{bi("Minta Penawaran Khusus", "Request a Custom Quote", lang)}</Link>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* TARIF PER TIPE (data nyata) */}
      <VehicleTypeCompare
        types={types}
        loading={cfgLoading}
        error={cfgError}
        dpPercent={dp}
        eyebrow={bi("Tarif berlaku", "Current rates", lang)}
        title={bi("Tarif awal per tipe unit", "Starting rates per unit type", lang)}
        subtitle={bi("Angka inilah yang dipakai kalkulator dan mesin pemesanan — sama, tanpa versi berbeda untuk brosur.", "These are the numbers used by both the calculator and the booking engine — the same, with no separate brochure version.", lang)}
      />

      {/* ANTAR-JEMPUT: tarif FLAT, bukan per hari — sering disalahpahami di kalkulator */}
      <AirportRouteStrip routes={config?.routes} loading={cfgLoading} error={cfgError} />

      {/* PROMO yang bisa dipakai */}
      <PromoStrip dpPercent={dp} eyebrow={bi("Promo", "Deals", lang)} title={bi("Bisa menurunkan estimasi Anda", "Can lower your estimate", lang)} subtitle={bi("Masukkan kodenya saat memesan online — sistem yang memverifikasi kelayakannya.", "Enter the code when booking online — the system verifies eligibility.", lang)} />

      <FaqBlock items={FAQS} testId="calc-faq" eyebrow={bi("FAQ Harga", "Pricing FAQ", lang)} title={bi("Pertanyaan seputar biaya", "Questions about cost", lang)} />

      <section className="mx-auto max-w-7xl px-4 pb-24 sm:px-6 lg:px-8">
        <CtaBand
          testId="calc-cta-band"
          eyebrow={bi("Langkah berikutnya", "Next step", lang)}
          title={bi("Sudah cocok dengan estimasinya?", "Happy with the estimate?", lang)}
          subtitle={bi("Lanjut ke pemesanan online untuk melihat unit yang benar-benar tersedia pada tanggal Anda beserta harga finalnya.", "Continue to online booking to see the units actually available on your dates and their final price.", lang)}
          note={bi(`DP ${dp}% · jadwal ditahan ${hold} jam`, `${dp}% deposit · schedule held ${hold} hours`, lang)}
          primary={{ to: "/booking", label: bi("Cek Ketersediaan", "Check Availability", lang), icon: CalendarCheck, testId: "calc-cta-booking" }}
          secondary={{ to: "/quotation", label: bi("Minta Penawaran", "Request a Quote", lang), icon: MessageCircle, testId: "calc-cta-quotation" }}
        />
      </section>
    </div>
  );
}
