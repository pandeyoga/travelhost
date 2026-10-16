import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Check, Sun, Moon, Palette, Save } from "lucide-react";
import apiClient from "@/services/apiClient";

// ThemeManagerPanel — atur tema situs publik (preset + mode), pratinjau langsung, publish.
// Preset diterapkan via [data-surface="public"][data-theme=...]; mode gelap via .dark ancestor.
// Publish => PATCH /api/settings { theme_config: { preset, mode } } (owner).
const PRESETS = [
  { v: "azure", label: "Azure", desc: "Biru cerah, bersih & modern" },
  { v: "midnight", label: "Midnight", desc: "Navy pekat, mewah & elegan" },
  { v: "sunrise", label: "Sunrise", desc: "Hangat keemasan, ramah" },
  { v: "harbor", label: "Harbor", desc: "Teal laut, segar & tenang" },
];

function PreviewCard({ preset, mode }) {
  return (
    <div className={mode === "dark" ? "dark" : ""}>
      <div data-surface="public" data-theme={preset}
        className="overflow-hidden rounded-2xl border border-border bg-background" data-testid="theme-preview">
        <div className="relative h-28 bg-primary">
          <div className="absolute inset-0 opacity-90 bg-cover bg-center"
            style={{ backgroundImage: "url('https://images.unsplash.com/photo-1537996194471-e657df975ab4?q=80&w=1200&auto=format&fit=crop')" }} />
          <div className="absolute inset-0" style={{ background: "var(--gradient-hero)" }} />
          <div className="absolute bottom-3 left-3">
            <span className="rounded-full bg-accent/90 px-2 py-0.5 text-[10px] font-semibold text-accent-foreground">Populer</span>
            <p className="mt-1 font-fraunces text-lg text-white">RahazaTrans</p>
          </div>
        </div>
        <div className="space-y-2 p-3">
          <p className="font-fraunces text-[15px] text-foreground">Sewa Hiace Premium</p>
          <p className="text-[11.5px] text-muted-foreground">Estimasi biaya transparan untuk perjalanan Jawa–Bali.</p>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-primary px-3 py-1 text-[11px] font-semibold text-primary-foreground">Minta Penawaran</span>
            <span className="rounded-full border border-border px-3 py-1 text-[11px] font-medium text-foreground">Lihat Armada</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ThemeManagerPanel() {
  const [preset, setPreset] = useState("azure");
  const [mode, setMode] = useState("light");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    apiClient.get("/settings")
      .then((r) => {
        const t = r.data?.theme_config || {};
        if (t.preset) setPreset(t.preset);
        if (t.mode) setMode(t.mode);
        setDenied(false);
      })
      .catch((e) => { if (e?.response?.status === 403) setDenied(true); })
      .finally(() => setLoading(false));
  }, []);

  const publish = async () => {
    setSaving(true);
    try {
      await apiClient.patch("/settings", { theme_config: { preset, mode } });
      toast.success("Tema situs dipublikasikan");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan tema");
    } finally { setSaving(false); }
  };

  if (loading) return <div className="flex justify-center py-16 text-muted-foreground" data-testid="theme-loading"><Loader2 className="mr-2 animate-spin" /> Memuat tema…</div>;
  if (denied) return (
    <div className="rounded-[14px] border border-[#FFE0DC] bg-[#FFF5F4] px-6 py-12 text-center" data-testid="theme-denied">
      <p className="text-sm font-semibold text-[#1C1C1E]">Akses terbatas</p>
      <p className="mt-1 text-[13px] text-[#6B6B73]">Tema situs hanya dapat diatur oleh Pemilik.</p>
    </div>
  );

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_360px]" data-testid="theme-manager">
      <div className="space-y-4">
        <div>
          <p className="flex items-center gap-2 text-[13px] font-bold text-[#1C1C1E]"><Palette size={15} /> Preset Warna</p>
          <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {PRESETS.map((p) => (
              <button key={p.v} type="button" onClick={() => setPreset(p.v)} data-testid={`theme-preset-${p.v}`}
                className={`flex items-center gap-3 rounded-xl border p-3 text-left transition ${preset === p.v ? "border-[#0A84FF] ring-2 ring-[#0A84FF]/20" : "border-border hover:border-[#C7C7CC]"}`}>
                <span data-surface="public" data-theme={p.v} className="flex gap-1">
                  <span className="h-7 w-7 rounded-full bg-primary" />
                  <span className="h-7 w-7 rounded-full bg-accent" />
                </span>
                <span className="min-w-0">
                  <span className="flex items-center gap-1.5 text-[13px] font-semibold text-[#1C1C1E]">{p.label}{preset === p.v ? <Check size={13} className="text-[#0A84FF]" /> : null}</span>
                  <span className="block text-[11.5px] text-[#6B6B73]">{p.desc}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
        <div>
          <p className="text-[13px] font-bold text-[#1C1C1E]">Mode Tampilan</p>
          <div className="mt-2 flex gap-2">
            {[["light", "Terang", Sun], ["dark", "Gelap", Moon]].map(([v, l, Icon]) => (
              <button key={v} type="button" onClick={() => setMode(v)} data-testid={`theme-mode-${v}`}
                className={`flex items-center gap-2 rounded-xl border px-4 py-2 text-[13px] font-medium transition ${mode === v ? "border-[#0A84FF] bg-[#0A84FF]/8 text-[#0A84FF]" : "border-border text-[#6B6B73] hover:text-[#1C1C1E]"}`}>
                <Icon size={14} /> {l}
              </button>
            ))}
          </div>
        </div>
        <button type="button" onClick={publish} disabled={saving} data-testid="theme-publish" className="primary-button">
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Publikasikan Tema
        </button>
      </div>
      <div>
        <p className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-[#8E8E93]">Pratinjau Langsung</p>
        <PreviewCard preset={preset} mode={mode} />
        <p className="mt-2 text-[11.5px] text-[#8E8E93]">Pratinjau mencerminkan tampilan situs publik dengan preset &amp; mode terpilih.</p>
      </div>
    </div>
  );
}
