import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

// INV-REF-02 batch 5: kota pelanggan/mitra = relasi ke master `cities`.
// Quick-add menulis ke MASTER (satu pintu) — bukan menyelundupkan teks bebas.
export const CitySelect = ({ value, onChange, testId = "city-select" }) => {
  const [options, setOptions] = useState([]);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");

  const load = useCallback(() => {
    apiClient.get("/cities")
      .then((r) => setOptions(Array.isArray(r.data) ? r.data : []))
      .catch(() => setOptions([]));
  }, []);
  useEffect(() => { load(); }, [load]);

  const quickAdd = async () => {
    const name = newName.trim();
    if (name.length < 2) return;
    try {
      const { data } = await apiClient.post("/cities", { name });
      toast.success(`Kota "${data.name}" siap dipakai`);
      setNewName(""); setAdding(false);
      load(); onChange(data.name);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menambah kota");
    }
  };

  const known = options.some((o) => o.name === value);
  const seen = new Set();
  const uniqueOptions = options.filter((o) => {
    const k = String(o.name || "").trim().toLowerCase();
    if (!k || seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  return (
    <div className="space-y-1.5">
      <Select value={value || ""} onValueChange={onChange}>
        <SelectTrigger data-testid={testId}><SelectValue placeholder="Pilih kota" /></SelectTrigger>
        <SelectContent>
          {value && !known ? <SelectItem value={value}>{value} (warisan — di luar master)</SelectItem> : null}
          {uniqueOptions.map((o) => (
            <SelectItem key={o.id} value={o.name} data-testid={`${testId}-opt-${o.id}`}>{o.name}</SelectItem>
          ))}
        </SelectContent>
      </Select>
      {adding ? (
        <div className="flex gap-1.5">
          <Input className="!h-8 text-[12px]" value={newName} onChange={(e) => setNewName(e.target.value)}
            placeholder="Nama kota baru" data-testid={`${testId}-new-input`} />
          <button type="button" className="secondary-button !h-8 !px-2 !text-[11px]" onClick={quickAdd} data-testid={`${testId}-new-save`}>Simpan</button>
        </div>
      ) : (
        <button type="button" className="flex items-center gap-1 text-[11.5px] font-semibold text-[#007AFF]"
          onClick={() => setAdding(true)} data-testid={`${testId}-add-toggle`}>
          <Plus size={12} /> Tambah kota baru (masuk master)
        </button>
      )}
    </div>
  );
};

export default CitySelect;
