import { Plus, Trash2, ArrowUp, ArrowDown, Images } from "lucide-react";
import { useState } from "react";
import SelectField from "@/components/shared/SelectField";
import { Switch } from "@/components/ui/switch";
import MediaLibrary from "@/components/app/landing/MediaLibrary";

/**
 * BlockFieldEditors.jsx — kumpulan editor kecil yang dipakai panel setelan blok.
 *
 * Dipisah dari `LandingBlockForm` karena 17 tipe blok membutuhkan pola yang SAMA (daftar item,
 * chip, tab, tombol, pilihan entitas). Menyatukannya di satu tempat membuat perilaku editor
 * konsisten — dan menjaga tiap berkas di bawah batas ukuran yang ditegakkan gate.
 */
const inputCls =
  "h-8 w-full rounded-lg border border-[#E5E5EA] bg-white px-2.5 text-[12.5px] text-[#1C1C1E] " +
  "outline-none focus:border-[#007AFF]";

export function TextRow({ id, label, value, onChange, placeholder, rows = 0, testId, hint }) {
  return (
    <div className="space-y-1">
      <label className="text-[11.5px] font-semibold text-[#3a3f4a]" htmlFor={id}>{label}</label>
      {rows > 0 ? (
        <textarea id={id} rows={rows} value={value ?? ""} placeholder={placeholder} data-testid={testId}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-lg border border-[#E5E5EA] bg-white px-2.5 py-1.5 text-[12.5px] outline-none focus:border-[#007AFF]" />
      ) : (
        <input id={id} value={value ?? ""} placeholder={placeholder} data-testid={testId}
          onChange={(e) => onChange(e.target.value)} className={inputCls} />
      )}
      {hint ? <p className="text-[10.5px] text-[#8E8E93]">{hint}</p> : null}
    </div>
  );
}

export function NumberRow({ id, label, value, onChange, min = 0, max = 999, testId, hint }) {
  return (
    <div className="space-y-1">
      <label className="text-[11.5px] font-semibold text-[#3a3f4a]" htmlFor={id}>{label}</label>
      <input id={id} type="number" min={min} max={max} value={value ?? 0} data-testid={testId}
        onChange={(e) => onChange(Number(e.target.value))} className={`${inputCls} tabular-nums`} />
      {hint ? <p className="text-[10.5px] text-[#8E8E93]">{hint}</p> : null}
    </div>
  );
}

export function ToggleRow({ label, checked, onChange, testId, hint }) {
  return (
    <div className="flex items-start justify-between gap-2 rounded-lg bg-[#F7F8FA] px-2.5 py-2">
      <div className="min-w-0">
        <p className="text-[12px] font-semibold text-[#3a3f4a]">{label}</p>
        {hint ? <p className="text-[10.5px] text-[#8E8E93]">{hint}</p> : null}
      </div>
      <Switch checked={!!checked} onCheckedChange={onChange} data-testid={testId} />
    </div>
  );
}

const CTA_TARGETS = ["/quotation", "/booking", "/fleet", "/destinations", "/contact", "#formulir"];
const CTA_KINDS = [
  { value: "internal", label: "Halaman situs ini" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "external", label: "Tautan luar" },
  { value: "anchor", label: "Gulir ke blok (anchor)" },
];

export function CtaEditor({ cta, onChange, onRemove, index = 0 }) {
  const c = cta || {};
  const set = (k, v) => onChange({ ...c, [k]: v });
  return (
    <div className="space-y-1.5 rounded-lg bg-[#F7F8FA] p-2.5" data-testid={`lp-cta-${index}`}>
      <div className="flex items-center justify-between">
        <p className="text-[11.5px] font-semibold text-[#3a3f4a]">Tombol aksi {index + 1}</p>
        {onRemove ? (
          <button type="button" className="icon-button !h-6 !w-6" onClick={onRemove}
            aria-label="Hapus tombol" data-testid={`lp-cta-remove-${index}`}><Trash2 size={11} /></button>
        ) : null}
      </div>
      <input value={c.label ?? ""} placeholder="Label tombol (mis. Minta Penawaran)"
        data-testid={`lp-cta-label-${index}`} onChange={(e) => set("label", e.target.value)} className={inputCls} />
      <SelectField value={c.kind || "internal"} onChange={(v) => set("kind", v)} options={CTA_KINDS}
        testId={`lp-cta-kind-${index}`} className="w-full" />
      {c.kind === "whatsapp" ? (
        <>
          <input value={c.target ?? ""} placeholder="Nomor WA tujuan (kosong = nomor default)"
            data-testid={`lp-cta-target-${index}`} onChange={(e) => set("target", e.target.value)} className={inputCls} />
          <textarea rows={2} value={c.message ?? ""} placeholder="Pesan awal yang sudah terisi di WhatsApp"
            data-testid={`lp-cta-message-${index}`} onChange={(e) => set("message", e.target.value)}
            className="w-full rounded-lg border border-[#E5E5EA] bg-white px-2.5 py-1.5 text-[12.5px] outline-none focus:border-[#007AFF]" />
        </>
      ) : (
        <>
          <input value={c.target ?? ""} placeholder="Tujuan (mis. /quotation)" list={`lp-cta-targets-${index}`}
            data-testid={`lp-cta-target-${index}`} onChange={(e) => set("target", e.target.value)} className={inputCls} />
          <datalist id={`lp-cta-targets-${index}`}>
            {CTA_TARGETS.map((t) => <option key={t} value={t} />)}
          </datalist>
        </>
      )}
      <SelectField value={c.style || "primary"} onChange={(v) => set("style", v)} className="w-full"
        testId={`lp-cta-style-${index}`}
        options={[{ value: "primary", label: "Gaya: utama (terisi)" }, { value: "secondary", label: "Gaya: garis tepi" }]} />
      <ToggleRow label="Teruskan atribusi iklan" checked={c.keep_attribution !== false}
        onChange={(v) => set("keep_attribution", v)} testId={`lp-cta-attr-${index}`}
        hint="Wajib aktif agar lead tetap terhubung ke iklan yang membayarnya." />
    </div>
  );
}

export function CtaListEditor({ ctas, onChange, max = 2 }) {
  const list = ctas || [];
  return (
    <div className="space-y-2">
      {list.map((c, i) => (
        <CtaEditor key={i} cta={c} index={i}
          onChange={(next) => onChange(list.map((x, j) => (j === i ? next : x)))}
          onRemove={list.length > 1 ? () => onChange(list.filter((_, j) => j !== i)) : undefined} />
      ))}
      {list.length < max ? (
        <button type="button" className="secondary-button !h-8 w-full" data-testid="lp-cta-add"
          onClick={() => onChange([...list, { label: "Tombol baru", kind: "internal", target: "/quotation",
            style: list.length ? "secondary" : "primary", keep_attribution: true }])}>
          <Plus size={12} /> Tambah tombol
        </button>
      ) : null}
    </div>
  );
}

/** Editor daftar objek generik (keunggulan, FAQ, lencana). `shape` menentukan kolomnya. */
export function ItemsEditor({ items, onChange, shape, addLabel = "Tambah item", max = 12, testId = "lp-items" }) {
  const list = items || [];
  const blank = Object.fromEntries(shape.map(([k]) => [k, ""]));
  const move = (i, dir) => {
    const j = i + dir;
    if (j < 0 || j >= list.length) return;
    const next = [...list];
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  };
  return (
    <div className="space-y-2" data-testid={testId}>
      {list.map((it, i) => (
        <div key={i} className="space-y-1.5 rounded-lg bg-[#F7F8FA] p-2">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-semibold text-[#6B6B73]">#{i + 1}</p>
            <div className="flex gap-1">
              <button type="button" className="icon-button !h-6 !w-6" onClick={() => move(i, -1)}
                aria-label="Naik" data-testid={`${testId}-up-${i}`}><ArrowUp size={10} /></button>
              <button type="button" className="icon-button !h-6 !w-6" onClick={() => move(i, 1)}
                aria-label="Turun" data-testid={`${testId}-down-${i}`}><ArrowDown size={10} /></button>
              <button type="button" className="icon-button !h-6 !w-6" data-testid={`${testId}-del-${i}`}
                onClick={() => onChange(list.filter((_, j) => j !== i))} aria-label="Hapus">
                <Trash2 size={10} />
              </button>
            </div>
          </div>
          {shape.map(([key, label, kind]) => (
            kind === "textarea" ? (
              <textarea key={key} rows={2} value={it[key] ?? ""} placeholder={label}
                data-testid={`${testId}-${i}-${key}`}
                onChange={(e) => onChange(list.map((x, j) => (j === i ? { ...x, [key]: e.target.value } : x)))}
                className="w-full rounded-lg border border-[#E5E5EA] bg-white px-2 py-1.5 text-[12px] outline-none focus:border-[#007AFF]" />
            ) : (
              <input key={key} value={it[key] ?? ""} placeholder={label} data-testid={`${testId}-${i}-${key}`}
                onChange={(e) => onChange(list.map((x, j) => (j === i ? { ...x, [key]: e.target.value } : x)))}
                className={inputCls} />
            )
          ))}
        </div>
      ))}
      {list.length < max ? (
        <button type="button" className="secondary-button !h-8 w-full" data-testid={`${testId}-add`}
          onClick={() => onChange([...list, blank])}><Plus size={12} /> {addLabel}</button>
      ) : null}
    </div>
  );
}

export function ChipsEditor({ chips, onChange }) {
  return (
    <TextRow id="lp-chips" label="Chip cepat (pisahkan dengan koma)" testId="lp-prop-chips"
      value={(chips || []).join(", ")} placeholder="Hiace, Elf, Bus"
      onChange={(v) => onChange(v.split(",").map((s) => s.trim()).filter(Boolean))}
      hint="Dipakai pengunjung untuk mempersempit pencarian dengan satu klik." />
  );
}

/** Galeri: banyak media sekaligus. */
export function GalleryEditor({ items, onChange }) {
  const [open, setOpen] = useState(false);
  const list = items || [];
  const backend = process.env.REACT_APP_BACKEND_URL || "";
  const abs = (u) => (u && u.startsWith("/") ? `${backend}${u}` : u || "");
  return (
    <div className="space-y-1.5 rounded-lg bg-[#F7F8FA] p-2.5">
      <p className="text-[11.5px] font-semibold text-[#3a3f4a]">Foto galeri ({list.length})</p>
      {!list.length ? (
        <p className="rounded-lg border border-dashed border-[#D9DEE6] bg-white px-2 py-3 text-center text-[11.5px] text-[#8E8E93]"
          data-testid="lp-gallery-editor-empty">Belum ada foto di galeri ini</p>
      ) : (
        <div className="grid grid-cols-4 gap-1.5" data-testid="lp-gallery-editor">
          {list.map((m, i) => (
            <div key={i} className="relative overflow-hidden rounded border border-[#E5E5EA] bg-white">
              <img src={abs(m.thumb_url || m.src)} alt={m.alt || ""} className="h-12 w-full object-cover" />
              <button type="button" onClick={() => onChange(list.filter((_, j) => j !== i))}
                aria-label="Hapus foto" data-testid={`lp-gallery-del-${i}`}
                className="absolute right-0.5 top-0.5 rounded bg-black/60 p-0.5 text-white">
                <Trash2 size={9} />
              </button>
            </div>
          ))}
        </div>
      )}
      <button type="button" className="secondary-button !h-8 w-full" onClick={() => setOpen(true)}
        data-testid="lp-gallery-add"><Images size={12} /> Tambah foto dari Media Library</button>
      <MediaLibrary open={open} onOpenChange={setOpen} pickKind="image" multiple
        title="Pilih foto galeri"
        description="Centang beberapa foto sekaligus — semuanya langsung ditambahkan ke galeri blok ini."
        onPick={(assets) => {
          // Mode banyak mengirim ARRAY. Sebelumnya galeri hanya bisa ditambah satu-satu sehingga
          // mengisi galeri 12 foto berarti 12 kali membuka dialog — pekerjaan yang membuat orang
          // menyerah dan meninggalkan galeri kosong di halaman iklan yang sudah dibayar.
          const picked = Array.isArray(assets) ? assets : [assets];
          const existing = new Set(list.map((m) => m.media_id));
          const added = picked
            .filter((a) => a && !existing.has(a.id))
            .map((a) => ({ media_id: a.id, src: a.url, thumb_url: a.thumb_url || a.url,
              kind: a.kind, alt: a.alt || "" }));
          if (added.length) onChange([...list, ...added]);
        }} />
    </div>
  );
}

/** Pilih entitas (armada/destinasi) yang ditampilkan grid; kosong = otomatis terbaru. */
export function EntityIdsPicker({ label, ids, options, onChange, testId }) {
  const list = ids || [];
  const toggle = (id) => onChange(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  return (
    <div className="space-y-1.5 rounded-lg bg-[#F7F8FA] p-2.5">
      <p className="text-[11.5px] font-semibold text-[#3a3f4a]">{label}</p>
      {!options.length ? (
        <p className="text-[11px] text-[#8E8E93]" data-testid={`${testId}-empty`}>Belum ada data untuk dipilih.</p>
      ) : (
        <div className="max-h-[132px] space-y-1 overflow-y-auto" data-testid={testId}>
          {options.map((o) => (
            <label key={o.value} className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-[11.5px] text-[#3a3f4a] hover:bg-white">
              <input type="checkbox" checked={list.includes(o.value)} onChange={() => toggle(o.value)}
                data-testid={`${testId}-${o.value}`} className="h-3.5 w-3.5 accent-[#007AFF]" />
              <span className="truncate">{o.label}</span>
            </label>
          ))}
        </div>
      )}
      <p className="text-[10.5px] text-[#8E8E93]">Kosongkan untuk menampilkan data terbaru otomatis.</p>
    </div>
  );
}

const LEAD_FIELD_LABELS = {
  name: "Nama", phone: "Nomor WhatsApp", email: "Email", origin: "Titik jemput",
  destination: "Tujuan", start: "Tanggal mulai", end: "Tanggal selesai", pax: "Jumlah orang",
  vehicle_type: "Jenis unit", message: "Catatan",
};

export function LeadFieldsEditor({ fields, onChange }) {
  const list = fields || [];
  const toggle = (f) => {
    if (f === "name" || f === "phone") return; // wajib — tanpa keduanya lead tak bisa dihubungi
    onChange(list.includes(f) ? list.filter((x) => x !== f) : [...list, f]);
  };
  return (
    <div className="space-y-1.5 rounded-lg bg-[#F7F8FA] p-2.5">
      <p className="text-[11.5px] font-semibold text-[#3a3f4a]">Kolom formulir</p>
      <div className="grid grid-cols-2 gap-1" data-testid="lp-lead-fields">
        {Object.entries(LEAD_FIELD_LABELS).map(([f, label]) => {
          const locked = f === "name" || f === "phone";
          return (
            <label key={f} className={`flex items-center gap-1.5 rounded px-1 py-0.5 text-[11.5px] ${
              locked ? "text-[#8E8E93]" : "cursor-pointer text-[#3a3f4a] hover:bg-white"}`}>
              <input type="checkbox" checked={list.includes(f) || locked} disabled={locked}
                onChange={() => toggle(f)} data-testid={`lp-lead-field-${f}`}
                className="h-3.5 w-3.5 accent-[#007AFF]" />
              <span className="truncate">{label}{locked ? " · wajib" : ""}</span>
            </label>
          );
        })}
      </div>
      <p className="text-[10.5px] text-[#8E8E93]">
        Makin sedikit kolom, makin tinggi konversi. Nama &amp; WhatsApp selalu ada.
      </p>
    </div>
  );
}

export const SEARCH_FIELD_SHAPE = [
  ["label", "Label kolom (mis. Tujuan)"],
  ["name", "Nama data (mis. destination)"],
  ["placeholder", "Contoh isi"],
];
