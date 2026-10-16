import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Calculator, Loader2, ArrowRight, MessageCircle, Info } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import apiClient from "@/services/apiClient";
import { formatCurrency } from "@/utils/formatters";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";
import { useSiteFeatures } from "@/hooks/useSiteFeatures";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";

const TYPES = [
  { v: "hiace_premio", l: "Hiace Premio (14)" },
  { v: "hiace", l: "Hiace Commuter (14)" },
  { v: "elf", l: "Isuzu Elf (19)" },
  { v: "bus", l: "Medium Bus (29)" },
  { v: "avanza", l: "Avanza / MPV (6)" },
];

function useCountUp(target, active, reduce) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (!active) return undefined;
    if (reduce) { setVal(target); return undefined; }
    let raf;
    const start = performance.now();
    const dur = 900;
    const tick = (now) => {
      const p = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setVal(target * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, active, reduce]);
  return val;
}

// TripEstimatorInline.jsx — widget estimasi inline (Home/Fleet/Destinasi).
// POST /public/trip-estimate. Breakdown + total count-up + DP + CTA penawaran/WA.
export const TripEstimatorInline = (props) => {
  const { tripCalculator } = useSiteFeatures();
  if (!tripCalculator) return null;
  return <TripEstimatorInlineBody {...props} />;
};

const TripEstimatorInlineBody = ({
  idPrefix = "hero-trip-estimator",
  defaultDestination = "",
  defaultVehicleType = "",
  waNumber = "6281120003000",
  className = "",
}) => {
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const lang = useLangValue();
  const [form, setForm] = useState({
    vehicle_type: defaultVehicleType || "hiace_premio",
    days: 2,
    destination: defaultDestination,
    pax: "",
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const liveRef = useRef(null);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const total = useCountUp(result?.total || 0, Boolean(result), reduce);

  useEffect(() => {
    if (defaultDestination) setForm((f) => ({ ...f, destination: defaultDestination }));
  }, [defaultDestination]);

  useEffect(() => {
    if (defaultVehicleType) setForm((f) => ({ ...f, vehicle_type: defaultVehicleType }));
  }, [defaultVehicleType]);

  const calc = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const { data } = await apiClient.post("/public/trip-estimate", {
        vehicle_type: form.vehicle_type,
        days: Number(form.days) || 1,
        destination: form.destination,
        pax: Number(form.pax) || 1,
      });
      setResult(data);
    } catch (err) {
      setError(bi("Gagal menghitung estimasi. Coba lagi sebentar lagi.", "Failed to calculate the estimate. Please try again shortly.", lang));
    } finally {
      setLoading(false);
    }
  };

  const waLink = `https://wa.me/${waNumber}?text=${encodeURIComponent(
    bi(
      `Halo RahazaTrans, saya tertarik trip ke ${form.destination || "destinasi pilihan"}` +
        (result ? ` (estimasi ${formatCurrency(result.total)} / ${result.days} hari).` : "."),
      `Hello RahazaTrans, I'm interested in a trip to ${form.destination || "a destination of my choice"}` +
        (result ? ` (estimate ${formatCurrency(result.total)} / ${result.days} days).` : "."),
      lang
    )
  )}`;

  return (
    // `glass-on-hero`: kartu ini hampir selalu duduk DI ATAS FOTO hero yang terang, jadi
    // base-nya harus pekat (bukan kaca 0,62) supaya label & placeholder tetap terbaca.
    <div className={`glass-3d glass-bevel glass-on-hero rounded-2xl p-5 sm:p-6 ${className}`} data-testid={idPrefix}>
      <h3 className="flex items-center gap-2 font-fraunces text-xl text-foreground">
        <Calculator size={18} className="text-primary" /> {bi("Hitung Estimasi Trip", "Estimate Your Trip", lang)}
      </h3>
      <p className="mt-1 text-[12.5px] text-muted-foreground">{bi("Perkiraan indikatif langsung di halaman ini.", "An indicative estimate, right here on this page.", lang)}</p>
      <form onSubmit={calc} className="mt-4 space-y-3.5">
        <div>
          <label className="text-[12px] font-semibold text-foreground">{bi("Destinasi", "Destination", lang)}</label>
          <input
            value={form.destination}
            onChange={(e) => set("destination", e.target.value)}
            placeholder={bi("mis. Bromo, Bali", "e.g. Bromo, Bali", lang)}
            data-testid={`${idPrefix}-destination`}
            className="mt-1 w-full rounded-lg border border-input bg-background/90 px-3 py-2.5 text-[14px] text-foreground outline-none transition placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/30"
          />
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="flex-1">
            <label className="text-[12px] font-semibold text-foreground">{bi("Tipe Armada", "Vehicle Type", lang)}</label>
            <Select value={form.vehicle_type} onValueChange={(v) => set("vehicle_type", v)}>
              <SelectTrigger className="mt-1 bg-background/90" data-testid={`${idPrefix}-vehicle`}>
                <SelectValue placeholder={bi("Pilih armada", "Choose a vehicle", lang)} />
              </SelectTrigger>
              <SelectContent>
                {TYPES.map((t) => (
                  <SelectItem key={t.v} value={t.v}>{t.l}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="w-full sm:w-28">
            <label className="text-[12px] font-semibold text-foreground">{bi("Durasi (hari)", "Days", lang)}</label>
            <div className="mt-1 flex items-center rounded-lg border border-input bg-background/90">
              <button type="button" onClick={() => set("days", Math.max(1, Number(form.days) - 1))} data-testid={`${idPrefix}-days-dec`} className="px-3 py-2.5 text-foreground/70 transition hover:text-foreground">−</button>
              <span className="flex-1 text-center font-mono text-[14px] tabular-nums text-foreground" data-testid={`${idPrefix}-days-value`}>{form.days}</span>
              <button type="button" onClick={() => set("days", Math.min(30, Number(form.days) + 1))} data-testid={`${idPrefix}-days-inc`} className="px-3 py-2.5 text-foreground/70 transition hover:text-foreground">+</button>
            </div>
          </div>
        </div>
        {/* Penggeser "perkiraan jarak" DIHAPUS: dulu angka km diisi pengunjung lalu dikalikan
            tarif BBM, jadi harga bergantung pada tebakan orang yang belum tahu rutenya.
            Sejak Pricing Engine v2 harga digerakkan JUMLAH HARI (lihat services/pricing.py). */}
        <button
          type="submit"
          disabled={loading}
          data-testid={`${idPrefix}-submit`}
          className="cta-shine glow-focus flex w-full items-center justify-center gap-2 rounded-lg py-3 text-[14px] font-semibold text-primary-foreground shadow-[var(--shadow-lift)] transition hover:-translate-y-0.5 disabled:opacity-60"
          style={{ background: "var(--gradient-cta)" }}
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Calculator size={16} />} {bi("Hitung Estimasi", "Calculate Estimate", lang)}
        </button>
      </form>

      <div className="mt-4" aria-live="polite" ref={liveRef} data-testid={`${idPrefix}-result`}>
        {error ? (
          <p className="rounded-lg bg-destructive/10 px-3 py-2 text-[12.5px] text-destructive" data-testid={`${idPrefix}-error`}>{error}</p>
        ) : !result ? (
          <p className="rounded-lg border border-dashed border-border px-3 py-3 text-center text-[12.5px] text-muted-foreground" data-testid={`${idPrefix}-empty`}>
            {bi("Belum ada estimasi — isi formulir lalu klik Hitung.", "No estimate yet — fill in the form and click Calculate.", lang)}
          </p>
        ) : (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
            <div className="space-y-1.5">
              {result.breakdown.slice(0, 4).map((b, i) => (
                <div key={i} className="flex items-center justify-between text-[12.5px]">
                  <span className="text-muted-foreground">{b.label}</span>
                  <span className="font-mono tabular-nums text-foreground">{formatCurrency(b.amount)}</span>
                </div>
              ))}
            </div>
            <div className="mt-3 flex items-center justify-between rounded-xl px-4 py-3 text-primary-foreground" style={{ background: "var(--gradient-cta)" }}>
              <span className="text-[12.5px] font-medium opacity-90">{bi("Estimasi Total", "Estimated Total", lang)}</span>
              <span className="font-mono text-xl font-semibold tabular-nums" data-testid={`${idPrefix}-total`}>{formatCurrency(total)}</span>
            </div>
            <p className="mt-2 flex items-start gap-1.5 text-[11.5px] leading-relaxed text-muted-foreground">
              <Info size={13} className="mt-0.5 flex-shrink-0" /> {result.note}
            </p>
            <div className="mt-3 flex gap-2">
              <Link
                to="/quotation"
                state={{ destination: form.destination, message: bi(`Estimasi ${formatCurrency(result.total)} untuk ${result.days} hari`, `Estimate ${formatCurrency(result.total)} for ${result.days} days`, lang) }}
                data-testid={`${idPrefix}-to-quote`}
                className="cta-shine flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-primary py-2.5 text-[13px] font-semibold text-primary-foreground transition hover:opacity-90"
              >
                {bi("Lanjut Penawaran", "Continue to Quote", lang)} <ArrowRight size={14} />
              </Link>
              <a
                href={waLink}
                target="_blank"
                rel="noreferrer"
                data-testid={`${idPrefix}-wa`}
                className="flex items-center justify-center gap-1.5 rounded-lg border border-border px-3 py-2.5 text-[13px] font-semibold text-foreground transition hover:bg-secondary"
              >
                <MessageCircle size={14} /> WA
              </a>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default TripEstimatorInline;
