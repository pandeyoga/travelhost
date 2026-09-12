import { useCallback, useEffect, useState } from "react";
import { ArrowLeftRight, Loader2, Plane, Plus, Save, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatCurrency } from "@/utils/formatters";

// TransferRoutesPanel — kelola RUTE ANTAR-JEMPUT BANDARA + tarif FLAT per tipe armada.
//
// Tipe armada yang tidak diisi tarifnya memang TIDAK dijual pada rute itu (mesin harga
// menolak, bukan mengarang tarif dari tipe lain). Jadi kolom kosong = keputusan bisnis,
// bukan data yang hilang.
//
// Dua alat bantu pengisian (permintaan user: "tambah rute nyata + tarif per tipe unit"):
//  1. KATALOG BANDARA — sekali klik mengisi nama rute, label asal/tujuan, kode IATA, dan
//     estimasi durasi. Yang TIDAK diisi otomatis: TARIF. Mengarang tarif adalah cacat yang
//     sedang diberantas di repo ini; harga adalah keputusan pemilik, jadi server menolak
//     menyimpan rute tanpa minimal satu tarif.
//  2. ARAH BALIK — hampir semua rute bandara dijual dua arah dengan tarif sama. Tombol ini
//     menyalin rute + tarifnya lalu menukar asal/tujuan, sehingga ops tidak mengetik ulang
//     (sumber utama salah ketik tarif yang bikin harga dua arah berbeda tanpa alasan).
const BLANK = {
  code: "", name: "", from_label: "", to_label: "", airport_code: "",
  duration_minutes: 180, notes: "", active: true, position: 0, rates: {},
};

// Bandara utama + kota asal yang lazim dilayani travel Jawa–Bali. Durasi = estimasi tempuh
// darat rata-rata (menit) yang masih bisa diubah ops sebelum menyimpan.
const AIRPORTS = [
  { city: "Bandung", code: "CGK", airport: "Soekarno-Hatta (CGK)", minutes: 240 },
  { city: "Bandung", code: "HLP", airport: "Halim Perdanakusuma (HLP)", minutes: 210 },
  { city: "Bandung", code: "KJT", airport: "Kertajati (KJT)", minutes: 150 },
  { city: "Bandung", code: "BDO", airport: "Husein Sastranegara (BDO)", minutes: 45 },
  { city: "Jakarta", code: "CGK", airport: "Soekarno-Hatta (CGK)", minutes: 90 },
  { city: "Yogyakarta", code: "YIA", airport: "Yogyakarta Intl (YIA)", minutes: 90 },
  { city: "Solo", code: "SOC", airport: "Adi Soemarmo (SOC)", minutes: 60 },
  { city: "Semarang", code: "SRG", airport: "Ahmad Yani (SRG)", minutes: 45 },
  { city: "Surabaya", code: "SUB", airport: "Juanda (SUB)", minutes: 60 },
  { city: "Malang", code: "SUB", airport: "Juanda (SUB)", minutes: 150 },
  { city: "Denpasar", code: "DPS", airport: "Ngurah Rai (DPS)", minutes: 60 },
];

function cityCode(city, airportCode = "") {
  const map = { Bandung: "BDO", Jakarta: "JKT", Yogyakarta: "YOG", Solo: "SOC",
                Semarang: "SRG", Surabaya: "SBY", Malang: "MLG", Denpasar: "DPS" };
  // Beberapa kota memakai kode yang SAMA dengan bandara di kotanya sendiri (Bandung–BDO,
  // Solo–SOC, Semarang–SRG, Denpasar–DPS). Tanpa alias, kode rute jadi "DPS-DPS" dan arah
  // baliknya menghasilkan kode yang IDENTIK → server menolak 409 "kode sudah dipakai" dan
  // ops kebingungan karena merasa tidak pernah membuat rute itu. Terbukti saat uji: rute
  // Denpasar ↔ DPS tidak bisa dibuat dua arah.
  const alt = { Bandung: "BDG", Solo: "SLO", Semarang: "SMG", Denpasar: "BALI" };
  const base = map[city] || city.slice(0, 3).toUpperCase();
  return base === String(airportCode || "").toUpperCase() ? (alt[city] || `${base}C`) : base;
}

export default function TransferRoutesPanel() {
  const [rows, setRows] = useState([]);
  const [labels, setLabels] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await apiClient.get("/transfer-routes");
      setRows(data?.routes || []);
      setLabels(data?.vehicle_type_labels || {});
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat rute antar-jemput");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    const body = {
      ...editing,
      duration_minutes: Number(editing.duration_minutes) || 180,
      position: Number(editing.position) || 0,
      rates: Object.fromEntries(Object.entries(editing.rates || {})
        .map(([k, v]) => [k, Number(v) || 0]).filter(([, v]) => v > 0)),
    };
    setSaving(true);
    try {
      if (editing.id) await apiClient.patch(`/transfer-routes/${editing.id}`, body);
      else await apiClient.post("/transfer-routes", body);
      toast.success("Rute disimpan");
      setEditing(null);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan rute");
    } finally { setSaving(false); }
  };

  const remove = async (row) => {
    if (!window.confirm(`Hapus rute "${row.name}"?`)) return;
    try {
      const { data } = await apiClient.delete(`/transfer-routes/${row.id}`);
      toast.success(data?.deactivated
        ? `Rute dinonaktifkan (dipakai ${data.used_by_bookings} booking)` : "Rute dihapus");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus rute");
    }
  };

  const typeKeys = Object.keys(labels).length ? Object.keys(labels)
    : ["hiace_premio", "hiace", "elf", "bus", "avanza"];

  // Katalog: isi identitas rute, TARIF tetap dikosongkan (keputusan pemilik).
  const prefill = (airport, direction) => {
    const toAirport = direction === "to";
    const from = toAirport ? airport.city : airport.airport;
    const to = toAirport ? airport.airport : airport.city;
    const cc = cityCode(airport.city, airport.code);
    setEditing({
      ...BLANK,
      name: `${from} → ${to}`,
      from_label: from,
      to_label: to,
      airport_code: airport.code,
      code: toAirport ? `${cc}-${airport.code}` : `${airport.code}-${cc}`,
      duration_minutes: airport.minutes,
      notes: "Termasuk driver, tol, dan parkir bandara.",
    });
    toast.success("Rute terisi — tinggal isi tarif per tipe armada");
  };

  // Arah balik: salin rute + TARIF-nya, tukar asal/tujuan. Belum disimpan (ops bisa mengoreksi).
  const reverseOf = (row) => {
    const parts = String(row.code || "").split("-");
    // Kode dibalik HANYA bila hasilnya berbeda; kode simetris (mis. "DPS-DPS") akan menabrak
    // rute asalnya, jadi lebih jujur dikosongkan agar ops menentukan kodenya sendiri.
    const flipped = parts.length === 2 && parts[0] !== parts[1]
      ? `${parts[1]}-${parts[0]}` : "";
    setEditing({
      ...BLANK, ...row, id: undefined,
      name: `${row.to_label} → ${row.from_label}`,
      from_label: row.to_label, to_label: row.from_label,
      code: flipped,
      rates: { ...(row.rates || {}) },
    });
    toast.info("Arah balik disiapkan — periksa tarif lalu simpan");
  };

  return (
    <section className="section-card" data-testid="settings-transfer-routes">
      <div className="section-head">
        <div className="flex min-w-0 items-center gap-2">
          <Plane size={16} className="text-[#007AFF]" />
          <h2 className="truncate">Rute Antar-Jemput Bandara</h2>
        </div>
        <button className="primary-button flex-shrink-0" onClick={() => setEditing({ ...BLANK })}
          data-testid="tr-add"><Plus size={14} /> Tambah Rute</button>
      </div>
      <div className="section-body space-y-3">
        <p className="text-[12px] text-[#6B6B73]">
          Tarif flat per rute per tipe armada. Dipakai langsung oleh pemesanan online — tipe yang
          tarifnya kosong tidak ditawarkan pada rute tersebut.
        </p>

        {/* Katalog bandara: mempercepat entri rute NYATA tanpa mengarang tarif. */}
        <div className="rounded-[12px] border border-[#E5E5EA] bg-[#FAFAFB] p-3" data-testid="tr-catalog">
          <p className="text-[12px] font-semibold text-[#1C1C1E]">Tambah cepat dari daftar bandara</p>
          <p className="mt-0.5 text-[11.5px] text-[#6B6B73]">
            Sekali klik mengisi nama rute, kode IATA, dan estimasi durasi. Tarif tetap Anda isi
            sendiri — sistem tidak akan pernah menebak harga.
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {AIRPORTS.map((a, i) => (
              <span key={`${a.city}-${a.code}-${i}`}
                className="inline-flex items-center gap-1 rounded-full border border-[#E5E5EA] bg-white px-2 py-1 text-[11.5px] text-[#1C1C1E]">
                {a.city} ↔ {a.code}
                <button type="button" onClick={() => prefill(a, "to")} title={`${a.city} → ${a.airport}`}
                  data-testid={`tr-quick-${cityCode(a.city, a.code)}-${a.code}`}
                  className="rounded bg-[#EAF2FF] px-1.5 font-semibold text-[#0058CC] hover:bg-[#D7E7FF]">ke bandara</button>
                <button type="button" onClick={() => prefill(a, "from")} title={`${a.airport} → ${a.city}`}
                  data-testid={`tr-quick-${a.code}-${cityCode(a.city, a.code)}`}
                  className="rounded bg-[#F0F1F4] px-1.5 font-semibold text-[#3C3C43] hover:bg-[#E5E5EA]">dari bandara</button>
              </span>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 py-8 text-[13px] text-[#6B6B73]" data-testid="tr-loading">
            <Loader2 size={15} className="animate-spin" /> Memuat rute…
          </div>
        ) : error ? (
          <div className="rounded-[12px] border border-[#FFE0DC] bg-[#FFF5F4] p-4 text-[13px] text-[#A8221A]"
            data-testid="tr-error">
            {error} <button onClick={load} className="ml-2 underline" data-testid="tr-retry">Coba lagi</button>
          </div>
        ) : rows.length === 0 ? (
          <p className="rounded-[12px] border border-dashed border-[#E5E5EA] px-4 py-8 text-center text-[13px] text-[#8E8E93]"
            data-testid="tr-empty">
            Belum ada rute. Tambahkan rute agar layanan antar-jemput bandara bisa dipesan online.
          </p>
        ) : (
          <div className="space-y-2" data-testid="tr-list">
            {rows.map((r) => (
              <div key={r.id} className="rounded-[12px] border border-[#E5E5EA] p-3.5" data-testid={`tr-row-${r.id}`}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-[13.5px] font-semibold text-[#1C1C1E]">
                      {r.name} {r.active === false ? (
                        <span className="ml-1 rounded-full bg-[#F2F2F5] px-2 py-0.5 text-[11px] text-[#6B6B73]">nonaktif</span>
                      ) : null}
                    </p>
                    <p className="text-[12px] text-[#6B6B73]">
                      {r.from_label} → {r.to_label} · {r.duration_minutes} menit
                      {r.code ? ` · ${r.code}` : ""}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-1.5">
                    <button className="secondary-button !px-2.5 !py-1 !text-[12px]"
                      onClick={() => setEditing({ ...BLANK, ...r })} data-testid={`tr-edit-${r.id}`}>Ubah</button>
                    <button className="secondary-button !px-2.5 !py-1 !text-[12px]" title="Buat rute arah balik (tarif ikut disalin)"
                      onClick={() => reverseOf(r)} data-testid={`tr-reverse-${r.id}`}>
                      <ArrowLeftRight size={12} /> Arah balik
                    </button>
                    <button className="icon-button !h-8 !w-8" onClick={() => remove(r)} title="Hapus"
                      data-testid={`tr-del-${r.id}`}><Trash2 size={13} /></button>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {(r.rate_rows || []).map((rr) => (
                    <span key={rr.vehicle_type} className="rounded-full bg-[#F2F2F5] px-2.5 py-1 text-[11.5px] text-[#1C1C1E] tabular-nums">
                      {rr.label}: {formatCurrency(rr.amount)}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {editing ? (
          <div className="rounded-[12px] border border-[#007AFF]/40 bg-[#F8FBFF] p-4" data-testid="tr-form">
            <div className="flex items-center justify-between">
              <h3 className="text-[13.5px] font-semibold text-[#1C1C1E]">
                {editing.id ? "Ubah rute" : "Rute baru"}
              </h3>
              <button className="icon-button !h-8 !w-8" onClick={() => setEditing(null)} data-testid="tr-close">
                <X size={14} />
              </button>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1.5 sm:col-span-2"><Label>Nama rute *</Label>
                <Input value={editing.name} onChange={(e) => setEditing((s) => ({ ...s, name: e.target.value }))}
                  placeholder="Bandung → Soekarno-Hatta (CGK)" data-testid="tr-name" /></div>
              <div className="space-y-1.5"><Label>Dari *</Label>
                <Input value={editing.from_label} onChange={(e) => setEditing((s) => ({ ...s, from_label: e.target.value }))}
                  data-testid="tr-from" /></div>
              <div className="space-y-1.5"><Label>Ke *</Label>
                <Input value={editing.to_label} onChange={(e) => setEditing((s) => ({ ...s, to_label: e.target.value }))}
                  data-testid="tr-to" /></div>
              <div className="space-y-1.5"><Label>Kode rute</Label>
                <Input value={editing.code} onChange={(e) => setEditing((s) => ({ ...s, code: e.target.value.toUpperCase() }))}
                  placeholder="BDO-CGK" data-testid="tr-code" /></div>
              <div className="space-y-1.5"><Label>Kode bandara</Label>
                <Input value={editing.airport_code} onChange={(e) => setEditing((s) => ({ ...s, airport_code: e.target.value.toUpperCase() }))}
                  placeholder="CGK" data-testid="tr-airport" /></div>
              <div className="space-y-1.5"><Label>Durasi tempuh (menit)</Label>
                <Input type="number" min="30" max="1440" value={editing.duration_minutes}
                  onChange={(e) => setEditing((s) => ({ ...s, duration_minutes: e.target.value }))}
                  data-testid="tr-duration" /></div>
              <div className="space-y-1.5"><Label>Urutan tampil</Label>
                <Input type="number" min="0" value={editing.position}
                  onChange={(e) => setEditing((s) => ({ ...s, position: e.target.value }))} data-testid="tr-position" /></div>
              <div className="space-y-1.5 sm:col-span-2"><Label>Catatan (tampil ke pelanggan)</Label>
                <Input value={editing.notes} onChange={(e) => setEditing((s) => ({ ...s, notes: e.target.value }))}
                  placeholder="Termasuk driver, tol, dan parkir bandara." data-testid="tr-notes" /></div>
            </div>
            <div className="mt-3">
              <Label>Tarif flat per tipe armada (Rp) — kosongkan bila tidak dilayani</Label>
              <div className="mt-1.5 grid grid-cols-1 gap-3 sm:grid-cols-3">
                {typeKeys.map((k) => (
                  <div className="space-y-1.5" key={k}>
                    <span className="text-[12px] text-[#6B6B73]">{labels[k] || k}</span>
                    <Input type="number" min="0" value={editing.rates?.[k] ?? ""}
                      onChange={(e) => setEditing((s) => ({ ...s, rates: { ...(s.rates || {}), [k]: e.target.value } }))}
                      placeholder="0" data-testid={`tr-rate-${k}`} />
                  </div>
                ))}
              </div>
            </div>
            <div className="mt-3 flex items-center gap-2">
              <label className="flex cursor-pointer items-center gap-2 text-[12.5px] text-[#1C1C1E]">
                <input type="checkbox" checked={editing.active !== false}
                  onChange={(e) => setEditing((s) => ({ ...s, active: e.target.checked }))}
                  data-testid="tr-active" /> Aktif dijual online
              </label>
              <button className="primary-button ml-auto" onClick={save} disabled={saving} data-testid="tr-save">
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Simpan Rute
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
