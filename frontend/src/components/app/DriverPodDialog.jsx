import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Upload } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const BACKEND = process.env.REACT_APP_BACKEND_URL || "";

export default function DriverPodDialog({ open, task, onOpenChange, onSaved }) {
  const [recipient, setRecipient] = useState("");
  const [note, setNote] = useState("");
  const [file, setFile] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && task) {
      setRecipient(task?.pod?.recipient_name || "");
      setNote(task?.pod?.note || "");
      setFile(null);
    }
  }, [open, task]);

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
      await apiClient.post(`/driver/tasks/${task.trip_id}/pod`, fd);
      toast.success("Bukti layanan (POD) tersimpan");
      onSaved?.();
      onOpenChange(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan POD");
    } finally { setSaving(false); }
  };

  const existingPhoto = task?.pod?.photo_url ? `${BACKEND}${task.pod.photo_url}` : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="dw-pod-dialog">
        <DialogHeader>
          <DialogTitle>Bukti Layanan (POD)</DialogTitle>
          <DialogDescription>Unggah foto serah-terima, nama penerima, dan catatan.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {existingPhoto ? (
            <img src={existingPhoto} alt="POD" className="h-40 w-full rounded-[12px] object-cover" data-testid="dw-pod-existing" />
          ) : null}
          <div>
            <Label className="text-[12px]">Foto (JPG/PNG/WebP, maks 6MB)</Label>
            <Input type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} data-testid="dw-pod-photo" />
          </div>
          <div>
            <Label className="text-[12px]">Nama Penerima</Label>
            <Input value={recipient} onChange={(e) => setRecipient(e.target.value)} placeholder="mis. Pak Budi" data-testid="dw-pod-recipient" />
          </div>
          <div>
            <Label className="text-[12px]">Catatan</Label>
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} placeholder="Kondisi serah-terima" data-testid="dw-pod-note" />
          </div>
        </div>
        <DialogFooter>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="dw-pod-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />} Simpan POD
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
