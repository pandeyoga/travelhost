import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Loader2, Camera, CheckCircle2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

// PodDialog — E3: unggah Bukti Layanan (Proof of Delivery) lokal: foto + nama penerima + catatan.
export default function PodDialog({ open, onOpenChange, trip, onSaved }) {
  const [recipient, setRecipient] = useState("");
  const [note, setNote] = useState("");
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [saving, setSaving] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setRecipient(trip?.pod?.recipient_name || "");
    setNote(trip?.pod?.note || "");
    setFile(null);
    setPreview(trip?.pod?.photo_url ? `${BACKEND_URL}${trip.pod.photo_url}` : null);
  }, [open, trip]);

  const onPick = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!/^image\/(jpe?g|png|webp)$/.test(f.type)) { toast.error("Format foto harus JPG/PNG/WebP"); return; }
    setFile(f);
    setPreview(URL.createObjectURL(f));
  };

  const submit = async () => {
    if (!file && !recipient.trim() && !note.trim()) {
      toast.error("Sertakan foto, nama penerima, atau catatan"); return;
    }
    setSaving(true);
    try {
      const fd = new FormData();
      if (file) fd.append("photo", file);
      fd.append("recipient_name", recipient);
      fd.append("note", note);
      await apiClient.post(`/dispatch/trips/${trip.id}/pod`, fd);
      toast.success("Bukti layanan (POD) tersimpan");
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan POD");
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="pod-dialog">
        <DialogHeader>
          <DialogTitle>Bukti Layanan (POD)</DialogTitle>
          <DialogDescription>Foto + penerima + catatan saat penyelesaian trip (disimpan lokal).</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label>Foto bukti</Label>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={onPick} data-testid="pod-photo" />
            <button type="button" className="secondary-button w-full justify-center" onClick={() => fileRef.current?.click()} data-testid="pod-photo-btn">
              <Camera size={14} /> {file ? "Ganti foto" : "Pilih foto"}
            </button>
            {preview ? <img src={preview} alt="POD" className="mt-2 h-36 w-full rounded-[10px] border border-[#EFF0F2] object-cover" data-testid="pod-preview" /> : null}
          </div>
          <div className="space-y-1.5">
            <Label>Nama penerima</Label>
            <Input value={recipient} onChange={(e) => setRecipient(e.target.value)} placeholder="mis. Pak Andi" data-testid="pod-recipient" />
          </div>
          <div className="space-y-1.5">
            <Label>Catatan</Label>
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Kondisi penyerahan / catatan lain" data-testid="pod-note" />
          </div>
          {trip?.pod ? <div className="flex items-center gap-1.5 text-[12px] font-medium text-[#127A36]"><CheckCircle2 size={13} /> POD sudah pernah direkam</div> : null}
        </div>
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="pod-cancel">Batal</button>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="pod-save">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Simpan POD
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
