import { useMemo, useState } from "react";
import { CheckCircle2, Loader2, Calculator, AlertCircle } from "lucide-react";
import axios from "axios";
import SelectField from "@/components/shared/SelectField";
import { formatCurrency } from "@/utils/formatters";
import { Btn, Field, Heading, Wrap, inputClass, btnRadius } from "@/components/app/landing/shared";

/**
 * blocks/ConversionBlocks.jsx — blok yang MENGHASILKAN uang: formulir lead, banner CTA,
 * tombol WhatsApp, dan kalkulator estimasi.
 *
 * Semuanya dulu hanya placeholder (kotak abu-abu bertuliskan nama field, tombol yang pindah
 * halaman). Untuk halaman tujuan iklan itu fatal: setiap langkah tambahan memangkas konversi,
 * jadi formulir HARUS bisa diisi & dikirim di tempat, dan estimasi harga HARUS memakai tarif
 * resmi ERP (bukan angka karangan) supaya pengunjung tidak merasa dibohongi saat penawaran datang.
 */
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const FIELD_META = {
  name: { label: "Nama lengkap", type: "text", placeholder: "mis. Budi Santoso" },
  phone: { label: "Nomor WhatsApp", type: "tel", placeholder: "08xxxxxxxxxx" },
  email: { label: "Email (opsional)", type: "email", placeholder: "nama@email.com" },
  origin: { label: "Titik jemput", type: "text", placeholder: "Alamat / hotel" },
  destination: { label: "Tujuan", type: "text", placeholder: "mis. Bromo" },
  start: { label: "Tanggal mulai", type: "date" },
  end: { label: "Tanggal selesai", type: "date" },
  pax: { label: "Jumlah orang", type: "number", placeholder: "mis. 12" },
  vehicle_type: { label: "Jenis unit", type: "select" },
  message: { label: "Catatan tambahan", type: "textarea", placeholder: "Rute, jam, permintaan khusus…" },
};

const digits = (v) => String(v || "").replace(/\D/g, "");

export function LeadForm({ p, theme, mode, fleet = [], onSubmit }) {
  const [values, setValues] = useState({});
  const [consent, setConsent] = useState(false);
  const [errors, setErrors] = useState({});
  const [state, setState] = useState("idle"); // idle | sending | done | error
  const [serverError, setServerError] = useState("");
  const preview = mode === "preview";
  const fields = p.fields?.length ? p.fields : ["name", "phone", "message"];

  const unitOptions = useMemo(() => {
    const seen = new Map();
    (fleet || []).forEach((v) => {
      const key = v.type || v.name;
      if (key && !seen.has(key)) seen.set(key, String(key).replace(/_/g, " "));
    });
    return [...seen].map(([value, label]) => ({ value, label }));
  }, [fleet]);

  const set = (k, v) => {
    setValues((s) => ({ ...s, [k]: v }));
    setErrors((e) => ({ ...e, [k]: "" }));
  };

  const validate = () => {
    const errs = {};
    if (String(values.name || "").trim().length < 2) errs.name = "Mohon isi nama Anda.";
    if (digits(values.phone).length < 8) errs.phone = "Nomor WhatsApp minimal 8 angka.";
    if (fields.includes("email") && values.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(values.email)) {
      errs.email = "Format email belum benar.";
    }
    if (p.require_consent !== false && !consent) errs.consent = "Mohon centang persetujuan.";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!validate()) return;
    if (preview) {
      setState("done");
      return;
    }
    setState("sending");
    setServerError("");
    try {
      await onSubmit?.({ ...values, marketing_consent: consent, hp: values.hp || "" });
      setState("done");
    } catch (err) {
      setServerError(err?.response?.data?.detail
        || "Pengiriman gagal. Mohon coba lagi atau hubungi kami via WhatsApp.");
      setState("error");
    }
  };

  if (state === "done") {
    return (
      <Wrap theme={theme}>
        <div className="mx-auto max-w-[640px] bg-white p-8 text-center shadow-sm"
          style={{ borderRadius: theme.radius }} data-testid="lp-lead-success">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full"
            style={{ background: `${theme.primary}18`, color: theme.primary }}>
            <CheckCircle2 size={26} />
          </span>
          <h2 className="mt-3 text-[19px] font-extrabold" style={{ color: theme.text }}>Permintaan terkirim</h2>
          <p className="mt-1.5 text-[13.5px] text-[#5B6472]">{p.success_text || "Terima kasih! Tim kami segera menghubungi Anda."}</p>
          {preview ? (
            <button type="button" onClick={() => setState("idle")} data-testid="lp-lead-reset"
              className="mt-4 text-[12.5px] font-bold underline" style={{ color: theme.primary }}>
              Ulangi pratinjau formulir
            </button>
          ) : null}
        </div>
      </Wrap>
    );
  }

  return (
    <Wrap theme={theme} id="formulir">
      <form onSubmit={submit} className="mx-auto max-w-[640px] bg-white p-5 shadow-sm"
        style={{ borderRadius: theme.radius }} data-testid="lp-lead-form" noValidate>
        <Heading title={p.title} subtitle={p.subtitle} theme={theme} />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {fields.map((f) => {
            const meta = FIELD_META[f] || { label: f, type: "text" };
            const wide = f === "message";
            return (
              <Field key={f} label={meta.label} error={errors[f]} wide={wide}>
                {meta.type === "textarea" ? (
                  <textarea id={`lp-lf-${f}`} rows={3} value={values[f] || ""} placeholder={meta.placeholder}
                    onChange={(e) => set(f, e.target.value)} data-testid={`lp-lf-${f}`}
                    className="w-full rounded-lg border border-[#D9DEE6] bg-white px-3 py-2 text-[13px] outline-none focus:border-[#0B7BD3]" />
                ) : meta.type === "select" ? (
                  <SelectField value={values[f] || ""} onChange={(v) => set(f, v)} className="w-full"
                    testId={`lp-lf-${f}`} placeholder="Pilih jenis unit"
                    options={unitOptions.length ? unitOptions : [{ value: "hiace", label: "Hiace" },
                      { value: "elf", label: "Elf" }, { value: "bus", label: "Bus" }]} />
                ) : (
                  <input id={`lp-lf-${f}`} type={meta.type} value={values[f] || ""}
                    placeholder={meta.placeholder} min={meta.type === "number" ? 1 : undefined}
                    onChange={(e) => set(f, e.target.value)} data-testid={`lp-lf-${f}`}
                    className={inputClass} />
                )}
              </Field>
            );
          })}
        </div>

        {/* honeypot: tersembunyi dari manusia, diisi bot → server membuang senyap */}
        <input type="text" tabIndex={-1} autoComplete="off" aria-hidden="true"
          value={values.hp || ""} onChange={(e) => set("hp", e.target.value)}
          className="pointer-events-none absolute h-0 w-0 opacity-0" />

        {p.require_consent !== false ? (
          <label className="mt-3 flex cursor-pointer items-start gap-2 text-[12px] text-[#4A5260]">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)}
              data-testid="lp-lf-consent" className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-[#0B7BD3]" />
            <span>{p.consent_text}</span>
          </label>
        ) : null}
        {errors.consent ? (
          <p className="mt-1 text-[11px] font-semibold text-[#C2261C]" data-testid="lp-lf-consent-error">{errors.consent}</p>
        ) : null}
        {serverError ? (
          <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-[#FDF2F1] p-2 text-[12px] font-semibold text-[#C2261C]"
            data-testid="lp-lf-error"><AlertCircle size={13} className="mt-0.5 shrink-0" /> {serverError}</p>
        ) : null}

        <button type="submit" disabled={state === "sending"} data-testid="lp-lead-submit"
          className="mt-4 inline-flex h-11 w-full items-center justify-center gap-2 text-[14px] font-bold text-white disabled:opacity-60"
          style={{ background: theme.primary, borderRadius: btnRadius(theme) }}>
          {state === "sending" ? <><Loader2 size={15} className="animate-spin" /> Mengirim…</> : (p.submit_label || "Kirim")}
        </button>
      </form>
    </Wrap>
  );
}

export function CtaBand({ p, theme, onCta }) {
  const dark = p.tone !== "light";
  return (
    <section className="px-5 py-9" data-testid="lp-cta-band"
      style={{ background: dark ? theme.primary : "#FFFFFF" }}>
      <div className="mx-auto flex max-w-[1120px] flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-[20px] font-extrabold" style={{ color: dark ? "#FFFFFF" : theme.text }}>{p.title}</h2>
          {p.text ? (
            <p className="mt-1 text-[13.5px]" style={{ color: dark ? "rgba(255,255,255,.9)" : "#5B6472" }}>{p.text}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {(p.ctas || []).map((c, i) => (
            <button key={i} type="button" onClick={() => onCta?.(c)} data-testid={`lp-band-cta-${i}`}
              className="inline-flex h-11 items-center px-5 text-[14px] font-bold"
              style={{ background: i === 0 ? theme.accent : "transparent",
                color: i === 0 ? "#1C1C1E" : dark ? "#FFFFFF" : theme.primary,
                border: i === 0 ? "none" : `1.5px solid ${dark ? "rgba(255,255,255,.7)" : theme.primary}`,
                borderRadius: btnRadius(theme) }}>
              {c.label}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

export function WaCta({ p, theme, onCta }) {
  return (
    <Wrap theme={theme} tight>
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-4 shadow-sm"
        style={{ borderRadius: theme.radius }} data-testid="lp-wa-block">
        <div>
          <h3 className="text-[15px] font-bold" style={{ color: theme.text }}>{p.title}</h3>
          {p.text ? <p className="mt-0.5 text-[12.5px] text-[#5B6472]">{p.text}</p> : null}
        </div>
        <Btn cta={p.cta} theme={theme} onClick={() => onCta?.(p.cta)} testId="lp-wa-cta" />
      </div>
    </Wrap>
  );
}

/**
 * PriceEstimator — memanggil `POST /api/public/trip-estimate` (Pricing Engine ERP) sehingga
 * angka yang dilihat pengunjung iklan SAMA dengan tarif yang dipakai tim sales.
 */
export function PriceEstimator({ p, theme, mode, fleet = [] }) {
  const [form, setForm] = useState({ vehicle_type: "", days: 2,
    pax: p.default_pax || 10, trip_date: "" });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const preview = mode === "preview";

  const unitOptions = useMemo(() => {
    const seen = new Map();
    (fleet || []).forEach((v) => { if (v.type && !seen.has(v.type)) seen.set(v.type, String(v.type).replace(/_/g, " ")); });
    const list = [...seen].map(([value, label]) => ({ value, label }));
    return list.length ? list : [{ value: "hiace_premio", label: "hiace premio" }];
  }, [fleet]);

  const set = (k, v) => setForm((s) => ({ ...s, [k]: v }));
  const calc = async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await axios.post(`${API}/public/trip-estimate`, {
        vehicle_type: form.vehicle_type || unitOptions[0].value,
        days: Number(form.days) || 1,
        pax: Number(form.pax) || 1,
        trip_date: form.trip_date || null,
      });
      setResult(data);
    } catch (err) {
      setError(err?.response?.data?.detail || "Estimasi gagal dihitung. Coba lagi sebentar lagi.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Wrap theme={theme}>
      <Heading title={p.title} subtitle={p.subtitle} theme={theme} />
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_340px]">
        <div className="bg-white p-4 shadow-sm" style={{ borderRadius: theme.radius }} data-testid="lp-estimator">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Jenis unit">
              <SelectField value={form.vehicle_type || unitOptions[0].value} onChange={(v) => set("vehicle_type", v)}
                options={unitOptions} testId="lp-est-unit" className="w-full" />
            </Field>
            <Field label="Lama sewa (hari)">
              <input type="number" min="1" value={form.days} onChange={(e) => set("days", e.target.value)}
                data-testid="lp-est-days" className={inputClass} />
            </Field>
            {/* Kolom "perkiraan jarak" dihapus: harga tidak lagi memakai komponen jarak
                (diisi pengunjung = harga tak bisa dipertanggungjawabkan). Lihat pricing v2. */}
            <Field label="Tanggal berangkat" hint="Akhir pekan & musim libur bisa berbeda tarif.">
              <input type="date" value={form.trip_date} onChange={(e) => set("trip_date", e.target.value)}
                data-testid="lp-est-date" className={inputClass} />
            </Field>
          </div>
          <button type="button" onClick={calc} disabled={loading || preview} data-testid="lp-est-submit"
            className="mt-3 inline-flex h-11 items-center justify-center gap-2 px-5 text-[14px] font-bold text-white disabled:opacity-60"
            style={{ background: theme.primary, borderRadius: btnRadius(theme) }}>
            {loading ? <Loader2 size={15} className="animate-spin" /> : <Calculator size={15} />}
            {loading ? "Menghitung…" : "Hitung Estimasi"}
          </button>
          {preview ? (
            <p className="mt-1.5 text-[11px] font-semibold text-[#8B93A0]">
              Mode pratinjau — kalkulator aktif di halaman publik.
            </p>
          ) : null}
          {error ? (
            <p className="mt-2 text-[12px] font-semibold text-[#C2261C]" data-testid="lp-est-error">{error}</p>
          ) : null}
        </div>

        <aside className="bg-white p-4 shadow-sm" style={{ borderRadius: theme.radius }}>
          {loading ? (
            <div className="space-y-2" data-testid="lp-est-loading">
              {[0, 1, 2, 3].map((i) => <div key={i} className="h-6 animate-pulse rounded bg-[#EEF1F5]" />)}
            </div>
          ) : !result ? (
            <p className="text-[12.5px] text-[#6B7280]" data-testid="lp-est-empty">
              Belum ada perhitungan. Isi kolom di samping lalu tekan “Hitung Estimasi”.
            </p>
          ) : (
            <div data-testid="lp-est-result">
              <p className="text-[11.5px] font-bold uppercase tracking-wide text-[#8E8E93]">Estimasi biaya</p>
              <p className="mt-0.5 text-[24px] font-extrabold tabular-nums" style={{ color: theme.primary }}>
                {formatCurrency(result.total)}
              </p>
              <ul className="mt-2.5 space-y-1.5 border-t border-[#F0F1F3] pt-2.5">
                {(result.breakdown || []).map((b, i) => (
                  <li key={i} className="flex items-center justify-between gap-2 text-[12.5px]">
                    <span className="text-[#5B6472]">{b.label}</span>
                    <span className="font-semibold tabular-nums text-[#1C1C1E]">{formatCurrency(b.amount)}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2.5 border-t border-[#F0F1F3] pt-2 text-[12px] text-[#5B6472]">
                DP {result.dp_percent}% ≈ <b className="tabular-nums">{formatCurrency(result.dp_amount)}</b>
              </p>
              <p className="mt-1.5 text-[11px] text-[#8B93A0]">{result.note}</p>
            </div>
          )}
        </aside>
      </div>
    </Wrap>
  );
}
