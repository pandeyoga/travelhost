import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
const toDateInput = (v) => (v ? String(v).slice(0, 10) : "");
const EMPTY = { name: "", phone: "", sim_number: "", sim_expiry: "", default_fee_rate: "" };
const ACC_MODES = [["none", "Tanpa akun"], ["existing", "Pilih akun yang ada"], ["new", "Buat akun baru"]];

export default function DriverFormDialog({ open, onOpenChange, initial, onSaved }) {
  const editing = Boolean(initial && initial.id);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [accMode, setAccMode] = useState("none");
  const [acc, setAcc] = useState({ user_id: "", email: "", password: "" });
  const [accounts, setAccounts] = useState([]);

  useEffect(() => {
    if (!open) return;
    setForm(editing ? {
      name: initial.name || "", phone: initial.phone || "", sim_number: initial.sim_number || "",
      sim_expiry: toDateInput(initial.sim_expiry), default_fee_rate: initial.default_fee_rate ?? "",
    } : EMPTY);
    const linked = editing && initial.user_id ? initial.user_id : "";
    setAccMode(linked ? "existing" : "none");
    setAcc({ user_id: linked, email: "", password: "" });
    apiClient.get("/drivers/accounts").then((r) => setAccounts(Array.isArray(r.data) ? r.data : [])).catch(() => setAccounts([]));
  }, [open, editing, initial]);

  // Akun driver yang bebas (belum terpaut driver lain) + akun yang sedang terpaut ke driver ini.
  const selectable = accounts.filter((u) => !u.driver_id || (editing && u.driver_id === initial.id));

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.name.trim()) {
      toast.error("Nama driver wajib diisi");
      return;
    }
    if (accMode === "existing" && !acc.user_id) { toast.error("Pilih akun login driver"); return; }
    if (accMode === "new" && (!acc.email.trim() || acc.password.length < 6)) { toast.error("Email & kata sandi (min. 6 karakter) wajib untuk akun baru"); return; }
    setSaving(true);
    const payload = {
      name: form.name.trim(), phone: form.phone, sim_number: form.sim_number,
      sim_expiry: form.sim_expiry || null, default_fee_rate: Number(form.default_fee_rate) || 0,
    };
    if (accMode === "existing") payload.user_id = acc.user_id;
    else if (accMode === "new") { payload.account_email = acc.email.trim(); payload.account_password = acc.password; }
    else if (editing && initial.user_id) payload.user_id = "";
    try {
      if (editing) await apiClient.patch(`/drivers/${initial.id}`, payload);
      else await apiClient.post("/drivers", payload);
      toast.success(editing ? "Driver diperbarui" : "Driver ditambahkan");
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan driver");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg" data-testid="driver-form-dialog">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit Driver" : "Tambah Driver"}</DialogTitle>
          <DialogDescription>Data master pengemudi & masa berlaku SIM. Status kerja (online / istirahat / offline) diperbarui otomatis dari trip & Ruang Kerja Driver — bukan diisi manual.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Nama</Label>
              <Input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="Nama lengkap" data-testid="df-name" />
            </div>
            <div className="space-y-1.5">
              <Label>Telepon</Label>
              <Input value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="0812xxxx" data-testid="df-phone" />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Nomor SIM</Label>
              <Input value={form.sim_number} onChange={(e) => set("sim_number", e.target.value)} placeholder="B1-00x" data-testid="df-sim" />
            </div>
            <div className="space-y-1.5">
              <Label>SIM Berlaku s/d</Label>
              <Input type="date" value={form.sim_expiry} onChange={(e) => set("sim_expiry", e.target.value)} data-testid="df-sim-expiry" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Fee Default /hari (Rp) — prefill otomatis saat assign dispatch</Label>
            <Input type="number" min="0" value={form.default_fee_rate} onChange={(e) => set("default_fee_rate", e.target.value)} placeholder="mis. 150000 (kosong = tanpa prefill)" data-testid="df-default-fee" />
          </div>
          <div className="rounded-xl border border-[#E9E9EE] bg-[#FAFAFC] p-3 space-y-2.5" data-testid="df-account-box">
            <div>
              <p className="text-[13px] font-semibold text-[#1C1C1E]">Akun Login Driver (Ruang Kerja Driver)</p>
              <p className="text-[12px] text-[#6B6B73]">Driver masuk ke ERP dgn akun peran <b>driver</b> untuk melihat tugas, mulai/selesai trip, dan GPS. Tautkan akun yang ada atau buat baru di sini.</p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {ACC_MODES.map(([v, l]) => (
                <button key={v} type="button" onClick={() => setAccMode(v)} data-testid={`df-acc-mode-${v}`}
                  className={`secondary-button !h-8 !px-3 !text-[12px] ${accMode === v ? "!border-[#0A84FF] !text-[#0A84FF]" : ""}`}>{l}</button>
              ))}
            </div>
            {accMode === "existing" ? (
              <Select value={acc.user_id} onValueChange={(v) => setAcc((a) => ({ ...a, user_id: v }))}>
                <SelectTrigger data-testid="df-acc-user"><SelectValue placeholder={selectable.length ? "Pilih akun peran driver…" : "Belum ada akun driver bebas — buat baru"} /></SelectTrigger>
                <SelectContent>
                  {selectable.map((u) => <SelectItem key={u.id} value={u.id} data-testid={`df-acc-user-opt-${u.id}`}>{u.name} — {u.email}</SelectItem>)}
                </SelectContent>
              </Select>
            ) : null}
            {accMode === "new" ? (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label>Email login</Label>
                  <Input type="email" value={acc.email} onChange={(e) => setAcc((a) => ({ ...a, email: e.target.value }))} placeholder="driver@perusahaan.com" data-testid="df-acc-email" />
                </div>
                <div className="space-y-1.5">
                  <Label>Kata sandi (min. 6)</Label>
                  <Input type="password" autoComplete="new-password" value={acc.password} onChange={(e) => setAcc((a) => ({ ...a, password: e.target.value }))} data-testid="df-acc-password" />
                </div>
              </div>
            ) : null}
            {accMode === "none" && editing && initial.user_id ? <p className="text-[12px] text-[#A8221A]">Akun login akan dilepas dari driver ini (akun tidak dihapus).</p> : null}
          </div>
        </div>
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="df-cancel">Batal</button>
          <button className="primary-button" disabled={saving} onClick={submit} data-testid="df-submit">
            {saving ? <Loader2 size={14} className="animate-spin" /> : null} Simpan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
