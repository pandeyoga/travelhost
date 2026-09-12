import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import SelectField from "@/components/shared/SelectField";
import { Btn, Icon, inputClass, btnRadius } from "@/components/app/landing/shared";

/**
 * blocks/HeroBlocks.jsx — blok layar pertama halaman iklan.
 *
 * `SearchHero` meniru pola OTA (tab kategori + chip cepat + baris pencarian di atas gambar)
 * karena pengunjung iklan datang dengan niat spesifik: formulir di layar pertama memangkas satu
 * langkah menuju lead. Inputnya BENAR-BENAR bisa diisi (dulu `readOnly` — pengunjung menekan
 * "Cari" tanpa bisa mengisi apa pun, dan seluruh niatnya hilang saat pindah halaman).
 */
function fieldName(f, i) {
  return f.name || `f${i}`;
}

export function SearchHero({ p, theme, mode, first, onSearch }) {
  const [tab, setTab] = useState(p.active_tab || 0);
  const [values, setValues] = useState({});
  const [chip, setChip] = useState("");
  const bg = p.media?.src;
  const preview = mode === "preview";
  // Di halaman publik header situs bersifat fixed & transparan di puncak halaman; hero pertama
  // WAJIB menyediakan ruang di atas agar judul tidak tertutup menu (dan logo putih tetap kontras
  // di atas latar hero yang gelap).
  const topPad = mode === "public" && first ? "pt-[104px]" : "pt-9";

  const set = (k, v) => setValues((s) => ({ ...s, [k]: v }));
  const submit = () => {
    const payload = { ...values };
    if (chip) payload.q = chip;
    const activeTab = (p.tabs || [])[tab];
    if (activeTab?.label) payload.kategori = activeTab.label;
    onSearch?.(payload, activeTab);
  };

  return (
    <section className={`relative overflow-hidden px-5 pb-9 ${topPad}`} data-testid="lp-search-hero"
      style={{ background: bg ? `url(${bg}) center/cover no-repeat`
        : `linear-gradient(135deg, ${theme.primary}, ${theme.accent})` }}>
      <div className="absolute inset-0" style={{ background: `rgba(6,18,30,${(p.overlay ?? 40) / 100})` }} />
      <div className="relative mx-auto max-w-[1120px]">
        {p.eyebrow ? (
          <p className="text-[11.5px] font-bold uppercase tracking-widest text-white/85">{p.eyebrow}</p>
        ) : null}
        <h1 className="mt-1 max-w-[760px] text-[30px] font-extrabold leading-tight text-white">{p.title}</h1>
        {p.subtitle ? <p className="mt-2 max-w-[640px] text-[14px] text-white/90">{p.subtitle}</p> : null}

        <div className="mt-5 rounded-2xl bg-white/95 p-3.5 shadow-lg backdrop-blur"
          style={{ borderRadius: Math.max(theme.radius, 12) }}>
          {p.tabs?.length ? (
            <div className="mb-3 flex flex-wrap gap-1.5 border-b border-[#EEF0F3] pb-2.5">
              {p.tabs.map((t, i) => (
                <button key={`${t.label}-${i}`} type="button" onClick={() => setTab(i)}
                  data-testid={`lp-tab-${i}`}
                  className="relative inline-flex items-center gap-1.5 rounded-full px-3.5 py-2 text-[13px] font-bold transition-colors"
                  style={{ background: tab === i ? theme.primary : "#F4F5F7",
                    color: tab === i ? "#FFFFFF" : "#3C4350" }}>
                  <Icon name={t.icon} size={14} /> {t.label}
                  {t.badge ? (
                    <span className="absolute -top-2 right-1 rounded-full px-1.5 text-[9.5px] font-bold text-[#1C1C1E]"
                      style={{ background: theme.accent }}>{t.badge}</span>
                  ) : null}
                </button>
              ))}
            </div>
          ) : null}

          {p.chips?.length ? (
            <div className="mb-3 flex flex-wrap gap-1.5">
              {p.chips.map((c) => (
                <button key={c} type="button" onClick={() => setChip(chip === c ? "" : c)}
                  data-testid={`lp-chip-${c.replace(/\s+/g, "-").toLowerCase()}`}
                  className="rounded-full border px-2.5 py-1 text-[11.5px] font-semibold transition-colors"
                  style={chip === c
                    ? { background: theme.primary, borderColor: theme.primary, color: "#fff" }
                    : { background: "#fff", borderColor: "#E3E6EB", color: "#4A5260" }}>
                  {c}
                </button>
              ))}
            </div>
          ) : null}

          <div className="flex flex-col gap-2 md:flex-row md:items-end">
            {(p.fields || []).map((f, i) => {
              const name = fieldName(f, i);
              return (
                <div key={`${name}-${i}`} className="min-w-0 flex-1">
                  <label className="mb-1 block text-[11.5px] font-bold text-[#4A5260]" htmlFor={`lp-hf-${name}`}>
                    {f.label}
                  </label>
                  {f.type === "select" && f.options?.length ? (
                    <SelectField value={values[name] || ""} onChange={(v) => set(name, v)}
                      testId={`lp-field-${name}`} className="w-full"
                      placeholder={f.placeholder || "Pilih"}
                      options={f.options.map((o) => ({ value: o, label: o }))} />
                  ) : f.type === "daterange" ? (
                    <div className="flex items-center gap-1.5">
                      <input id={`lp-hf-${name}`} type="date" value={values[`${name}_start`] || ""}
                        onChange={(e) => set(`${name}_start`, e.target.value)}
                        data-testid={`lp-field-${name}-start`} className={inputClass} />
                      <span className="text-[12px] text-[#9AA1AC]">–</span>
                      <input type="date" value={values[`${name}_end`] || ""}
                        onChange={(e) => set(`${name}_end`, e.target.value)}
                        data-testid={`lp-field-${name}-end`} className={inputClass} />
                    </div>
                  ) : (
                    <div className="flex h-10 items-center gap-2 rounded-lg border border-[#D9DEE6] bg-white px-2.5 focus-within:border-[#0B7BD3]">
                      <span style={{ color: theme.primary }}><Icon name={f.icon} size={14} /></span>
                      <input id={`lp-hf-${name}`} type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                        min={f.type === "number" ? 1 : undefined}
                        value={values[name] || ""} onChange={(e) => set(name, e.target.value)}
                        placeholder={f.placeholder || f.label} data-testid={`lp-field-${name}`}
                        className="w-full bg-transparent text-[13px] text-[#1C1C1E] outline-none placeholder:text-[#9AA1AC]" />
                    </div>
                  )}
                </div>
              );
            })}
            <button type="button" onClick={submit} data-testid="lp-search-submit"
              className="inline-flex h-10 items-center justify-center gap-2 px-5 text-[13.5px] font-bold text-white"
              style={{ background: theme.accent, borderRadius: btnRadius(theme) }}>
              <Search size={15} /> {p.search_label || "Cari"}
            </button>
          </div>
          {p.note ? <p className="mt-2 text-[11.5px] text-[#6B7280]">{p.note}</p> : null}
          {preview ? (
            <p className="mt-1 text-[11px] font-semibold text-[#8B93A0]">
              Mode pratinjau — pencarian tidak berpindah halaman.
            </p>
          ) : null}
        </div>
        {p.cta?.label ? (
          <div className="mt-4"><Btn cta={p.cta} theme={theme} onClick={() => onSearch?.(values, null, p.cta)} testId="lp-hero-cta" /></div>
        ) : null}
      </div>
    </section>
  );
}

export function HeroMedia({ p, theme, mode, first, onCta }) {
  const align = p.align === "center";
  const ctas = useMemo(() => p.ctas || [], [p.ctas]);
  const topPad = mode === "public" && first ? "pt-[136px]" : "pt-14";
  return (
    <section className={`relative px-5 pb-14 ${topPad}`} data-testid="lp-hero"
      style={{ background: p.media?.src ? `url(${p.media.src}) center/cover no-repeat` : theme.primary }}>
      <div className="absolute inset-0" style={{ background: `rgba(6,18,30,${(p.overlay ?? 45) / 100})` }} />
      <div className={`relative mx-auto max-w-[1120px] ${align ? "text-center" : ""}`}>
        {p.eyebrow ? (
          <p className="text-[11.5px] font-bold uppercase tracking-widest text-white/85">{p.eyebrow}</p>
        ) : null}
        <h1 className="mt-1 text-[30px] font-extrabold leading-tight text-white">{p.title}</h1>
        {p.subtitle ? <p className="mt-2 text-[14px] text-white/90">{p.subtitle}</p> : null}
        <div className={`mt-5 flex flex-wrap gap-2 ${align ? "justify-center" : ""}`}>
          {ctas.map((c, i) => (
            <Btn key={i} cta={c} theme={theme} onClick={() => onCta?.(c)} testId={`lp-hero-cta-${i}`} />
          ))}
        </div>
      </div>
    </section>
  );
}
