import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Save, Loader2, Image as ImageIcon, X } from "lucide-react";
import apiClient from "@/services/apiClient";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { LoadingState } from "@/components/shared/DataStates";
import { invalidateSiteFeatures } from "@/hooks/useSiteFeatures";
import { resolveLogoUrl } from "@/components/public/Logo";
import MediaPickerDialog from "@/components/media/MediaPickerDialog";
import { assetUrl } from "@/lib/mediaKind";

// Pengaturan Situs (CMS): identitas & kontak yang tampil di header, footer, dan halaman
// Kontak publik. Satu sumber dgn settings.company_info (Profil Perusahaan di /app/settings).
const GROUPS = [
  ["Identitas", [
    ["name", "Nama brand"], ["tagline", "Tagline singkat"], ["logo_url", "Logo (unggah / URL)"],
    ["site_url", "URL situs publik (mis. https://rahazatrans.com) — dipakai pratinjau CMS"],
  ]],
  ["Kontak", [
    ["phone", "Telepon"], ["whatsapp", "WhatsApp (format 62…)"], ["email", "Email"],
    ["address", "Alamat"], ["city", "Kota"], ["service_area", "Area layanan"],
    ["work_hours_label", "Jam operasional (label)"],
  ]],
  ["Footer & Media Sosial", [
    ["footer_text", "Teks footer", "textarea"],
    ["instagram", "URL Instagram"], ["facebook", "URL Facebook"],
    ["tiktok", "URL TikTok"], ["youtube", "URL YouTube"],
  ]],
];

// Logo dipilih dari Media Library bersama (MediaPickerDialog) — bisa unggah baru di dalamnya.
// Dulu panel ini punya kotak unggah sendiri ke /uploads/cms (INV-MEDIA-03: "pemilih media liar").
function LogoField({ value, onChange }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const src = resolveLogoUrl(value);
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Input className="!h-9 text-[13px]" value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder="URL logo atau pilih dari Media Library" data-testid="ss-logo_url" />
        <button type="button" className="secondary-button !h-9 shrink-0 !px-3" onClick={() => setPickerOpen(true)} data-testid="ss-logo_url-upload">
          <ImageIcon size={14} /> Pilih / Unggah
        </button>
      </div>
      {src ? (
        <div className="flex items-center gap-2">
          <img src={src} alt="Logo" className="h-12 w-12 rounded border border-[#E5E5EA] bg-white object-contain" data-testid="ss-logo_url-preview" />
          <button type="button" className="icon-button !h-7 !w-7" title="Hapus logo" onClick={() => onChange("")} data-testid="ss-logo_url-clear"><X size={12} /></button>
        </div>
      ) : null}
      <MediaPickerDialog open={pickerOpen} onOpenChange={setPickerOpen} pickKind="image"
        title="Pilih logo" description="Pilih gambar dari Media Library atau unggah baru (PNG transparan disarankan)."
        onPick={(a) => { onChange(assetUrl(a)); toast.success("Logo dipilih — klik Simpan agar tampil di website"); }} />
    </div>
  );
}

export default function SiteSettingsPanel() {
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    apiClient.get("/site/settings")
      .then((r) => setForm(r.data || {}))
      .catch(() => setForm({}));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await apiClient.put("/site/settings", form);
      invalidateSiteFeatures();
      toast.success("Pengaturan situs disimpan — header, footer & halaman kontak ikut diperbarui");
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan"); }
    finally { setSaving(false); }
  };

  if (!form) return <LoadingState testId="site-settings-loading" />;
  return (
    <div className="max-w-3xl space-y-4" data-testid="site-settings-panel">
      <p className="text-[12.5px] text-[#6B6B73]">
        Identitas yang tampil di header, footer, dan halaman Kontak website. Tersinkron dengan
        "Profil Perusahaan" di Pengaturan sistem.
      </p>
      {GROUPS.map(([title, fields]) => (
        <section key={title} className="rounded-[14px] border border-[#EFF0F2] bg-white p-4 shadow-sm">
          <h3 className="text-[13px] font-bold text-[#1C1C1E]">{title}</h3>
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {fields.map(([key, label, kind]) => (
              <div key={key} className={kind === "textarea" ? "sm:col-span-2" : ""}>
                <label className="text-[11.5px] font-semibold text-[#6B6B73]">{label}</label>
                {key === "logo_url" ? (
                  <LogoField value={form.logo_url} onChange={(v) => set("logo_url", v)} />
                ) : kind === "textarea"
                  ? <Textarea className="min-h-[64px] text-[12.5px]" value={form[key] || ""} onChange={(e) => set(key, e.target.value)} data-testid={`ss-${key}`} />
                  : <Input className="!h-9 text-[13px]" value={form[key] || ""} onChange={(e) => set(key, e.target.value)} data-testid={`ss-${key}`} />}
              </div>
            ))}
          </div>
        </section>
      ))}
      <section className="rounded-[14px] border border-[#EFF0F2] bg-white p-4 shadow-sm" data-testid="ss-features">
        <h3 className="text-[13px] font-bold text-[#1C1C1E]">Fitur Situs</h3>
        <div className="mt-3 flex items-center justify-between gap-4">
          <div>
            <p className="text-[13px] font-semibold text-[#1C1C1E]">Kalkulator estimasi trip</p>
            <p className="text-[12px] text-[#6B6B73]">Tampilkan kalkulator di beranda, halaman armada, menu, footer, CTA, dan halaman /trip-calculator.</p>
          </div>
          <Switch checked={form.show_trip_calculator !== false} onCheckedChange={(v) => set("show_trip_calculator", v)} data-testid="ss-show_trip_calculator" />
        </div>
      </section>
      <button className="primary-button !h-10 !px-5 !text-[13px]" disabled={saving} onClick={save} data-testid="ss-save">
        {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Simpan Pengaturan
      </button>
    </div>
  );
}
