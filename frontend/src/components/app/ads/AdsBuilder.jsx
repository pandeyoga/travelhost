import { useEffect, useState } from "react";
import { Wrench, ShieldCheck, Rocket, AlertTriangle, Loader2 } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { EmptyState } from "@/components/shared/DataStates";
import SelectField from "@/components/shared/SelectField";
import ConfirmNameDialog from "@/components/app/ads/ConfirmNameDialog";

/**
 * AdsBuilder — membuat kampanye langsung dari ERP dengan pengaman berlapis:
 *   Langkah 1 "Validasi"  → platform memeriksa payload (validate_only): tidak ada objek, tanpa biaya.
 *   Langkah 2 "Terbitkan" → objek dibuat NYATA tapi status DIJEDA + wajib ketik ulang nama kampanye.
 *   Aktivasi dilakukan terpisah di tab Per Kampanye (juga dengan konfirmasi ketik nama).
 */
const PROVIDERS = [
  { value: "meta", label: "Meta (Facebook & Instagram)" },
  { value: "google", label: "Google Ads (Search)" },
];
const OBJECTIVES = [
  { value: "OUTCOME_LEADS", label: "Dapatkan lead (form / WhatsApp)" },
  { value: "OUTCOME_SALES", label: "Dapatkan penjualan (booking)" },
  { value: "OUTCOME_TRAFFIC", label: "Kunjungan ke landing page" },
  { value: "OUTCOME_ENGAGEMENT", label: "Interaksi (engagement)" },
];
const DESTINATIONS = [
  { value: "whatsapp", label: "Klik-ke-WhatsApp (chat langsung)" },
  { value: "lead_form", label: "Formulir Lead Ads di dalam aplikasi" },
  { value: "website", label: "Website / landing page" },
  { value: "website_conversion", label: "Website + optimasi konversi pixel" },
];

function Field({ label, hint, children }) {
  return (
    <div className="space-y-1.5">
      <label className="text-[12px] font-semibold text-[#3a3f4a]">{label}</label>
      {children}
      {hint ? <p className="text-[11px] text-[#8E8E93]">{hint}</p> : null}
    </div>
  );
}

function Input({ value, onChange, testId, placeholder = "", type = "text" }) {
  return (
    <input type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
      data-testid={testId}
      className="h-9 w-full rounded-lg border border-[#E5E5EA] bg-white px-3 text-[13px] outline-none focus:border-[#007AFF]" />
  );
}

export default function AdsBuilder({ canManage, readiness }) {
  const [provider, setProvider] = useState("meta");
  // FASE F8b — halaman tujuan iklan DIPILIH dari daftar, tidak lagi ditulis tangan. URL yang
  // ditulis tangan adalah penyebab paling umum iklan mendarat di 404 atau di halaman draf,
  // dan biayanya tetap ditagih penuh.
  const [targets, setTargets] = useState([]);
  const [lpSlug, setLpSlug] = useState("");
  const [meta, setMeta] = useState({
    name: "", objective: "OUTCOME_LEADS", adsetName: "", budget: "150000",
    destination: "whatsapp", headline: "", message: "", link: "",
  });
  const [google, setGoogle] = useState({
    name: "", budget: "150000", adgroupName: "", keywords: "sewa hiace bali, rental bus wisata",
    finalUrl: "", headlines: "Sewa Hiace Bali, Driver Ramah & Tepat Waktu, Harga Transparan",
    descriptions: "Armada terawat, sopir berpengalaman, siap antar wisata rombongan.",
  });
  const [busy, setBusy] = useState("");
  const [result, setResult] = useState(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const campaignName = provider === "meta" ? meta.name : google.name;

  const buildBody = () => (provider === "meta" ? {
    provider: "meta",
    campaign: { name: meta.name, objective: meta.objective },
    adset: { name: meta.adsetName || `${meta.name} · adset`, daily_budget_minor: Number(meta.budget) || 0,
             destination: meta.destination, countries: ["ID"] },
    creative: { headline: meta.headline, message: meta.message, link: meta.link },
    ad: { name: `${meta.name} · iklan` },
  } : {
    provider: "google",
    campaign: { name: google.name, daily_budget_micros: Math.round((Number(google.budget) || 0) * 1_000_000),
                channel_type: "SEARCH" },
    adgroup: { name: google.adgroupName || `${google.name} · grup`,
               keywords: google.keywords.split(",").map((k) => k.trim()).filter(Boolean) },
    creative: { final_url: google.finalUrl,
                headlines: google.headlines.split(",").map((h) => h.trim()).filter(Boolean),
                descriptions: google.descriptions.split(",").map((d) => d.trim()).filter(Boolean) },
  });

  useEffect(() => {
    apiClient.get("/landing/ad-targets").then(({ data }) => {
      setTargets(data.targets || []);
      const preset = new URLSearchParams(window.location.search).get("lp");
      if (preset) setLpSlug(preset);
    }).catch(() => setTargets([]));
  }, []);

  const chosen = targets.find((t) => t.slug === lpSlug) || null;
  const utmFor = (prov) => (prov === "google"
    ? { utm_source: "google", utm_medium: "cpc" }
    : { utm_source: "meta", utm_medium: "paid_social" });
  const adUrl = (prov, campaignName) => {
    if (!lpSlug) return "";
    const qs = new URLSearchParams({ ...utmFor(prov), utm_campaign: campaignName || lpSlug });
    return `${window.location.origin}/lp/${lpSlug}?${qs.toString()}`;
  };
  const applyLanding = (slug) => {
    setLpSlug(slug);
    if (!slug) return;
    setMeta((m) => ({ ...m, link: `${window.location.origin}/lp/${slug}` }));
    setGoogle((g) => ({ ...g, finalUrl: `${window.location.origin}/lp/${slug}` }));
  };

  const LandingChooser = () => (
    <div className="mb-3 rounded-xl border border-[#E5E5EA] bg-[#F7F8FA] p-3" data-testid="ads-lp-chooser">
      <p className="text-[12px] font-bold text-[#1C1C1E]">Halaman tujuan iklan</p>
      <p className="mt-0.5 text-[11.5px] text-[#6B6B73]">
        Pilih halaman iklan yang sudah dibuat di menu Landing Page Iklan. UTM ditempel otomatis
        supaya lead-nya terhubung ke kampanye ini.
      </p>
      <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-[1fr_auto]">
        <SelectField value={lpSlug} onChange={applyLanding} testId="ads-lp-select" className="w-full"
          placeholder="Pilih halaman iklan"
          options={targets.map((t) => ({
            value: t.slug,
            label: `${t.title} · ${t.published ? "TERBIT" : "DRAF"} · skor ${t.score}`,
          }))} />
        {lpSlug ? (
          <button type="button" className="secondary-button !h-9" data-testid="ads-lp-copy"
            onClick={() => {
              const url = adUrl(provider, provider === "google" ? google.name : meta.name);
              try { navigator.clipboard.writeText(url); toast.success("URL iklan disalin"); }
              catch (e) { window.prompt("Salin URL iklan:", url); }
            }}>Salin URL iklan</button>
        ) : null}
      </div>
      {chosen && !chosen.published ? (
        <p className="mt-2 rounded-lg bg-[#FDF2F1] px-2.5 py-1.5 text-[11.5px] font-semibold text-[#C2261C]"
          data-testid="ads-lp-warning">
          Halaman ini masih DRAF — terbitkan dulu, kalau tidak klik iklan akan mendarat di halaman 404.
        </p>
      ) : null}
      {chosen && chosen.published && chosen.blockers?.length ? (
        <p className="mt-2 rounded-lg bg-[#FFF8EC] px-2.5 py-1.5 text-[11.5px] text-[#8A5300]"
          data-testid="ads-lp-blockers">
          Perlu diperbaiki dulu: {chosen.blockers.join(" · ")}
        </p>
      ) : null}
      {lpSlug ? (
        <p className="mt-2 break-all rounded-lg bg-white px-2.5 py-1.5 text-[11px] text-[#3a3f4a]"
          data-testid="ads-lp-url">{adUrl(provider, provider === "google" ? google.name : meta.name)}</p>
      ) : null}
    </div>
  );

  const validate = async () => {
    setBusy("validate");
    try {
      const { data } = await apiClient.post("/ads/campaigns/validate", buildBody());
      setResult(data);
      const st = data?.validated?.status;
      if (st === "ok") toast.success("Platform menyatakan payload VALID (belum ada objek dibuat)");
      else if (st === "not_configured") toast.warning(data.validated.reason);
      else toast.warning(data?.validated?.reason || `Validasi ditolak (${st})`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memvalidasi kampanye");
    } finally { setBusy(""); }
  };

  const publish = async (typed) => {
    setBusy("publish");
    setConfirmOpen(false);
    try {
      const { data } = await apiClient.post("/ads/campaigns/publish", { ...buildBody(), confirm_name: typed });
      setResult(data);
      const first = (data?.steps || [])[0]?.result || {};
      if (first.status === "ok") toast.success("Kampanye dibuat dengan status DIJEDA — aktifkan bila sudah yakin");
      else toast.warning(first.reason || "Belum bisa diterbitkan");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menerbitkan kampanye");
    } finally { setBusy(""); }
  };

  if (!canManage) {
    return (
      <EmptyState title="Hanya owner & marketing admin" testId="ads-builder-readonly"
        description="Pembuatan kampanye membelanjakan uang, jadi dibatasi pada peran yang berwenang. Anda tetap bisa melihat performa iklan." />
    );
  }

  const mode = readiness?.[provider]?.mode;

  return (
    <div className="space-y-4" data-testid="ads-builder">
      {mode !== "live" ? (
        <div className="flex items-start gap-2 rounded-xl border border-[#FFD9A8] bg-[#FFF8EC] p-3.5 text-[12.5px] text-[#8A5300]"
          data-testid="ads-builder-warning">
          <AlertTriangle size={15} className="mt-0.5 shrink-0" />
          <span>
            Integrasi {provider === "meta" ? "Meta" : "Google"} belum aktif
            {readiness?.[provider]?.missing_labels?.length ? ` (belum lengkap: ${readiness[provider].missing_labels.join(", ")})` : ""}.
            Anda masih bisa menyusun kampanye dan melihat payload yang akan dikirim; pengiriman nyata menunggu kredensial.
          </span>
        </div>
      ) : null}

      <section className="section-card">
        <div className="section-head">
          <h2 className="flex items-center gap-2"><Wrench size={15} /> Susun Kampanye</h2>
          <p className="mt-0.5 text-[12px] font-normal text-[#6B6B73]">
            Semua objek dibuat dengan status <b>DIJEDA</b>. Tidak ada rupiah yang keluar sebelum Anda mengaktifkannya sendiri.
          </p>
        </div>
        <div className="section-body space-y-3.5">
          <div className="w-full sm:w-[320px]">
            <Field label="Platform">
              <SelectField value={provider} onChange={setProvider} options={PROVIDERS} testId="ads-builder-provider" className="w-full" />
            </Field>
          </div>

          {provider === "meta" ? (
            <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
              <div className="md:col-span-2"><LandingChooser /></div>
              <Field label="Nama kampanye"><Input value={meta.name} onChange={(v) => setMeta((m) => ({ ...m, name: v }))} testId="ads-builder-meta-name" placeholder="Lead WA Bali Agustus" /></Field>
              <Field label="Tujuan kampanye">
                <SelectField value={meta.objective} onChange={(v) => setMeta((m) => ({ ...m, objective: v }))} options={OBJECTIVES} testId="ads-builder-meta-objective" className="w-full" />
              </Field>
              <Field label="Nama adset"><Input value={meta.adsetName} onChange={(v) => setMeta((m) => ({ ...m, adsetName: v }))} testId="ads-builder-meta-adset" placeholder="Jakarta & Bali · 25-55" /></Field>
              <Field label="Budget harian (satuan terkecil mata uang akun)" hint="Plafon maksimum diatur di Integrasi API">
                <Input type="number" value={meta.budget} onChange={(v) => setMeta((m) => ({ ...m, budget: v }))} testId="ads-builder-meta-budget" />
              </Field>
              <Field label="Tujuan klik iklan">
                <SelectField value={meta.destination} onChange={(v) => setMeta((m) => ({ ...m, destination: v }))} options={DESTINATIONS} testId="ads-builder-meta-destination" className="w-full" />
              </Field>
              <Field label="Judul iklan"><Input value={meta.headline} onChange={(v) => setMeta((m) => ({ ...m, headline: v }))} testId="ads-builder-meta-headline" placeholder="Sewa Hiace + Driver" /></Field>
              <Field label="Teks iklan"><Input value={meta.message} onChange={(v) => setMeta((m) => ({ ...m, message: v }))} testId="ads-builder-meta-message" placeholder="Chat sekarang untuk cek ketersediaan unit" /></Field>
              <Field label="Tautan (untuk tujuan website)" hint="boleh dikosongkan untuk Klik-ke-WhatsApp">
                <Input value={meta.link} onChange={(v) => setMeta((m) => ({ ...m, link: v }))} testId="ads-builder-meta-link" placeholder="https://…/lp/armada" />
              </Field>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
              <div className="md:col-span-2"><LandingChooser /></div>
              <Field label="Nama kampanye"><Input value={google.name} onChange={(v) => setGoogle((g) => ({ ...g, name: v }))} testId="ads-builder-google-name" placeholder="Search · Sewa Bus Wisata" /></Field>
              <Field label="Budget harian (mata uang akun)" hint="dikirim ke Google dalam micros (×1.000.000)">
                <Input type="number" value={google.budget} onChange={(v) => setGoogle((g) => ({ ...g, budget: v }))} testId="ads-builder-google-budget" />
              </Field>
              <Field label="Nama grup iklan"><Input value={google.adgroupName} onChange={(v) => setGoogle((g) => ({ ...g, adgroupName: v }))} testId="ads-builder-google-adgroup" /></Field>
              <Field label="URL tujuan"><Input value={google.finalUrl} onChange={(v) => setGoogle((g) => ({ ...g, finalUrl: v }))} testId="ads-builder-google-url" placeholder="https://…/armada" /></Field>
              <Field label="Kata kunci (pisahkan dengan koma)">
                <Input value={google.keywords} onChange={(v) => setGoogle((g) => ({ ...g, keywords: v }))} testId="ads-builder-google-keywords" />
              </Field>
              <Field label="Judul iklan (maks 30 karakter/judul, pisahkan koma)">
                <Input value={google.headlines} onChange={(v) => setGoogle((g) => ({ ...g, headlines: v }))} testId="ads-builder-google-headlines" />
              </Field>
              <Field label="Deskripsi (maks 90 karakter, pisahkan koma)">
                <Input value={google.descriptions} onChange={(v) => setGoogle((g) => ({ ...g, descriptions: v }))} testId="ads-builder-google-descriptions" />
              </Field>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <button className="secondary-button" onClick={validate} disabled={!campaignName || busy === "validate"}
              data-testid="ads-builder-validate">
              {busy === "validate" ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
              {busy === "validate" ? " Memvalidasi…" : " 1. Validasi (tanpa biaya)"}
            </button>
            <button className="primary-button" onClick={() => setConfirmOpen(true)}
              disabled={!campaignName || !result || busy === "publish"} data-testid="ads-builder-publish">
              {busy === "publish" ? <Loader2 size={14} className="animate-spin" /> : <Rocket size={14} />}
              {busy === "publish" ? " Menerbitkan…" : " 2. Terbitkan (status DIJEDA)"}
            </button>
          </div>
          {!result ? (
            <p className="text-[11.5px] text-[#8E8E93]">Validasi dulu sebelum menerbitkan — tombol terbitkan aktif setelah validasi dijalankan.</p>
          ) : null}
        </div>
      </section>

      {result ? (
        <section className="section-card" data-testid="ads-builder-result">
          <div className="section-head">
            <h2 className="flex items-center gap-2"><ShieldCheck size={15} /> Hasil &amp; Payload yang Dikirim</h2>
            <p className="mt-0.5 text-[12px] font-normal text-[#6B6B73]">
              Ditampilkan apa adanya supaya Anda tahu persis apa yang dikirim ke platform (tanpa kredensial di dalamnya).
            </p>
          </div>
          <div className="section-body">
            <pre className="max-h-[360px] overflow-auto rounded-xl bg-[#F7F8FA] p-3 text-[11.5px] leading-relaxed text-[#3C3C43]">
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        </section>
      ) : null}

      <ConfirmNameDialog
        open={confirmOpen}
        expectedName={campaignName}
        title="Terbitkan kampanye ini?"
        description="Objek kampanye/adset/iklan akan DIBUAT di platform dengan status DIJEDA. Belum ada biaya berjalan sampai Anda mengaktifkannya."
        actionLabel="Terbitkan (DIJEDA)"
        testId="ads-publish-confirm"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={publish}
      />
    </div>
  );
}
