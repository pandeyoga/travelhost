import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";

function move(list, i, dir) {
  const j = i + dir;
  if (j < 0 || j >= list.length) return list;
  const out = [...list];
  [out[i], out[j]] = [out[j], out[i]];
  return out.map((r, idx) => ({ ...r, order: idx * 10 }));
}

export default function RowsForm({ rows, sections, onRows, onSections }) {
  const list = [...(rows || [])].sort((a, b) => (a.order || 0) - (b.order || 0));
  const secs = [...(sections || [])].sort((a, b) => (a.order || 0) - (b.order || 0));
  const setRow = (i, patch) => onRows(list.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  const addManual = () => onRows([...list, { code: `MANUAL_${Date.now()}`, label: "Baris tambahan", visible: true, order: list.length * 10, hide_if_zero: false, manual: true, amount: 0 }]);
  return (
    <div className="space-y-3" data-testid="rows-form">
      <section className="section-card">
        <div className="section-head"><h2>Baris ringkasan biaya</h2>
          <button className="secondary-button !h-8" onClick={addManual} data-testid="rows-add-manual"><Plus size={13} /> Baris manual</button>
        </div>
        <div className="section-body space-y-2">
          <p className="text-[12px] text-[#6B6B73]">Konfigurasi boleh menyembunyikan, mengurutkan, dan menamai baris — nilainya tetap dari sistem. Baris manual ditandai * di dokumen.</p>
          {list.map((r, i) => (
            <div key={r.code} className="flex flex-wrap items-center gap-2 rounded-[10px] border border-[#F2F2F5] px-3 py-2" data-testid={`row-${r.code}`}>
              <Switch checked={r.visible !== false} onCheckedChange={(v) => setRow(i, { visible: v })} data-testid={`row-visible-${r.code}`} />
              <Input className="h-8 min-w-[180px] flex-1" value={r.label} onChange={(e) => setRow(i, { label: e.target.value })} data-testid={`row-label-${r.code}`} />
              {r.manual ? <Input type="number" className="h-8 w-[150px]" value={r.amount ?? 0} onChange={(e) => setRow(i, { amount: Number(e.target.value) })} data-testid={`row-amount-${r.code}`} /> : <span className="w-[150px] text-[11px] text-[#8E8E93]">{r.code}</span>}
              <label className="flex items-center gap-1 text-[11px] text-[#6B6B73]"><input type="checkbox" checked={r.hide_if_zero !== false} onChange={(e) => setRow(i, { hide_if_zero: e.target.checked })} /> sembunyikan bila 0</label>
              <button className="icon-button !h-7 !w-7" onClick={() => onRows(move(list, i, -1))} title="Naik"><ArrowUp size={12} /></button>
              <button className="icon-button !h-7 !w-7" onClick={() => onRows(move(list, i, 1))} title="Turun"><ArrowDown size={12} /></button>
              {r.manual ? <button className="icon-button !h-7 !w-7 !text-[#FF3B30]" onClick={() => onRows(list.filter((_, idx) => idx !== i))} title="Hapus"><Trash2 size={12} /></button> : null}
            </div>
          ))}
        </div>
      </section>
      <section className="section-card">
        <div className="section-head"><h2>Bagian dokumen & urutannya</h2></div>
        <div className="section-body space-y-2">
          {secs.map((s, i) => (
            <div key={s.key} className="flex items-center gap-2 rounded-[10px] border border-[#F2F2F5] px-3 py-2" data-testid={`section-${s.key}`}>
              <Switch checked={s.visible !== false} onCheckedChange={(v) => onSections(secs.map((x, idx) => (idx === i ? { ...x, visible: v } : x)))} data-testid={`section-visible-${s.key}`} />
              <span className="flex-1 text-[12.5px]">{s.label}</span>
              <button className="icon-button !h-7 !w-7" onClick={() => onSections(move(secs, i, -1))}><ArrowUp size={12} /></button>
              <button className="icon-button !h-7 !w-7" onClick={() => onSections(move(secs, i, 1))}><ArrowDown size={12} /></button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
