import { useCallback, useEffect, useState } from "react";
import { Plug, ShieldCheck, Save, Zap, Eye, EyeOff, MessageCircle, Facebook, Chrome, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { LoadingState, ErrorState } from "@/components/shared/DataStates";
import SelectField from "@/components/shared/SelectField";
import { Switch } from "@/components/ui/switch";

/**
 * Integrations.jsx — halaman "Integrasi API" (owner + marketing_admin).
 *
 * Kredensial TIDAK pernah di-hardcode: diisi di sini, disimpan TERENKRIPSI di server, dan
 * dikembalikan hanya dalam bentuk ter-mask ("••••••1234"). Mengosongkan kolom = biarkan
 * rahasia lama; menekan "Hapus" mengirim sentinel khusus.
 */
const MASK_HINT = "biarkan kosong untuk mempertahankan nilai tersimpan";

function Section({ icon: Icon, title, subtitle, badge, children }) {
  return (
    <section className="section-card">
      <div className="section-head">
        <h2 className="flex flex-wrap items-center gap-2">
          <Icon size={15} /> {title}
          {badge}
        </h2>
        {subtitle ? <p className="mt-0.5 text-[12px] font-normal text-[#6B6B73]">{subtitle}</p> : null}
      </div>
      <div className="section-body space-y-3.5">{children}</div>
    </section>
  );
}

function ModeBadge({ status }) {
  const live = status?.mode === "live";
  return (
    <span data-testid={`int-mode-${live ? "live" : "mock"}`}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wide ${
        live ? "bg-[#E7F7EC] text-[#12703A]" : "bg-[#FFF3E0] text-[#8A5300]"}`}>
      {live ? "AKTIF" : "BELUM AKTIF · MOCK"}
    </span>
  );
}

function Field({ label, hint, children }) {
  return (
    <div className="space-y-1.5">
      <label className="text-[12px] font-semibold text-[#3a3f4a]">{label}</label>
      {children}
      {hint ? <p className="text-[11px] text-[#8E8E93]">{hint}</p> : null}
    </div>
  );
}

function Text({ value, onChange, testId, placeholder = "", type = "text" }) {
  return (
    <input type={type} value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
      data-testid={testId}
      className="h-9 w-full rounded-lg border border-[#E5E5EA] bg-white px-3 text-[13px] outline-none focus:border-[#007AFF]" />
  );
}

function Secret({ label, field, cfg, draft, setDraft, testId }) {
  const [show, setShow] = useState(false);
  const saved = cfg?.[`${field}_set`];
  return (
    <Field label={label} hint={saved ? `Tersimpan: ${cfg[`${field}_masked`]} — ${MASK_HINT}` : "Belum diisi"}>
      <div className="flex items-center gap-2">
        <input type={show ? "text" : "password"} value={draft[field] || ""}
          onChange={(e) => setDraft((d) => ({ ...d, [field]: e.target.value }))}
          placeholder={saved ? "••••••••" : "tempel kunci di sini"} data-testid={testId}
          className="h-9 flex-1 rounded-lg border border-[#E5E5EA] bg-white px-3 text-[13px] outline-none focus:border-[#007AFF]" />
        <button type="button" className="icon-button !h-9 !w-9" onClick={() => setShow((s) => !s)}
          aria-label={show ? "Sembunyikan" : "Tampilkan"} data-testid={`${testId}-toggle`}>
          {show ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
        {saved ? (
          <button type="button" className="secondary-button !h-9" data-testid={`${testId}-clear`}
            onClick={() => setDraft((d) => ({ ...d, [field]: "__HAPUS__" }))}>Hapus</button>
        ) : null}
      </div>
    </Field>
  );
}

export default function Integrations() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState("");
  const [meta, setMeta] = useState({});
  const [google, setGoogle] = useState({});
  const [wa, setWa] = useState(null);
  const [waDraft, setWaDraft] = useState({});

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiClient.get("/integrations/config").then((r) => r.data),
      apiClient.get("/wa/config").then((r) => r.data).catch(() => null),
    ])
      .then(([cfg, waCfg]) => { setData(cfg); setWa(waCfg); setError(null); })
      .catch((e) => setError(e?.response?.data?.detail || "Gagal memuat konfigurasi integrasi"))
      .finally(() => setLoading(false));
  }, []);
  useEffect(load, [load]);

  const save = async (provider, draft, setDraft) => {
    setBusy(provider);
    try {
      await apiClient.patch(`/integrations/config/${provider}`, draft);
      toast.success("Konfigurasi disimpan (kredensial terenkripsi di server)");
      setDraft({});
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan konfigurasi");
    } finally { setBusy(""); }
  };

  const test = async (provider) => {
    setBusy(`test-${provider}`);
    try {
      const { data: res } = await apiClient.post(`/integrations/test/${provider}`);
      (res.ok ? toast.success : toast.warning)(res.message || (res.ok ? "Siap" : "Belum siap"));
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Uji koneksi gagal");
    } finally { setBusy(""); }
  };

  const saveConsent = async (patch) => {
    try {
      const { data: res } = await apiClient.patch("/integrations/consent", patch);
      setData((d) => ({ ...d, consent: res }));
      toast.success("Pengaturan persetujuan disimpan");
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan"); }
  };

  const saveWa = async () => {
    setBusy("wa");
    try {
      const payload = {
        provider: waDraft.provider || wa?.provider,
        business_phone: waDraft.business_phone ?? wa?.business_phone,
        meta: {
          phone_number_id: waDraft.phone_number_id ?? wa?.meta?.phone_number_id,
          verify_token: waDraft.verify_token ?? wa?.meta?.verify_token,
          access_token: waDraft.access_token || "",
          app_secret: waDraft.app_secret || "",
        },
      };
      await apiClient.patch("/wa/config", payload);
      toast.success("Konfigurasi WhatsApp disimpan");
      setWaDraft({});
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan WhatsApp");
    } finally { setBusy(""); }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const mp = data?.providers?.meta_ads || {};
  const gp = data?.providers?.google_ads || {};
  const mc = mp.config || {};
  const gc = gp.config || {};
  const consent = data?.consent || {};

  return (
    <div className="space-y-5" data-testid="integrations-page">
      {!data?.vault_ready ? (
        <div className="flex items-start gap-2 rounded-xl border border-[#FFD9A8] bg-[#FFF8EC] p-3.5 text-[12.5px] text-[#8A5300]"
          data-testid="int-vault-warning">
          <AlertTriangle size={15} className="mt-0.5 shrink-0" />
          <span>Kunci enkripsi server belum diset, jadi kredensial belum bisa disimpan dengan aman.
            Hubungi pengelola sistem (variabel <b>SETTINGS_ENCRYPTION_KEY_B64</b>).</span>
        </div>
      ) : null}

      <Section icon={Facebook} title="Meta Ads — Pixel & Conversions API" badge={<ModeBadge status={mp.status} />}
        subtitle="Dipakai untuk melacak pengunjung iklan Facebook/Instagram dan mengirim konversi dari server (lead, booking, DP).">
        <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
          <Field label="Pixel ID (wajib)" hint="Events Manager → Data Sources">
            <Text value={meta.pixel_id ?? mc.pixel_id} onChange={(v) => setMeta((m) => ({ ...m, pixel_id: v }))} testId="int-meta-pixel" placeholder="1234567890" />
          </Field>
          <Field label="Versi API" hint="v26.0 aktif (terbaru); ganti hanya bila Meta merilis versi baru">
            <Text value={meta.api_version ?? mc.api_version} onChange={(v) => setMeta((m) => ({ ...m, api_version: v }))} testId="int-meta-version" />
          </Field>
          <Field label="Dataset ID (opsional)" hint="dipakai Conversions API bila berbeda dari Pixel ID">
            <Text value={meta.dataset_id ?? mc.dataset_id} onChange={(v) => setMeta((m) => ({ ...m, dataset_id: v }))} testId="int-meta-dataset" />
          </Field>
          <Field label="Ad Account ID" hint="format act_XXXXXXXX — wajib untuk laporan biaya & kampanye">
            <Text value={meta.ad_account_id ?? mc.ad_account_id} onChange={(v) => setMeta((m) => ({ ...m, ad_account_id: v }))} testId="int-meta-account" placeholder="act_1234567890" />
          </Field>
          <Field label="Page ID" hint="wajib untuk Lead Ads & iklan Klik-ke-WhatsApp">
            <Text value={meta.page_id ?? mc.page_id} onChange={(v) => setMeta((m) => ({ ...m, page_id: v }))} testId="int-meta-page" />
          </Field>
          <Field label="WhatsApp Business Account ID (WABA)" hint="untuk konversi dari chat iklan (CTWA)">
            <Text value={meta.waba_id ?? mc.waba_id} onChange={(v) => setMeta((m) => ({ ...m, waba_id: v }))} testId="int-meta-waba" />
          </Field>
          <Field label="Nomor WhatsApp iklan" hint="format 628xxx — tujuan iklan Klik-ke-WhatsApp">
            <Text value={meta.whatsapp_number ?? mc.whatsapp_number} onChange={(v) => setMeta((m) => ({ ...m, whatsapp_number: v }))} testId="int-meta-wanumber" />
          </Field>
          <Field label="Plafon budget harian (satuan terkecil, 0 = tanpa plafon)"
            hint="ERP menolak budget di atas angka ini — pengaman agar tidak salah ketik nol">
            <Text type="number" value={meta.max_daily_budget_minor ?? mc.max_daily_budget_minor} onChange={(v) => setMeta((m) => ({ ...m, max_daily_budget_minor: v }))} testId="int-meta-budgetcap" />
          </Field>
          <Secret label="Access Token (Conversions API)" field="access_token" cfg={mc} draft={meta} setDraft={setMeta} testId="int-meta-token" />
          <Secret label="System User Token (Marketing API: laporan & kampanye)" field="system_user_token" cfg={mc} draft={meta} setDraft={setMeta} testId="int-meta-systoken" />
          <Secret label="Page Access Token (baca isi Lead Ads)" field="page_access_token" cfg={mc} draft={meta} setDraft={setMeta} testId="int-meta-pagetoken" />
          <Secret label="Verify Token webhook Lead Ads" field="lead_verify_token" cfg={mc} draft={meta} setDraft={setMeta} testId="int-meta-leadverify" />
          <Secret label="App Secret" field="app_secret" cfg={mc} draft={meta} setDraft={setMeta} testId="int-meta-secret" />
          <Secret label="Test Event Code (opsional, untuk uji)" field="test_event_code" cfg={mc} draft={meta} setDraft={setMeta} testId="int-meta-testcode" />
          <Field label="Opsi">
            <div className="flex flex-col gap-2 pt-1">
              <label className="flex items-center gap-2 text-[12.5px] text-[#1C1C1E]">
                <Switch checked={(meta.enabled ?? mc.enabled) || false} onCheckedChange={(v) => setMeta((m) => ({ ...m, enabled: v }))} data-testid="int-meta-enabled" />
                Aktifkan pelacakan Meta
              </label>
              <label className="flex items-center gap-2 text-[12.5px] text-[#1C1C1E]">
                <Switch checked={(meta.ldu_enabled ?? mc.ldu_enabled) || false} onCheckedChange={(v) => setMeta((m) => ({ ...m, ldu_enabled: v }))} data-testid="int-meta-ldu" />
                Limited Data Use (privasi)
              </label>
            </div>
          </Field>
        </div>
        {mp.status?.missing?.length ? (
          <p className="text-[12px] text-[#8A5300]" data-testid="int-meta-missing">Belum lengkap: {mp.status.missing.join(", ")}</p>
        ) : null}
        {mp.ads_status?.missing_labels?.length ? (
          <p className="text-[12px] text-[#8A5300]" data-testid="int-meta-ads-missing">
            Fitur iklan (laporan biaya, kampanye, audiens) belum bisa dipakai — perlu: {mp.ads_status.missing_labels.join(", ")}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <button className="primary-button" onClick={() => save("meta_ads", meta, setMeta)} disabled={busy === "meta_ads"} data-testid="int-meta-save">
            <Save size={14} /> {busy === "meta_ads" ? "Menyimpan…" : "Simpan Meta"}
          </button>
          <button className="secondary-button" onClick={() => test("meta_ads")} disabled={busy === "test-meta_ads"} data-testid="int-meta-test">
            <Zap size={14} /> Uji Koneksi
          </button>
        </div>
      </Section>

      <Section icon={Chrome} title="Google Ads & GA4" badge={<ModeBadge status={gp.status} />}
        subtitle="Tag GA4 + konversi Google Ads. Konversi dari gclid dikirim via Data Manager API (aturan baru sejak 15 Juni 2026).">
        <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
          <Field label="GA4 Measurement ID" hint="format G-XXXXXXXXXX">
            <Text value={google.ga4_measurement_id ?? gc.ga4_measurement_id} onChange={(v) => setGoogle((g) => ({ ...g, ga4_measurement_id: v }))} testId="int-google-ga4" placeholder="G-XXXXXXXXXX" />
          </Field>
          <Field label="Google Ads Conversion ID" hint="format AW-XXXXXXXXX">
            <Text value={google.ads_conversion_id ?? gc.ads_conversion_id} onChange={(v) => setGoogle((g) => ({ ...g, ads_conversion_id: v }))} testId="int-google-aw" placeholder="AW-123456789" />
          </Field>
          <Field label="Customer ID (wajib)" hint="tanpa tanda hubung">
            <Text value={google.customer_id ?? gc.customer_id} onChange={(v) => setGoogle((g) => ({ ...g, customer_id: v }))} testId="int-google-customer" placeholder="1234567890" />
          </Field>
          <Field label="Login Customer ID (akun manajer)" hint="opsional; tanpa tanda hubung">
            <Text value={google.login_customer_id ?? gc.login_customer_id} onChange={(v) => setGoogle((g) => ({ ...g, login_customer_id: v }))} testId="int-google-login" />
          </Field>
          <Field label="Plafon budget harian (micros, 0 = tanpa plafon)"
            hint="1 satuan mata uang = 1.000.000 micros">
            <Text type="number" value={google.max_daily_budget_micros ?? gc.max_daily_budget_micros} onChange={(v) => setGoogle((g) => ({ ...g, max_daily_budget_micros: v }))} testId="int-google-budgetcap" />
          </Field>
        </div>
        <div className="grid grid-cols-1 gap-3.5 md:grid-cols-3">
          {[["lead_submitted", "Label konversi: Lead"], ["booking_confirmed", "Label konversi: Booking"], ["deposit_received", "Label konversi: DP"]].map(([k, label]) => (
            <Field key={k} label={label} hint="format AW-XXXX/labelKode">
              <Text value={(google.conversion_labels?.[k]) ?? gc.conversion_labels?.[k]}
                onChange={(v) => setGoogle((g) => ({ ...g, conversion_labels: { ...(g.conversion_labels || gc.conversion_labels || {}), [k]: v } }))}
                testId={`int-google-label-${k}`} />
            </Field>
          ))}
          {[["lead_submitted", "ID action: Lead"], ["booking_confirmed", "ID action: Booking"], ["deposit_received", "ID action: DP"]].map(([k, label]) => (
            <Field key={`a-${k}`} label={label} hint="angka ID conversion action (Data Manager)">
              <Text value={(google.conversion_action_ids?.[k]) ?? gc.conversion_action_ids?.[k]}
                onChange={(v) => setGoogle((g) => ({ ...g, conversion_action_ids: { ...(g.conversion_action_ids || gc.conversion_action_ids || {}), [k]: v } }))}
                testId={`int-google-action-${k}`} />
            </Field>
          ))}
        </div>
        <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
          <Secret label="OAuth Client ID" field="oauth_client_id" cfg={gc} draft={google} setDraft={setGoogle} testId="int-google-clientid" />
          <Secret label="OAuth Client Secret" field="oauth_client_secret" cfg={gc} draft={google} setDraft={setGoogle} testId="int-google-clientsecret" />
          <Secret label="OAuth Refresh Token (wajib)" field="oauth_refresh_token" cfg={gc} draft={google} setDraft={setGoogle} testId="int-google-refresh" />
          <Secret label="Developer Token (laporan & kampanye)" field="developer_token" cfg={gc} draft={google} setDraft={setGoogle} testId="int-google-devtoken" />
          <Secret label="GA4 API Secret (event server-side, opsional)" field="ga4_api_secret" cfg={gc} draft={google} setDraft={setGoogle} testId="int-google-ga4secret" />
        </div>
        <label className="flex items-center gap-2 text-[12.5px] text-[#1C1C1E]">
          <Switch checked={(google.enabled ?? gc.enabled) || false} onCheckedChange={(v) => setGoogle((g) => ({ ...g, enabled: v }))} data-testid="int-google-enabled" />
          Aktifkan pelacakan Google
        </label>
        {gp.status?.missing?.length ? (
          <p className="text-[12px] text-[#8A5300]" data-testid="int-google-missing">Belum lengkap: {gp.status.missing.join(", ")}</p>
        ) : null}
        {gp.ads_status?.missing_labels?.length ? (
          <p className="text-[12px] text-[#8A5300]" data-testid="int-google-ads-missing">
            Fitur iklan (laporan GAQL, kampanye, Customer Match) belum bisa dipakai — perlu: {gp.ads_status.missing_labels.join(", ")}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <button className="primary-button" onClick={() => save("google_ads", google, setGoogle)} disabled={busy === "google_ads"} data-testid="int-google-save">
            <Save size={14} /> {busy === "google_ads" ? "Menyimpan…" : "Simpan Google"}
          </button>
          <button className="secondary-button" onClick={() => test("google_ads")} disabled={busy === "test-google_ads"} data-testid="int-google-test">
            <Zap size={14} /> Uji Koneksi
          </button>
        </div>
      </Section>

      <Section icon={MessageCircle} title="WhatsApp Cloud API"
        badge={<ModeBadge status={{ mode: wa?.provider === "meta_cloud" && wa?.meta?.access_token_set ? "live" : "mock" }} />}
        subtitle="Pengiriman pesan otomatis (konfirmasi booking, pengingat). Selama provider = mock, pesan hanya disimulasikan.">
        {!wa ? <p className="text-[12.5px] text-[#6B6B73]">Konfigurasi WhatsApp tidak tersedia.</p> : (
          <>
            <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
              <Field label="Provider">
                <SelectField value={waDraft.provider ?? wa.provider} onChange={(v) => setWaDraft((d) => ({ ...d, provider: v }))}
                  testId="int-wa-provider" className="w-full"
                  options={[{ value: "mock", label: "Mock (simulasi, tanpa kirim nyata)" },
                            { value: "meta_cloud", label: "Meta WhatsApp Cloud API" },
                            { value: "partner", label: "Partner (Wati/Qontak/Twilio)" }]} />
              </Field>
              <Field label="Nomor Bisnis" hint="format 62...">
                <Text value={waDraft.business_phone ?? wa.business_phone} onChange={(v) => setWaDraft((d) => ({ ...d, business_phone: v }))} testId="int-wa-phone" />
              </Field>
              <Field label="Phone Number ID">
                <Text value={waDraft.phone_number_id ?? wa.meta?.phone_number_id} onChange={(v) => setWaDraft((d) => ({ ...d, phone_number_id: v }))} testId="int-wa-phoneid" />
              </Field>
              <Field label="Verify Token (webhook)">
                <Text value={waDraft.verify_token ?? wa.meta?.verify_token} onChange={(v) => setWaDraft((d) => ({ ...d, verify_token: v }))} testId="int-wa-verify" />
              </Field>
              <Field label="Access Token" hint={wa.meta?.access_token_set ? `Tersimpan — ${MASK_HINT}` : "Belum diisi"}>
                <Text type="password" value={waDraft.access_token} onChange={(v) => setWaDraft((d) => ({ ...d, access_token: v }))} testId="int-wa-token" placeholder={wa.meta?.access_token_set ? "••••••••" : ""} />
              </Field>
              <Field label="App Secret" hint={wa.meta?.app_secret_set ? `Tersimpan — ${MASK_HINT}` : "Belum diisi"}>
                <Text type="password" value={waDraft.app_secret} onChange={(v) => setWaDraft((d) => ({ ...d, app_secret: v }))} testId="int-wa-secret" placeholder={wa.meta?.app_secret_set ? "••••••••" : ""} />
              </Field>
            </div>
            <button className="primary-button" onClick={saveWa} disabled={busy === "wa"} data-testid="int-wa-save">
              <Save size={14} /> {busy === "wa" ? "Menyimpan…" : "Simpan WhatsApp"}
            </button>
          </>
        )}
      </Section>

      <Section icon={ShieldCheck} title="Persetujuan Pengunjung (Consent)"
        subtitle="Mengatur banner persetujuan di situs publik. Google Consent Mode v2 default DITOLAK sampai pengunjung mengizinkan.">
        <div className="space-y-2.5">
          <label className="flex items-center gap-2 text-[12.5px] text-[#1C1C1E]">
            <Switch checked={consent.require_consent !== false} onCheckedChange={(v) => saveConsent({ require_consent: v })} data-testid="int-consent-require" />
            Wajib minta persetujuan sebelum memasang cookie iklan (disarankan)
          </label>
          <label className="flex items-center gap-2 text-[12.5px] text-[#1C1C1E]">
            <Switch checked={consent.banner_enabled !== false} onCheckedChange={(v) => saveConsent({ banner_enabled: v })} data-testid="int-consent-banner" />
            Tampilkan banner persetujuan
          </label>
          <Field label="Teks banner">
            <Text value={consent.banner_text} onChange={(v) => setData((d) => ({ ...d, consent: { ...d.consent, banner_text: v } }))} testId="int-consent-text" />
          </Field>
          <button className="secondary-button" onClick={() => saveConsent({ banner_text: consent.banner_text })} data-testid="int-consent-save">
            <Save size={14} /> Simpan Teks
          </button>
        </div>
      </Section>

      <p className="flex items-center gap-1.5 text-[11.5px] text-[#8E8E93]">
        <Plug size={12} /> Kredensial disimpan terenkripsi di server dan tidak pernah dikirim kembali ke browser dalam bentuk asli.
      </p>
    </div>
  );
}
