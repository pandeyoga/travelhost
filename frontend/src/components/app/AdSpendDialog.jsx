import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Plus, Trash2, Megaphone } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import SelectField from "@/components/shared/SelectField";

// Kunci channel BAKU. Harus sama persis dengan nilai `channel`/`source` pada lead, karena
// laporan ROAS (`services/analytics.channels_roi`) menggabungkan belanja iklan dengan lead
// lewat PENCOCOKAN STRING PERSIS. Dulu kolom ini input bebas: mengetik "Meta Ads" (spasi &
// huruf besar) membuat belanjanya tidak pernah bertemu lead `meta_ads` — barisnya jadi
// "spend ada, lead 0" dan CPL/CAC/ROAS diam-diam salah tanpa satu pun peringatan.
const SUGGEST = ["meta_ads", "google_ads", "tiktok", "instagram", "website", "whatsapp",
                 "referral", "organic", "manual"];
const MANUAL = "__manual__";
const chLabel = (c) => String(c || "").replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());

// AdSpendDialog — E4: atur belanja iklan manual per channel (settings.marketing_spend) untuk CPL/CAC/ROAS.
export default function AdSpendDialog({ open, onOpenChange, onSaved }) {
  const [items, setItems] = useState([]);
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  // Channel yang BENAR-BENAR ada di data (dari lead/atribusi) — supaya pilihan tidak
  // mengarang, dan channel baru yang sudah dipakai iklan otomatis muncul di daftar.
  const [known, setKnown] = useState([]);
  const [manualRows, setManualRows] = useState({});

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    apiClient.get("/analytics/ad-spend")
      .then((r) => {
        const list = Array.isArray(r.data?.items) ? r.data.items : [];
        setItems(list.length ? list : SUGGEST.slice(0, 4).map((c) => ({ channel: c, amount: 0 })));
        setNote(r.data?.note || "");
      })
      .catch(() => setItems(SUGGEST.slice(0, 4).map((c) => ({ channel: c, amount: 0 }))))
      .finally(() => setLoading(false));
    apiClient.get("/analytics/channels")
      .then((r) => {
        const list = Array.isArray(r.data?.channels) ? r.data.channels : [];
        setKnown(list.map((c) => c.channel).filter(Boolean));
      })
      .catch(() => setKnown([]));
  }, [open]);

  const update = (i, field, val) => {
    setItems((prev) => prev.map((it, idx) => (idx === i ? { ...it, [field]: val } : it)));
  };
  const addRow = () => setItems((prev) => [...prev, { channel: "", amount: 0 }]);
  const removeRow = (i) => setItems((prev) => prev.filter((_, idx) => idx !== i));

  const submit = async () => {
    const clean = items
      .map((i) => ({ channel: (i.channel || "").trim(), amount: Number(i.amount) || 0 }))
      .filter((i) => i.channel);
    setSaving(true);
    try {
      await apiClient.put("/analytics/ad-spend", { items: clean, note });
      toast.success("Belanja iklan tersimpan");
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan belanja iklan");
    } finally { setSaving(false); }
  };

  // Union: channel baku + channel yang sudah ada di data + yang sudah tersimpan di belanja.
  const options = Array.from(new Set([...SUGGEST, ...known,
                                     ...items.map((i) => i.channel).filter(Boolean)]));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="adspend-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Megaphone size={16} className="text-[#AF52DE]" /> Belanja Iklan per Channel</DialogTitle>
          <DialogDescription>Masukkan estimasi biaya iklan untuk menghitung CPL, CAC, dan ROAS.</DialogDescription>
        </DialogHeader>
        {loading ? (
          <div className="flex justify-center py-8"><Loader2 className="animate-spin text-[#8E8E93]" /></div>
        ) : (
          <div className="max-h-[46vh] space-y-2 overflow-y-auto pr-1">
            {items.map((it, i) => (
              <div key={i} className="flex items-end gap-2" data-testid={`adspend-row-${i}`}>
                <div className="flex-1 space-y-1">
                  {i === 0 ? <Label className="text-[11px]">Channel</Label> : null}
                  {manualRows[i] ? (
                    <Input value={it.channel} placeholder="huruf kecil & garis bawah, mis. tiktok_ads"
                      onChange={(e) => update(i, "channel", e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_"))}
                      data-testid={`adspend-channel-manual-${i}`} />
                  ) : (
                    <SelectField
                      testId={`adspend-channel-${i}`}
                      value={it.channel}
                      placeholder="Pilih channel"
                      options={[...options.map((c) => ({ value: c, label: chLabel(c) })),
                                { value: MANUAL, label: "+ Channel lain (tulis sendiri)" }]}
                      onChange={(v) => {
                        if (v === MANUAL) {
                          setManualRows((m) => ({ ...m, [i]: true }));
                          update(i, "channel", "");
                          return;
                        }
                        update(i, "channel", v);
                      }}
                    />
                  )}
                </div>
                <div className="w-[42%] space-y-1">
                  {i === 0 ? <Label className="text-[11px]">Biaya (Rp)</Label> : null}
                  <Input type="number" min="0" value={it.amount}
                    onChange={(e) => update(i, "amount", e.target.value)} data-testid={`adspend-amount-${i}`} />
                </div>
                <button type="button" className="icon-button !h-9 !w-9 flex-shrink-0" title="Hapus"
                  onClick={() => removeRow(i)} data-testid={`adspend-remove-${i}`}><Trash2 size={14} /></button>
              </div>
            ))}
            <button type="button" className="secondary-button mt-1" onClick={addRow} data-testid="adspend-add"><Plus size={13} /> Tambah channel</button>
          </div>
        )}
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="adspend-cancel">Batal</button>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="adspend-save">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Simpan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
