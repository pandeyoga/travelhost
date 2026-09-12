import { Type, Trash2, Eye, EyeOff, Monitor } from "lucide-react";
import SelectField from "@/components/shared/SelectField";
import { EmptyState } from "@/components/shared/DataStates";
import MediaPicker from "@/components/app/landing/MediaPicker";
import { ChipsEditor, CtaEditor, CtaListEditor, EntityIdsPicker, GalleryEditor, ItemsEditor,
  LeadFieldsEditor, NumberRow, SEARCH_FIELD_SHAPE, TextRow, ToggleRow }
  from "@/components/app/landing/BlockFieldEditors";

/**
 * LandingBlockForm.jsx — panel setelan SATU blok, sadar-tipe.
 *
 * Versi lama menebak kolom dari props yang "kebetulan ada" sehingga banyak setelan penting tak
 * pernah bisa diubah (daftar tab, kolom formulir, tenggat promo, batas jumlah kartu) dan beberapa
 * kolom muncul di blok yang tidak memakainya. Di sini setiap tipe blok punya peta kolomnya
 * sendiri — nama props mengikuti kontrak kanonik backend (`landing_blocks.BLOCK_TYPES`), yang
 * dijaga guardrail INV-LP-02 agar tak ada lagi setelan "hilang senyap".
 */
export const BLOCK_LABELS = {
  search_hero: "Hero + Pencarian", hero_media: "Hero Gambar/Video", value_props: "Keunggulan",
  fleet_grid: "Daftar Armada", destination_grid: "Daftar Destinasi", route_grid: "Rute Antar-Jemput",
  gallery: "Galeri Foto",
  video: "Video", testimonials: "Testimoni", price_estimator: "Estimasi Harga", faq: "FAQ",
  cta_band: "Banner CTA", wa_cta: "Tombol WhatsApp", lead_form: "Formulir Lead",
  countdown: "Hitung Mundur", trust_badges: "Lencana Kepercayaan", rich_text: "Teks Bebas",
  spacer: "Jarak",
};

const TEXTS = {
  search_hero: [["eyebrow", "Label kecil di atas judul"], ["title", "Judul utama"],
    ["subtitle", "Sub-judul", 2], ["search_label", "Label tombol cari"], ["note", "Catatan kecil"]],
  hero_media: [["eyebrow", "Label kecil di atas judul"], ["title", "Judul utama"],
    ["subtitle", "Sub-judul", 2]],
  value_props: [["title", "Judul bagian"]],
  fleet_grid: [["title", "Judul bagian"], ["subtitle", "Sub-judul"]],
  destination_grid: [["title", "Judul bagian"], ["subtitle", "Sub-judul"]],
  route_grid: [["title", "Judul bagian"], ["subtitle", "Sub-judul"]],
  gallery: [["title", "Judul bagian"]],
  video: [["title", "Judul bagian"]],
  testimonials: [["title", "Judul bagian"]],
  price_estimator: [["title", "Judul bagian"], ["subtitle", "Sub-judul"]],
  faq: [["title", "Judul bagian"]],
  cta_band: [["title", "Judul banner"], ["text", "Teks pendukung", 2]],
  wa_cta: [["title", "Judul"], ["text", "Teks pendukung", 2]],
  lead_form: [["title", "Judul formulir"], ["subtitle", "Sub-judul"],
    ["submit_label", "Label tombol kirim"], ["consent_text", "Teks persetujuan", 2],
    ["success_text", "Pesan setelah terkirim", 2]],
  countdown: [["title", "Judul"], ["subtitle", "Teks pendukung"]],
  trust_badges: [["title", "Judul (opsional)"]],
  rich_text: [["title", "Judul (opsional)"], ["html", "Teks bebas (boleh <b>, <a>, daftar)", 5]],
  spacer: [],
};

const DEVICES = [
  { value: "all", label: "Tampil di semua perangkat" },
  { value: "desktop", label: "Hanya desktop" },
  { value: "mobile", label: "Hanya ponsel" },
];

export default function LandingBlockForm({ block, onChange, onDelete, fleet = [], destinations = [], routes = [] }) {
  if (!block) {
    return (
      <EmptyState title="Pilih blok" testId="lp-form-empty"
        description="Klik salah satu blok di panel kiri untuk mengubah isinya." />
    );
  }
  const p = block.props || {};
  const type = block.type;
  const setProp = (key, value) => onChange({ ...block, props: { ...p, [key]: value } });

  const fleetOptions = (fleet || []).map((v) => ({ value: v.id, label: `${v.name} (${v.capacity || "-"} kursi)` }));
  const destOptions = (destinations || []).map((d) => ({ value: d.id, label: d.name }));
  const routeOptions = (routes || []).map((r) => ({
    value: r.id, label: `${r.from_label} → ${r.to_label}${r.code ? ` (${r.code})` : ""}` }));

  return (
    <section className="section-card" data-testid="lp-block-form">
      <div className="section-head flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-[13px]">
          <Type size={14} /> {BLOCK_LABELS[type] || type}
        </h2>
        <div className="flex gap-1">
          <button type="button" className="icon-button !h-7 !w-7" data-testid="lp-block-hide"
            aria-label={block.hidden ? "Tampilkan blok" : "Sembunyikan blok"}
            onClick={() => onChange({ ...block, hidden: !block.hidden })}>
            {block.hidden ? <EyeOff size={12} /> : <Eye size={12} />}
          </button>
          <button type="button" className="icon-button !h-7 !w-7" aria-label="Hapus blok"
            data-testid="lp-block-delete" onClick={onDelete}><Trash2 size={12} /></button>
        </div>
      </div>

      <div className="section-body space-y-2.5">
        {block.hidden ? (
          <p className="rounded-lg bg-[#FFF8EC] px-2.5 py-2 text-[11.5px] font-semibold text-[#8A5300]"
            data-testid="lp-block-hidden-note">
            Blok ini disembunyikan — tidak akan tampil di halaman publik.
          </p>
        ) : null}

        {(TEXTS[type] || []).map(([key, label, rows]) => (
          <TextRow key={key} id={`bf-${key}`} label={label} rows={rows || 0} testId={`lp-prop-${key}`}
            value={p[key]} onChange={(v) => setProp(key, v)} />
        ))}

        {type === "spacer" ? (
          <NumberRow id="bf-size" label="Tinggi jarak (piksel)" min={8} max={160} testId="lp-prop-size"
            value={p.size ?? 32} onChange={(v) => setProp("size", v)} />
        ) : null}

        {type === "rich_text" ? (
          <SelectField value={p.width || "narrow"} onChange={(v) => setProp("width", v)} className="w-full"
            testId="lp-prop-width"
            options={[{ value: "narrow", label: "Lebar teks: sempit (mudah dibaca)" },
              { value: "wide", label: "Lebar teks: penuh" }]} />
        ) : null}

        {["search_hero", "hero_media", "video"].includes(type) ? (
          <MediaPicker label={type === "video" ? "Berkas video" : "Foto/video latar"}
            kind={type === "video" ? "video" : "image"} value={p.media}
            onChange={(v) => setProp("media", v)} testId="lp-media" />
        ) : null}
        {["search_hero", "hero_media"].includes(type) ? (
          <NumberRow id="bf-overlay" label="Kegelapan lapisan gambar (%)" min={0} max={90}
            testId="lp-prop-overlay" value={p.overlay ?? 45} onChange={(v) => setProp("overlay", v)}
            hint="Naikkan bila teks kurang terbaca di atas foto." />
        ) : null}
        {type === "hero_media" ? (
          <SelectField value={p.align || "left"} onChange={(v) => setProp("align", v)} className="w-full"
            testId="lp-prop-align"
            options={[{ value: "left", label: "Teks rata kiri" }, { value: "center", label: "Teks di tengah" }]} />
        ) : null}

        {type === "search_hero" ? (
          <>
            <ChipsEditor chips={p.chips} onChange={(v) => setProp("chips", v)} />
            <div className="space-y-1.5">
              <p className="text-[11.5px] font-semibold text-[#3a3f4a]">Tab kategori</p>
              <ItemsEditor testId="lp-tabs" items={p.tabs} onChange={(v) => setProp("tabs", v)} max={7}
                addLabel="Tambah tab"
                shape={[["label", "Nama tab"], ["target", "Tujuan saat dicari (mis. /fleet)"], ["badge", "Label kecil (mis. Baru)"]]} />
            </div>
            <div className="space-y-1.5">
              <p className="text-[11.5px] font-semibold text-[#3a3f4a]">Kolom pencarian</p>
              <ItemsEditor testId="lp-sfields" items={p.fields} onChange={(v) => setProp("fields", v)}
                max={4} addLabel="Tambah kolom" shape={SEARCH_FIELD_SHAPE} />
            </div>
          </>
        ) : null}

        {type === "value_props" ? (
          <ItemsEditor testId="lp-vp" items={p.items} onChange={(v) => setProp("items", v)} max={6}
            addLabel="Tambah keunggulan"
            shape={[["title", "Judul keunggulan"], ["text", "Penjelasan singkat", "textarea"], ["icon", "Ikon (shield/clock/receipt/users/map/camera)"]]} />
        ) : null}
        {type === "trust_badges" ? (
          <ItemsEditor testId="lp-tb" items={p.items} onChange={(v) => setProp("items", v)} max={6}
            addLabel="Tambah lencana" shape={[["label", "Teks lencana"], ["icon", "Ikon (shield/check/star)"]]} />
        ) : null}
        {type === "faq" ? (
          <ItemsEditor testId="lp-faq" items={p.items} onChange={(v) => setProp("items", v)} max={12}
            addLabel="Tambah pertanyaan" shape={[["q", "Pertanyaan"], ["a", "Jawaban", "textarea"]]} />
        ) : null}
        {type === "gallery" ? (
          <>
            <GalleryEditor items={p.items} onChange={(v) => setProp("items", v)} />
            <NumberRow id="bf-cols" label="Jumlah kolom galeri" min={1} max={4} testId="lp-prop-columns"
              value={p.columns ?? 3} onChange={(v) => setProp("columns", v)} />
          </>
        ) : null}
        {type === "video" ? (
          <>
            <ToggleRow label="Putar otomatis (tanpa suara)" checked={p.autoplay}
              onChange={(v) => setProp("autoplay", v)} testId="lp-prop-autoplay" />
            <ToggleRow label="Ulangi terus" checked={p.loop} onChange={(v) => setProp("loop", v)}
              testId="lp-prop-loop" />
          </>
        ) : null}

        {["fleet_grid", "destination_grid", "route_grid", "testimonials"].includes(type) ? (
          <NumberRow id="bf-limit" label="Maksimal kartu ditampilkan" min={1} max={12} testId="lp-prop-limit"
            value={p.limit ?? 6} onChange={(v) => setProp("limit", v)} />
        ) : null}
        {["fleet_grid", "destination_grid", "route_grid"].includes(type) ? (
          <ToggleRow label="Tampilkan harga" checked={p.show_price !== false}
            onChange={(v) => setProp("show_price", v)} testId="lp-prop-showprice"
            hint="Harga mempercepat keputusan, tapi matikan bila tarif sedang berubah." />
        ) : null}
        {type === "route_grid" ? (
          <EntityIdsPicker label="Pilih rute tertentu (kosongkan = semua rute aktif)" ids={p.ids}
            options={routeOptions} onChange={(v) => setProp("ids", v)} testId="lp-route-ids" />
        ) : null}
        {type === "fleet_grid" ? (
          <>
            <TextRow id="bf-vt" label="Saring jenis unit (mis. hiace)" testId="lp-prop-vehicletype"
              value={p.vehicle_type} onChange={(v) => setProp("vehicle_type", v)}
              hint="Kosongkan untuk menampilkan semua jenis." />
            <EntityIdsPicker label="Pilih unit tertentu" ids={p.ids} options={fleetOptions}
              onChange={(v) => setProp("ids", v)} testId="lp-fleet-ids" />
          </>
        ) : null}
        {type === "destination_grid" ? (
          <>
            <TextRow id="bf-region" label="Saring wilayah (mis. bali)" testId="lp-prop-region"
              value={p.region} onChange={(v) => setProp("region", v)}
              hint="Kosongkan untuk menampilkan semua wilayah." />
            <EntityIdsPicker label="Pilih destinasi tertentu" ids={p.ids} options={destOptions}
              onChange={(v) => setProp("ids", v)} testId="lp-dest-ids" />
          </>
        ) : null}
        {type === "price_estimator" ? (
          <NumberRow id="bf-pax" label="Jumlah orang bawaan" min={1} max={60} testId="lp-prop-pax"
            value={p.default_pax ?? 10} onChange={(v) => setProp("default_pax", v)} />
        ) : null}

        {type === "lead_form" ? (
          <>
            <LeadFieldsEditor fields={p.fields} onChange={(v) => setProp("fields", v)} />
            <ToggleRow label="Wajib centang persetujuan" checked={p.require_consent !== false}
              onChange={(v) => setProp("require_consent", v)} testId="lp-prop-consent"
              hint="Persetujuan adalah dasar hukum menghubungi & mengunggah audiens ke platform iklan." />
          </>
        ) : null}
        {type === "countdown" ? (
          <div className="space-y-1">
            <label className="text-[11.5px] font-semibold text-[#3a3f4a]" htmlFor="bf-deadline">
              Tenggat promo
            </label>
            <input id="bf-deadline" type="datetime-local" value={(p.deadline || "").slice(0, 16)}
              data-testid="lp-prop-deadline" onChange={(e) => setProp("deadline", e.target.value)}
              className="h-8 w-full rounded-lg border border-[#E5E5EA] bg-white px-2.5 text-[12.5px] outline-none focus:border-[#007AFF]" />
            <p className="text-[10.5px] text-[#8E8E93]">Hitung mundur berdetak nyata di halaman publik.</p>
          </div>
        ) : null}

        {["search_hero", "wa_cta"].includes(type) ? (
          <CtaEditor cta={p.cta} onChange={(v) => setProp("cta", v)} />
        ) : null}
        {["hero_media", "cta_band"].includes(type) ? (
          <CtaListEditor ctas={p.ctas} onChange={(v) => setProp("ctas", v)} max={2} />
        ) : null}
        {["fleet_grid", "destination_grid", "route_grid"].includes(type) ? (
          <CtaEditor cta={p.cta} onChange={(v) => setProp("cta", v)} />
        ) : null}
        {type === "cta_band" ? (
          <SelectField value={p.tone || "dark"} onChange={(v) => setProp("tone", v)} className="w-full"
            testId="lp-prop-tone"
            options={[{ value: "dark", label: "Latar warna utama" }, { value: "light", label: "Latar putih" }]} />
        ) : null}

        <div className="space-y-1 border-t border-[#F0F1F3] pt-2.5">
          <p className="flex items-center gap-1.5 text-[11px] font-semibold text-[#6B6B73]">
            <Monitor size={11} /> Tampil di perangkat
          </p>
          <SelectField value={block.device || "all"} onChange={(v) => onChange({ ...block, device: v })}
            options={DEVICES} testId="lp-prop-device" className="w-full" />
        </div>
      </div>
    </section>
  );
}
