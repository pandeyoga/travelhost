import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Loader2, SearchX, Sparkles } from "lucide-react";
import { toast } from "sonner";
import PageHero from "@/components/public/PageHero";
import StepIndicator from "@/components/public/booking/StepIndicator";
import BookingSearchForm, { defaultSearchState } from "@/components/public/booking/BookingSearchForm";
import UnitOptionCard, { UnavailableUnitRow } from "@/components/public/booking/UnitOptionCard";
import QuoteBreakdown from "@/components/public/booking/QuoteBreakdown";
import BookerForm from "@/components/public/booking/BookerForm";
import { formatCurrency, formatDateTime } from "@/utils/formatters";
import { getAttribution } from "@/utils/attribution";
import { trackBeginCheckout, trackLead } from "@/lib/tracking";
import {
  SERVICE_TRANSFER, getBookingConfig, getQuote, newIdempotencyKey, rememberBooking,
  searchUnits, submitBooking,
} from "@/services/bookingApi";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

// BookingWizard — alur pemesanan online 3 langkah: Cari → Pilih Unit → Data & Konfirmasi.
//
// Kenapa wizard (bukan satu formulir panjang seperti sebelumnya): pengunjung baru boleh
// memasukkan data pribadi SETELAH melihat unit yang benar-benar tersedia beserta harga
// finalnya.

export default function BookingWizard() {
  const lang = useLangValue();
  const STEPS = [
    bi("Cari", "Search", lang),
    bi("Pilih Unit", "Choose Unit", lang),
    bi("Data & Konfirmasi", "Details & Confirm", lang),
  ];
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [config, setConfig] = useState(null);
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [configError, setConfigError] = useState("");
  const [search, setSearch] = useState(null);
  const [step, setStep] = useState(0);
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState(null);
  const [picked, setPicked] = useState(null);
  const [quote, setQuote] = useState(null);
  const [promo, setPromo] = useState({ code: "", error: "" });
  const [applying, setApplying] = useState(false);
  const [booker, setBooker] = useState({ name: "", phone: "", email: "", pickup_address: "", message: "", hp: "" });
  const [consent, setConsent] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [idemKey] = useState(newIdempotencyKey);

  const loadConfig = useCallback(async () => {
    setLoadingConfig(true);
    setConfigError("");
    try {
      const cfg = await getBookingConfig();
      setConfig(cfg);
      const base = defaultSearchState(cfg);
      const wanted = params.get("service");
      const type = params.get("type");
      const routeId = params.get("route");
      const routeValid = (cfg.routes || []).some((r) => r.id === routeId);
      setSearch({
        ...base,
        service: (cfg.services || []).some((s) => s.value === wanted)
          ? wanted
          : (routeValid ? SERVICE_TRANSFER : base.service),
        vehicle_type: type || base.vehicle_type,
        route_id: routeValid ? routeId : base.route_id,
        destination: params.get("destination") || base.destination,
      });
    } catch (e) {
      setConfigError(e?.response?.data?.detail || bi("Gagal memuat pilihan layanan.", "Failed to load service options.", lang));
    } finally { setLoadingConfig(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  useEffect(() => { loadConfig(); }, [loadConfig]);
  useEffect(() => { trackBeginCheckout({ value: 0 }); }, []);

  const isTransfer = search?.service === SERVICE_TRANSFER;
  const activeRoute = useMemo(
    () => (config?.routes || []).find((r) => r.id === search?.route_id) || null,
    [config, search?.route_id]);

  const searchPayload = useCallback((extra = {}) => ({
    service: search.service,
    start_datetime: new Date(search.start).toISOString(),
    end_datetime: isTransfer ? "" : new Date(search.end).toISOString(),
    pax: Number(search.pax) || 1,
    vehicle_type: isTransfer ? "" : (search.vehicle_type || ""),
    route_id: isTransfer ? search.route_id : "",
    origin: search.origin || "",
    destination: search.destination || "",
    ...extra,
  }), [search, isTransfer]);

  const runSearch = async () => {
    if (!search?.start || (!isTransfer && !search?.end)) {
      toast.error(bi("Lengkapi tanggal & jam perjalanan", "Complete the travel date & time", lang)); return;
    }
    if (isTransfer && !search.route_id) { toast.error(bi("Pilih rute antar-jemput", "Choose a transfer route", lang)); return; }
    setSearching(true);
    try {
      const data = await searchUnits(searchPayload({ promo_code: promo.code || "" }));
      setResult(data);
      setPicked(null);
      setQuote(null);
      setStep(1);
      if (data?.promo?.error) setPromo((p) => ({ ...p, error: data.promo.error }));
    } catch (e) {
      toast.error(e?.response?.data?.detail || bi("Pencarian gagal. Periksa tanggal Anda.", "Search failed. Please check your dates.", lang));
    } finally { setSearching(false); }
  };

  const pickUnit = async (option, code = promo.code) => {
    setPicked(option);
    setQuote(option.quote);
    setStep(2);
    try {
      const data = await getQuote({
        service: search.service, vehicle_id: option.vehicle.id,
        start_datetime: new Date(search.start).toISOString(),
        end_datetime: isTransfer ? "" : new Date(search.end).toISOString(),
        route_id: isTransfer ? search.route_id : "",
        pax: Number(search.pax) || 1, promo_code: code || "",
      });
      setQuote(data.quote);
      setPromo((p) => ({ ...p, error: "" }));
    } catch (e) {
      if (code) {
        setPromo({ code: "", error: e?.response?.data?.detail || bi("Kode promo tidak bisa dipakai.", "This promo code cannot be used.", lang) });
        if (code !== "") pickUnit(option, "");
      } else {
        toast.error(e?.response?.data?.detail || bi("Gagal menghitung harga", "Failed to calculate the price", lang));
      }
    }
  };

  const applyPromo = async (code) => {
    if (!picked) return;
    setApplying(true);
    setPromo({ code, error: "" });
    await pickUnit(picked, code);
    setApplying(false);
  };

  const clearPromo = async () => {
    setPromo({ code: "", error: "" });
    if (picked) await pickUnit(picked, "");
  };

  const submit = async () => {
    if (!picked) { toast.error(bi("Pilih unit dulu", "Pick a unit first", lang)); return; }
    if (!booker.name.trim() || !booker.phone.trim()) {
      toast.error(bi("Nama & nomor WhatsApp wajib diisi", "Name & WhatsApp number are required", lang)); return;
    }
    setSubmitting(true);
    try {
      const res = await submitBooking({
        service: search.service, vehicle_id: picked.vehicle.id,
        route_id: isTransfer ? search.route_id : "",
        start_datetime: new Date(search.start).toISOString(),
        end_datetime: isTransfer ? "" : new Date(search.end).toISOString(),
        pax: Number(search.pax) || 1,
        name: booker.name.trim(), phone: booker.phone.trim(), email: booker.email,
        origin: search.origin, destination: search.destination,
        pickup_address: booker.pickup_address, message: booker.message,
        promo_code: promo.code || "", marketing_consent: consent,
        attribution: getAttribution(), idempotency_key: idemKey, hp: booker.hp,
      });
      if (!res?.code) { toast.error(bi("Pesanan tidak tersimpan. Coba lagi.", "Booking was not saved. Please try again.", lang)); return; }
      rememberBooking({ code: res.code, token: res.token });
      trackLead({ eventKey: `booking_${res.code}`, source: "booking_online" });
      toast.success(res.message || bi("Pesanan dibuat", "Booking created", lang));
      navigate(`/booking/status?code=${encodeURIComponent(res.code)}&token=${encodeURIComponent(res.token)}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || bi("Gagal membuat pesanan", "Failed to create the booking", lang));
    } finally { setSubmitting(false); }
  };

  const options = result?.options || [];
  const unavailable = result?.unavailable || [];
  const tripLabel = isTransfer
    ? (activeRoute?.name || "")
    : (search?.origin && search?.destination
      ? `${search.origin} → ${search.destination}`
      : search?.origin ? bi(`Dari ${search.origin}`, `From ${search.origin}`, lang)
        : search?.destination ? bi(`Menuju ${search.destination}`, `To ${search.destination}`, lang) : "");
  const dpNote = quote?.dp_amount
    ? (config?.mode === "hold_dp"
      ? bi(
          `Unit ditahan untuk Anda setelah pesanan dibuat. Bayar DP ${formatCurrency(quote.dp_amount)} dalam ${config?.hold_hours || 2} jam, lalu unggah bukti transfer.`,
          `The unit is held for you once the booking is created. Pay a ${formatCurrency(quote.dp_amount)} deposit within ${config?.hold_hours || 2} hours, then upload proof of transfer.`,
          lang,
        )
      : bi(
          `Tim kami memeriksa ketersediaan lebih dulu (maks ${config?.approval_sla_hours || 6} jam kerja). Setelah disetujui, Anda diminta membayar DP ${formatCurrency(quote.dp_amount)}.`,
          `Our team checks availability first (max ${config?.approval_sla_hours || 6} business hours). Once approved, you'll be asked to pay a ${formatCurrency(quote.dp_amount)} deposit.`,
          lang,
        ))
    : "";

  return (
    <div>
      <PageHero eyebrow={bi("Pesan Online", "Book Online", lang)} title={bi("Pesan armada, langsung dapat kode booking", "Book a vehicle and get a booking code instantly", lang)}
        subtitle={bi("Cek ketersediaan nyata, lihat harga final, dan amankan unit Anda — tanpa menunggu balasan chat.", "Check real availability, see the final price, and secure your unit — without waiting for a chat reply.", lang)}
        image="https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?q=80&w=2000&auto=format&fit=crop"
        breadcrumb={[{ label: bi("Beranda", "Home", lang), to: "/" }, { label: bi("Pesan Online", "Book Online", lang) }]} />

      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <StepIndicator steps={STEPS} current={step} onJump={setStep} />

        {loadingConfig ? (
          <div className="mt-8 flex items-center justify-center gap-2 rounded-2xl border border-border bg-card py-20 text-muted-foreground"
            data-testid="booking-config-loading">
            <Loader2 size={18} className="animate-spin" /> {bi("Menyiapkan pilihan layanan…", "Preparing service options…", lang)}
          </div>
        ) : configError ? (
          <div className="mt-8 rounded-2xl border border-border bg-card p-8 text-center" data-testid="booking-config-error">
            <p className="text-[14px] text-foreground">{configError}</p>
            <button onClick={loadConfig} className="mt-3 rounded-lg border border-border px-4 py-2 text-[13px] font-semibold"
              data-testid="booking-config-retry">{bi("Coba lagi", "Try again", lang)}</button>
          </div>
        ) : (
          <div className="mt-6">
            {step === 0 ? (
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.2fr_.8fr]">
                <BookingSearchForm config={config} value={search} onChange={setSearch}
                  onSubmit={runSearch} loading={searching} />
                <aside className="glass rounded-2xl p-6" data-testid="booking-why">
                  <h3 className="flex items-center gap-2 font-fraunces text-xl text-foreground">
                    <Sparkles size={17} className="text-primary" /> {bi("Kenapa pesan di sini", "Why book here", lang)}
                  </h3>
                  <ul className="mt-4 space-y-3 text-[13.5px] leading-relaxed tabular-nums text-muted-foreground">
                    <li><b className="text-foreground">{bi("Ketersediaan nyata.", "Real availability.", lang)}</b> {bi("Yang tampil hanya unit yang benar-benar bebas pada tanggal Anda.", "Only units that are truly free on your dates are shown.", lang)}</li>
                    <li><b className="text-foreground">{bi("Harga final & terbuka.", "Final & transparent price.", lang)}</b> {bi("Sudah termasuk driver, tol & parkir — rinciannya dapat Anda lihat sebelum bayar.", "Includes driver, tolls & parking — you can see the breakdown before paying.", lang)}</li>
                    <li><b className="text-foreground">{bi(`DP ${config?.dp_percent || 30}% saja.`, `Only ${config?.dp_percent || 30}% deposit.`, lang)}</b> {bi("Sisanya dilunasi mendekati keberangkatan.", "The rest is settled close to departure.", lang)}</li>
                    <li><b className="text-foreground">{bi("Tanpa buat akun.", "No account needed.", lang)}</b> {bi("Cek pesanan pakai kode booking + nomor WhatsApp.", "Track your booking with the booking code + WhatsApp number.", lang)}</li>
                  </ul>
                  {config?.terms ? (
                    <p className="mt-4 border-t border-border pt-3 text-[12px] leading-relaxed text-muted-foreground">
                      {config.terms}
                    </p>
                  ) : null}
                </aside>
              </div>
            ) : null}

            {step === 1 ? (
              <div>
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-card px-5 py-4">
                  <div>
                    <p className="text-[12px] uppercase tracking-wide text-muted-foreground">{bi("Pencarian Anda", "Your search", lang)}</p>
                    <p className="text-[14px] font-semibold text-foreground">
                      {isTransfer ? (activeRoute?.name || bi("Antar-jemput bandara", "Airport transfer", lang)) : bi("Sewa harian + driver", "Daily rental + driver", lang)}
                      {" · "}{formatDateTime(search.start)}
                      {!isTransfer ? ` → ${formatDateTime(search.end)}` : ""}
                      {` · ${search.pax} ${bi("orang", "people", lang)}`}
                    </p>
                  </div>
                  <button onClick={() => setStep(0)} data-testid="booking-change-search"
                    className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3.5 py-2 text-[13px] font-semibold text-foreground transition hover:-translate-y-0.5">
                    <ArrowLeft size={14} /> {bi("Ubah pencarian", "Change search", lang)}
                  </button>
                </div>

                {searching ? (
                  <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3" data-testid="booking-results-loading">
                    {[0, 1, 2].map((i) => (
                      <div key={i} className="h-72 animate-pulse rounded-2xl border border-border bg-secondary" />
                    ))}
                  </div>
                ) : options.length === 0 ? (
                  <div className="mt-6 rounded-2xl border border-border bg-card px-6 py-16 text-center" data-testid="booking-results-empty">
                    <SearchX size={30} className="mx-auto mb-3 text-muted-foreground" />
                    <h3 className="font-fraunces text-2xl text-foreground">{bi("Tidak ada unit bebas di tanggal itu", "No units are free on those dates", lang)}</h3>
                    <p className="mx-auto mt-2 max-w-md text-[13.5px] text-muted-foreground">
                      {bi("Semua unit yang cocok sudah dipesan atau sedang perawatan. Coba geser tanggal, kurangi jumlah penumpang, atau minta penawaran khusus — kami bisa mencarikan unit mitra.", "All matching units are booked or under maintenance. Try shifting the dates, reducing passengers, or request a custom quote — we can source a partner unit.", lang)}
                    </p>
                    <div className="mt-4 flex flex-wrap justify-center gap-2">
                      <button onClick={() => setStep(0)} className="rounded-lg border border-border px-4 py-2.5 text-[13px] font-semibold text-foreground"
                        data-testid="booking-empty-back">{bi("Ubah tanggal", "Change dates", lang)}</button>
                      <a href="/quotation" className="cta-shine rounded-lg px-4 py-2.5 text-[13px] font-semibold text-primary-foreground"
                        style={{ background: "var(--gradient-cta)" }} data-testid="booking-empty-quote">{bi("Minta penawaran khusus", "Request a custom quote", lang)}</a>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="mt-6 text-[13px] text-muted-foreground" data-testid="booking-results-count">
                      <b className="text-foreground">{options.length} unit</b> {bi("tersedia · harga sudah final untuk tanggal ini", "available · prices are final for these dates", lang)}
                    </p>
                    <div className="mt-3 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3" data-testid="booking-results">
                      {options.map((o) => (
                        <UnitOptionCard key={o.vehicle.id} option={o} onPick={pickUnit}
                          picked={picked?.vehicle?.id === o.vehicle.id} />
                      ))}
                    </div>
                  </>
                )}

                {unavailable.length ? (
                  <div className="mt-8">
                    <p className="text-[12.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                      {bi("Tidak tersedia di tanggal ini", "Not available on these dates", lang)}
                    </p>
                    <div className="mt-2 space-y-2">
                      {unavailable.map((u) => <UnavailableUnitRow item={u} key={u.id} />)}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}

            {step === 2 && picked ? (
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.15fr_.85fr]">
                <div className="space-y-4">
                  <div className="rounded-2xl border border-border bg-card p-5" data-testid="booking-summary">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-[12px] uppercase tracking-wide text-muted-foreground">{bi("Unit dipilih", "Selected unit", lang)}</p>
                        <h3 className="font-fraunces text-xl text-foreground">{picked.vehicle.name}</h3>
                        <p className="mt-0.5 text-[12.5px] text-muted-foreground">
                          {picked.vehicle.type_label} · {picked.vehicle.capacity} {bi("kursi", "seats", lang)}
                        </p>
                      </div>
                      <button onClick={() => setStep(1)} data-testid="booking-change-unit"
                        className="rounded-lg border border-border px-3 py-1.5 text-[12.5px] font-semibold text-foreground">
                        {bi("Ganti unit", "Change unit", lang)}
                      </button>
                    </div>
                    <dl className="mt-4 grid grid-cols-2 gap-3 text-[13px]">
                      {tripLabel ? (
                        <div><dt className="text-muted-foreground">{isTransfer ? bi("Rute", "Route", lang) : bi("Perjalanan", "Trip", lang)}</dt>
                          <dd className="font-medium text-foreground" data-testid="booking-summary-trip">
                            {tripLabel}
                          </dd></div>
                      ) : null}
                      <div><dt className="text-muted-foreground">{bi("Penumpang", "Passengers", lang)}</dt>
                        <dd className="font-medium text-foreground">{search.pax} {bi("orang", "people", lang)}</dd></div>
                      <div><dt className="text-muted-foreground">{isTransfer ? bi("Penjemputan", "Pickup", lang) : bi("Mulai", "Start", lang)}</dt>
                        <dd className="font-medium text-foreground">{formatDateTime(search.start)}</dd></div>
                      {!isTransfer ? (
                        <div><dt className="text-muted-foreground">{bi("Selesai", "End", lang)}</dt>
                          <dd className="font-medium text-foreground">{formatDateTime(search.end)}</dd></div>
                      ) : null}
                    </dl>
                  </div>
                  <BookerForm value={booker} onChange={setBooker} onSubmit={submit} submitting={submitting}
                    consent={consent} onConsent={setConsent} showPickup
                    ctaLabel={config?.mode === "hold_dp" ? bi("Amankan unit & lanjut bayar DP", "Secure unit & continue to deposit", lang) : bi("Kirim pesanan untuk dikonfirmasi", "Submit booking for confirmation", lang)}
                    note={bi("Dengan menekan tombol ini Anda menyetujui ketentuan layanan & kebijakan pembatalan.", "By pressing this button you agree to the terms of service & cancellation policy.", lang)} />
                </div>
                <div className="space-y-4 lg:sticky lg:top-24 lg:self-start">
                  <QuoteBreakdown quote={quote} promo={promo} onApplyPromo={applyPromo}
                    onClearPromo={clearPromo} applying={applying}
                    promoContext={picked ? {
                      service: search.service, vehicle_id: picked.vehicle.id,
                      start_datetime: new Date(search.start).toISOString(),
                      end_datetime: isTransfer ? "" : new Date(search.end).toISOString(),
                      route_id: isTransfer ? search.route_id : "",
                      pax: Number(search.pax) || 1,
                    } : null}
                    policy={config?.cancellation_policy} dpNote={dpNote} />
                </div>
              </div>
            ) : null}

            {step === 2 && !picked ? (
              <div className="rounded-2xl border border-border bg-card px-6 py-14 text-center" data-testid="booking-no-pick">
                <p className="text-[14px] text-muted-foreground">{bi("Belum ada unit dipilih.", "No unit selected yet.", lang)}</p>
                <button onClick={() => setStep(0)} className="mt-3 rounded-lg border border-border px-4 py-2 text-[13px] font-semibold"
                  data-testid="booking-no-pick-back">{bi("Mulai pencarian", "Start searching", lang)}</button>
              </div>
            ) : null}
          </div>
        )}
      </section>
    </div>
  );
}
