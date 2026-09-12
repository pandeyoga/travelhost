import { useCallback, useEffect, useState } from "react";
import { BadgeDollarSign, Loader2, Save, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { Input } from "@/components/ui/input";
import { formatCurrency } from "@/utils/formatters";

// RC-B (INV-PRICE-02): SATU-SATUNYA tempat menulis tarif khusus per unit.
// Form Armada kini read-only untuk harga — tidak ada lagi dua pintu tulis.
export const UnitRatesPanel = () => {
  const [rows, setRows] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [savingId, setSavingId] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await apiClient.get("/pricing/unit-rates");
      setRows(Array.isArray(data) ? data : []);
      setDrafts({});
    } catch {
      toast.error("Gagal memuat tarif per unit");
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const saveRow = async (r) => {
    const raw = drafts[r.id];
    if (raw === undefined) return;
    setSavingId(r.id);
    try {
      const { data } = await apiClient.patch(`/pricing/unit-rates/${r.id}`, { day_rate: Number(raw) || 0 });
      if (data?.warning) toast.warning(data.warning, { duration: 8000 });
      else toast.success(`Tarif ${r.name} disimpan`);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan tarif unit");
    } finally { setSavingId(""); }
  };

  return (
    <div className="mt-2 rounded-[12px] border border-[#E5E5EA]" data-testid="settings-unit-rates">
      <div className="flex items-center gap-2 border-b border-[#EFF0F2] px-3 py-2.5">
        <BadgeDollarSign size={15} className="text-[#007AFF]" />
        <span className="text-[13px] font-semibold text-[#1C1C1E]">Tarif Khusus per Unit (Master Harga)</span>
      </div>
      <p className="px-3 pt-2 text-[12px] text-[#6B6B73]">
        Kosong/0 = unit memakai tarif per tipe di atas. Ini SATU-SATUNYA pintu mengubah tarif
        unit — form Armada hanya menampilkan (read-only).
      </p>
      {loading ? (
        <div className="flex items-center gap-2 px-3 py-4 text-[12px] text-[#6B6B73]" data-testid="unit-rates-loading">
          <Loader2 size={14} className="animate-spin" /> Memuat…
        </div>
      ) : (
        <div className="divide-y divide-[#F2F2F5] px-3 py-1">
          {rows.map((r) => (
            <div key={r.id} className="flex flex-wrap items-center gap-2 py-2" data-testid={`unit-rate-row-${r.id}`}>
              <div className="min-w-[180px] flex-1">
                <span className="block text-[13px] font-semibold text-[#1C1C1E]">{r.name}</span>
                <span className="block text-[11px] text-[#8E8E93]">
                  {r.code} · {r.type_label} · efektif {formatCurrency(r.effective_rate)}/hari ({r.rate_basis})
                </span>
                {r.warning ? (
                  <span className="mt-0.5 flex items-start gap-1 text-[11px] font-semibold text-[#B45309]" data-testid={`unit-rate-warning-${r.id}`}>
                    <AlertTriangle size={11} className="mt-0.5 shrink-0" /> {r.warning}
                  </span>
                ) : null}
              </div>
              <Input type="number" className="!h-9 max-w-[160px]"
                value={drafts[r.id] ?? (r.day_rate || "")}
                onChange={(e) => setDrafts((d) => ({ ...d, [r.id]: e.target.value }))}
                placeholder="0 = tarif tipe" data-testid={`unit-rate-input-${r.id}`} />
              <button className="secondary-button !h-9 !px-2.5 !text-[12px]"
                disabled={savingId === r.id || drafts[r.id] === undefined}
                onClick={() => saveRow(r)} data-testid={`unit-rate-save-${r.id}`}>
                {savingId === r.id ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Simpan
              </button>
            </div>
          ))}
          {rows.length === 0 ? (
            <p className="py-3 text-[12px] text-[#8E8E93]">Belum ada armada terdaftar.</p>
          ) : null}
        </div>
      )}
    </div>
  );
};

export default UnitRatesPanel;
