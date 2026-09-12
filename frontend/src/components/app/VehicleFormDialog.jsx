import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, ChevronDown, Globe } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import GalleryManager from "@/components/cms/GalleryManager";
import TourSceneBuilder from "@/components/cms/TourSceneBuilder";
import ExteriorFramesEditor from "@/components/cms/ExteriorFramesEditor";
import SpecsEditor from "@/components/cms/SpecsEditor";

const TYPES = [
  { v: "hiace_premio", l: "Hiace Premio" }, { v: "hiace", l: "Hiace Commuter" },
  { v: "elf", l: "Isuzu Elf" }, { v: "bus", l: "Medium Bus" }, { v: "avanza", l: "Avanza/MPV" },
];
// Status OPERASIONAL (available / on_trip / maintenance) diatur otomatis oleh trip & modul
// Maintenance — bukan diisi manual. Master data hanya memutuskan LIFECYCLE: aktif vs nonaktif.
const OPS_STATUS_LABEL = { on_trip: "Dalam Perjalanan (trip aktif)", maintenance: "Perawatan (jadwal servis aktif)" };
const LIFECYCLE = [
  { v: "active", l: "Aktif — bisa dijadwalkan & dijual" },
  { v: "inactive", l: "Nonaktif — keluar dari daftar jual & dispatch" },
];
// Kepemilikan menentukan apakah unit boleh dijual di web (publishable_filter menuntut `owned`)
// dan ke siapa biaya sub-charter dibayarkan. Sebelumnya field ini TIDAK ADA di formulir sama
// sekali padahal backend & data memakainya — unit mitra hanya bisa dibuat lewat API/seed,
// dan ops tidak punya cara melihat/mengubahnya. Mitra diambil dari koleksi `partners`.
const OWNERSHIPS = [{ v: "owned", l: "Milik sendiri" }, { v: "partner", l: "Milik mitra" }];

const toDateInput = (v) => (v ? String(v).slice(0, 10) : "");
const EMPTY = {
  name: "", plate_number: "", type: "hiace_premio", capacity: "", lifecycle: "active",
  kir_expiry: "", tax_expiry: "", next_service_date: "", odometer: "", notes: "",
  price_from: "", day_rate: "", publish_to_web: true, year: "", color: "", highlights: "", photos: [], gallery: [], tour_scenes: [],
  exterior_frames: [], rental_terms: "", features: "", specs: [],
  ownership: "owned", partner_id: "",
};
// RC-B (INV-PRICE-02): `price_from`/`day_rate` tinggal READ-ONLY di sini — jalur tulisnya
// hanya Pengaturan → Master Harga. Form ini tidak lagi mengirim field harga apa pun.

export default function VehicleFormDialog({ open, onOpenChange, initial, onSaved }) {
  const editing = Boolean(initial && initial.id);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [showWeb, setShowWeb] = useState(false);
  const [partners, setPartners] = useState([]);

  // Daftar mitra diambil dari KOLEKSI (bukan diketik bebas): salah ketik nama mitra membuat
  // unit tidak pernah bisa ditagihkan ke mitra yang benar.
  useEffect(() => {
    if (!open) return;
    apiClient.get("/partners").then((r) => setPartners(Array.isArray(r.data) ? r.data : []))
      .catch(() => setPartners([]));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (editing) {
      const web = {
        price_from: initial.price_from ?? "", day_rate: initial.day_rate ?? "",
        publish_to_web: initial.publish_to_web !== false, year: initial.year ?? "", color: initial.color || "",
        ownership: initial.ownership || "owned", partner_id: initial.partner_id || "",
        highlights: Array.isArray(initial.highlights) ? initial.highlights.join("\n") : "",
        photos: Array.isArray(initial.photos) ? initial.photos : [],
        gallery: Array.isArray(initial.gallery) ? initial.gallery : [],
        tour_scenes: Array.isArray(initial.tour_scenes) ? initial.tour_scenes : [],
        exterior_frames: Array.isArray(initial.exterior_frames) ? initial.exterior_frames : [],
        rental_terms: Array.isArray(initial.rental_terms) ? initial.rental_terms.join("\n") : "",
        features: Array.isArray(initial.features) ? initial.features.join("\n") : "",
        specs: Array.isArray(initial.specs) ? initial.specs : [],
      };
      setForm({
        name: initial.name || "", plate_number: initial.plate_number || "",
        type: initial.type || "hiace_premio", capacity: initial.capacity ?? "",
        lifecycle: ["inactive", "sold"].includes(initial.status) ? "inactive" : "active", kir_expiry: toDateInput(initial.kir_expiry),
        tax_expiry: toDateInput(initial.tax_expiry), next_service_date: toDateInput(initial.next_service_date),
        odometer: initial.odometer ?? "", notes: initial.notes || "", ...web,
      });
      setShowWeb(Boolean(web.photos.length || web.gallery.length || web.tour_scenes.length || web.exterior_frames.length || web.price_from));
    } else {
      setForm(EMPTY);
      setShowWeb(false);
    }
  }, [open, editing, initial]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.name.trim() || !form.plate_number.trim()) {
      toast.error("Nama & nomor plat wajib diisi");
      return;
    }
    setSaving(true);
    const wasInactive = editing && ["inactive", "sold"].includes(initial.status);
    const payload = {
      name: form.name.trim(), plate_number: form.plate_number.trim(), type: form.type,
      capacity: Number(form.capacity) || 0,
      kir_expiry: form.kir_expiry || null, tax_expiry: form.tax_expiry || null,
      next_service_date: form.next_service_date || null,
      odometer: Number(form.odometer) || 0, notes: form.notes,
      // Konten web (URL-based, P10/FASE 5) — harga TIDAK dikirim dari form ini (INV-PRICE-02)
      publish_to_web: Boolean(form.publish_to_web), year: Number(form.year) || 0, color: form.color,
      ownership: form.ownership || "owned",
      partner_id: form.ownership === "partner" ? (form.partner_id || "") : "",
      highlights: String(form.highlights || "").split("\n").map((s) => s.trim()).filter(Boolean),
      photos: Array.isArray(form.photos) ? form.photos : [],
      gallery: Array.isArray(form.gallery) ? form.gallery : [],
      tour_scenes: Array.isArray(form.tour_scenes) ? form.tour_scenes : [],
      exterior_frames: Array.isArray(form.exterior_frames) ? form.exterior_frames.map((u) => (typeof u === "string" ? u : u?.url || "")).filter(Boolean) : [],
      rental_terms: String(form.rental_terms || "").split("\n").map((s) => s.trim()).filter(Boolean),
      // Lifecycle: kirim status hanya saat berubah; status operasional (on_trip/maintenance) TIDAK disentuh form ini.
      ...(!editing ? { status: form.lifecycle === "inactive" ? "inactive" : "available" }
        : form.lifecycle === "inactive" && !wasInactive ? { status: "inactive" }
          : form.lifecycle === "active" && wasInactive ? { status: "available" } : {}),
      features: String(form.features || "").split("\n").map((s) => s.trim()).filter(Boolean),
      specs: (Array.isArray(form.specs) ? form.specs : []).filter((r) => (r.label || "").trim() && (r.value || "").trim()),
    };
    try {
      if (editing) await apiClient.patch(`/vehicles/${initial.id}`, payload);
      else await apiClient.post("/vehicles", payload);
      toast.success(editing ? "Armada diperbarui" : "Armada ditambahkan");
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan armada");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl" data-testid="vehicle-form-dialog">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit Armada" : "Tambah Armada"}</DialogTitle>
          <DialogDescription>Data master kendaraan, jadwal dokumen (KIR/pajak/servis) & konten web.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Nama Armada</Label>
              <Input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="Hiace Premio 03" data-testid="vf-name" />
            </div>
            <div className="space-y-1.5">
              <Label>Nomor Plat</Label>
              <Input value={form.plate_number} onChange={(e) => set("plate_number", e.target.value)} placeholder="D 1234 AA" data-testid="vf-plate" />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label>Tipe</Label>
              <Select value={form.type} onValueChange={(v) => set("type", v)}>
                <SelectTrigger data-testid="vf-type"><SelectValue /></SelectTrigger>
                <SelectContent>{TYPES.map((t) => <SelectItem key={t.v} value={t.v}>{t.l}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Kapasitas (pax)</Label>
              <Input type="number" value={form.capacity} onChange={(e) => set("capacity", e.target.value)} placeholder="14" data-testid="vf-capacity" />
            </div>
            <div className="space-y-1.5">
              <Label>Kepemilikan</Label>
              <Select value={form.ownership} onValueChange={(v) => set("ownership", v)}>
                <SelectTrigger data-testid="vf-ownership"><SelectValue /></SelectTrigger>
                <SelectContent>{OWNERSHIPS.map((o) => (
                  <SelectItem key={o.v} value={o.v} data-testid={`vf-ownership-opt-${o.v}`}>{o.l}</SelectItem>
                ))}</SelectContent>
              </Select>
            </div>
            {form.ownership === "partner" ? (
              <div className="space-y-1.5 sm:col-span-2">
                <Label>Mitra pemilik unit *</Label>
                <Select value={form.partner_id || ""} onValueChange={(v) => set("partner_id", v)}>
                  <SelectTrigger data-testid="vf-partner"><SelectValue placeholder="Pilih mitra terdaftar" /></SelectTrigger>
                  <SelectContent>{partners.map((pt) => (
                    <SelectItem key={pt.id} value={pt.id} data-testid={`vf-partner-opt-${pt.id}`}>
                      {pt.name}{pt.city ? ` · ${pt.city}` : ""}
                    </SelectItem>
                  ))}</SelectContent>
                </Select>
                <p className="text-[11.5px] text-[#8E8E93]">
                  Unit mitra TIDAK dijual di website (hanya untuk sub-charter) — itu sebabnya
                  kepemilikan wajib benar.
                </p>
              </div>
            ) : null}
            <div className="space-y-1.5">
              <Label>Status Unit</Label>
              <Select value={form.lifecycle} onValueChange={(v) => set("lifecycle", v)}>
                <SelectTrigger data-testid="vf-lifecycle"><SelectValue /></SelectTrigger>
                <SelectContent>{LIFECYCLE.map((s) => <SelectItem key={s.v} value={s.v} data-testid={`vf-lifecycle-opt-${s.v}`}>{s.l}</SelectItem>)}</SelectContent>
              </Select>
              {editing && OPS_STATUS_LABEL[initial?.status] && form.lifecycle === "active" ? (
                <p className="text-[11.5px] text-[#8E8E93]" data-testid="vf-ops-status">
                  Status operasional saat ini: <b>{OPS_STATUS_LABEL[initial.status]}</b> — otomatis dari trip & Maintenance.
                </p>
              ) : null}
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label>KIR Berlaku s/d</Label>
              <Input type="date" value={form.kir_expiry} onChange={(e) => set("kir_expiry", e.target.value)} data-testid="vf-kir" />
            </div>
            <div className="space-y-1.5">
              <Label>Pajak s/d</Label>
              <Input type="date" value={form.tax_expiry} onChange={(e) => set("tax_expiry", e.target.value)} data-testid="vf-tax" />
            </div>
            <div className="space-y-1.5">
              <Label>Servis Berikutnya</Label>
              <Input type="date" value={form.next_service_date} onChange={(e) => set("next_service_date", e.target.value)} data-testid="vf-service" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Odometer (km)</Label>
            <Input type="number" value={form.odometer} onChange={(e) => set("odometer", e.target.value)} placeholder="84000" data-testid="vf-odometer" />
          </div>
          <div className="space-y-1.5">
            <Label>Catatan</Label>
            <Textarea value={form.notes} onChange={(e) => set("notes", e.target.value)} placeholder="Fitur / catatan unit" data-testid="vf-notes" />
          </div>

          {/* Konten Web (galeri + tur 360) */}
          <div className="rounded-xl border border-border">
            <button type="button" onClick={() => setShowWeb((s) => !s)} data-testid="vf-toggle-web"
              className="flex w-full items-center justify-between px-3 py-2.5 text-left">
              <span className="flex items-center gap-2 text-[13px] font-semibold text-[#1C1C1E]"><Globe size={14} /> Konten Web (tampil di situs publik)</span>
              <ChevronDown size={16} className={`text-muted-foreground transition ${showWeb ? "rotate-180" : ""}`} />
            </button>
            {showWeb ? (
              <div className="space-y-3 border-t border-border p-3" data-testid="vf-web-section">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <div className="space-y-1.5 sm:col-span-2">
                    <Label>Tarif resmi / hari</Label>
                    <div className="rounded-[10px] border border-[#E5E5EA] bg-[#F7F8FA] px-3 py-2.5 text-[13px] text-[#1C1C1E]" data-testid="vf-day-rate">
                      {Number(form.day_rate) > 0
                        ? `Rp ${Number(form.day_rate).toLocaleString("id-ID")} / hari (tarif khusus unit)`
                        : "Memakai tarif per tipe (lihat Pengaturan → Master Harga)"}
                    </div>
                    <p className="text-[11.5px] text-[#8E8E93]">
                      Harga hanya bisa diubah di <b>Pengaturan → Aturan Harga (Master Harga)</b> —
                      satu pintu agar tidak ada dua sumber harga yang saling menimpa.
                    </p>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Tayang & bisa dipesan di website</Label>
                    <label className="flex cursor-pointer items-center gap-2 rounded-[10px] border border-[#E5E5EA] px-3 py-2.5 text-[13px] text-[#1C1C1E]">
                      <input type="checkbox" checked={Boolean(form.publish_to_web)}
                        onChange={(e) => set("publish_to_web", e.target.checked)} data-testid="vf-publish-web" />
                      Tampilkan unit ini di katalog &amp; pemesanan online
                    </label>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Tahun</Label>
                    <Input type="number" value={form.year} onChange={(e) => set("year", e.target.value)} placeholder="2023" data-testid="vf-year" />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Warna</Label>
                    <Input value={form.color} onChange={(e) => set("color", e.target.value)} placeholder="Putih Mutiara" data-testid="vf-color" />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label>Keunggulan (1 per baris)</Label>
                  <Textarea value={form.highlights} onChange={(e) => set("highlights", e.target.value)} placeholder={"AC Double Blower\nKursi Reclining\nWifi & USB"} data-testid="vf-highlights" />
                </div>
                <div className="space-y-1.5">
                  <Label>Fasilitas Unit (1 per baris — tab Fasilitas di web)</Label>
                  <Textarea value={form.features} onChange={(e) => set("features", e.target.value)} placeholder={"Full AC\nKursi Reclining\nWifi Unlimited\nKaraoke & TV Roof"} data-testid="vf-features" />
                </div>
                <div className="space-y-1.5">
                  <Label>Spesifikasi (label &amp; nilai — section Spesifikasi di web)</Label>
                  <SpecsEditor value={form.specs} onChange={(arr) => set("specs", arr)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Foto Utama (cover di urutan pertama)</Label>
                  <GalleryManager value={form.photos} onChange={(arr) => set("photos", arr)} mode="urls" />
                </div>
                <div className="space-y-1.5">
                  <Label>Galeri (dengan keterangan)</Label>
                  <GalleryManager value={form.gallery} onChange={(arr) => set("gallery", arr)} mode="captioned" />
                </div>
                <div className="space-y-1.5">
                  <Label>Tur Kabin 360°</Label>
                  <TourSceneBuilder value={form.tour_scenes} onChange={(arr) => set("tour_scenes", arr)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Eksterior 360° (frame berurutan, jumlah bebas)</Label>
                  <ExteriorFramesEditor value={form.exterior_frames} onChange={(arr) => set("exterior_frames", arr)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Syarat &amp; Ketentuan Sewa (1 per baris)</Label>
                  <Textarea value={form.rental_terms} onChange={(e) => set("rental_terms", e.target.value)}
                    placeholder={"Harga termasuk jasa pengemudi\nSewa dihitung per hari kalender\nPelunasan maksimal H-1"}
                    data-testid="vf-rental-terms" />
                </div>
              </div>
            ) : null}
          </div>
        </div>
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="vf-cancel">Batal</button>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="vf-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Simpan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
