import { Plus, Trash2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Field, ImagePicker } from "@/components/documents/BrandForm";

export default function SignaturesForm({ signatures, onChange }) {
  const list = signatures || [];
  const set = (i, patch) => onChange(list.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
  const add = () => onChange([...list, { title: "Pihak", name: "", position: "", show_stamp: false, stamp_file_id: null, sign_file_id: null, auto_from_issuer: false }]);
  return (
    <section className="section-card" data-testid="signatures-form">
      <div className="section-head"><h2>Kolom tanda tangan (maks 4)</h2>
        <button className="secondary-button !h-8" onClick={add} disabled={list.length >= 4} data-testid="sig-add"><Plus size={13} /> Tambah kolom</button>
      </div>
      <div className="section-body space-y-3">
        {list.length === 0 ? <p className="text-[12.5px] text-[#6B6B73]">Tanpa kolom tanda tangan.</p> : null}
        {list.map((s, i) => (
          <div key={i} className="grid grid-cols-1 gap-3 rounded-[10px] border border-[#F2F2F5] p-3 sm:grid-cols-2" data-testid={`sig-${i}`}>
            <Field label="Judul kolom"><Input value={s.title || ""} onChange={(e) => set(i, { title: e.target.value })} data-testid={`sig-title-${i}`} /></Field>
            <Field label="Jabatan"><Input value={s.position || ""} onChange={(e) => set(i, { position: e.target.value })} data-testid={`sig-position-${i}`} /></Field>
            <Field label="Nama" hint={s.auto_from_issuer ? "Otomatis: nama pemakai yang mencetak dokumen" : ""}><Input value={s.name || ""} disabled={s.auto_from_issuer} onChange={(e) => set(i, { name: e.target.value })} data-testid={`sig-name-${i}`} /></Field>
            <div className="grid gap-2">
              <div className="flex items-center justify-between rounded-[10px] border border-[#F2F2F5] px-3 py-2"><span className="text-[12.5px]">Nama dari penerbit dokumen</span><Switch checked={Boolean(s.auto_from_issuer)} onCheckedChange={(v) => set(i, { auto_from_issuer: v })} data-testid={`sig-auto-${i}`} /></div>
              <div className="flex items-center justify-between rounded-[10px] border border-[#F2F2F5] px-3 py-2"><span className="text-[12.5px]">Tampilkan cap perusahaan</span><Switch checked={Boolean(s.show_stamp)} onCheckedChange={(v) => set(i, { show_stamp: v })} data-testid={`sig-stamp-${i}`} /></div>
            </div>
            <ImagePicker label="Spesimen tanda tangan" fileId={s.sign_file_id} onChange={(v) => set(i, { sign_file_id: v })} testId={`sig-sign-img-${i}`} />
            <ImagePicker label="Gambar cap / stempel" fileId={s.stamp_file_id} onChange={(v) => set(i, { stamp_file_id: v })} testId={`sig-stamp-img-${i}`} />
            <div className="sm:col-span-2 flex justify-end"><button className="secondary-button !h-8 !text-[#FF3B30]" onClick={() => onChange(list.filter((_, idx) => idx !== i))} data-testid={`sig-remove-${i}`}><Trash2 size={13} /> Hapus kolom</button></div>
          </div>
        ))}
      </div>
    </section>
  );
}
