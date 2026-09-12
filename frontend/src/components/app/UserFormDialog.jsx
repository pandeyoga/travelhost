import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const ROLE_OPTIONS = [
  ["owner", "Pemilik"],
  ["ops_admin", "Admin Operasional"],
  ["marketing_admin", "Admin Marketing (Website, CMS & Iklan)"],
  ["driver", "Driver"],
];
const EMPTY = { name: "", email: "", password: "", role: "ops_admin", phone: "", status: "active" };

// Tambah (initial=null) / Edit user. Saat edit: email tidak bisa diubah, sandi opsional (kosong = tetap).
export default function UserFormDialog({ open, onOpenChange, initial, isSelf, onSaved }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const editing = Boolean(initial);
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    if (open) setForm(initial ? { ...EMPTY, ...initial, password: "" } : EMPTY);
  }, [open, initial]);

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (editing) {
        const body = { name: form.name, phone: form.phone, role: form.role, status: form.status };
        if (form.password) body.password = form.password;
        await apiClient.patch(`/users/${initial.id}`, body);
        toast.success(form.password ? "User diperbarui & kata sandi direset" : "User diperbarui");
      } else {
        await apiClient.post("/users", { name: form.name, email: form.email, password: form.password, role: form.role, phone: form.phone });
        toast.success("User berhasil dibuat");
      }
      onOpenChange(false);
      onSaved && onSaved();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal menyimpan user");
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="user-form-dialog">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit User" : "Tambah User Baru"}</DialogTitle>
          <DialogDescription>{editing ? "Ubah data, peran, status, atau reset kata sandi." : "Buat akun baru dan tetapkan perannya (RBAC)."}</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="u-name">Nama</Label>
            <Input id="u-name" value={form.name} onChange={(e) => set("name", e.target.value)} required data-testid="users-name-input" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="u-email">Email</Label>
            <Input id="u-email" type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required disabled={editing} data-testid="users-email-input" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="u-password">{editing ? "Kata Sandi Baru (kosongkan jika tidak diubah)" : "Kata Sandi"}</Label>
            <Input id="u-password" type="password" value={form.password} onChange={(e) => set("password", e.target.value)}
              required={!editing} minLength={6} autoComplete="new-password" data-testid="users-password-input" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="u-phone">Telepon</Label>
            <Input id="u-phone" value={form.phone || ""} onChange={(e) => set("phone", e.target.value)} data-testid="users-phone-input" />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Peran</Label>
              <Select value={form.role} onValueChange={(v) => set("role", v)} disabled={isSelf}>
                <SelectTrigger data-testid="users-role-select"><SelectValue placeholder="Pilih peran" /></SelectTrigger>
                <SelectContent>
                  {ROLE_OPTIONS.map(([v, l]) => <SelectItem key={v} value={v} data-testid={`users-role-opt-${v}`}>{l}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {editing ? (
              <div className="space-y-1.5">
                <Label>Status</Label>
                <Select value={form.status || "active"} onValueChange={(v) => set("status", v)} disabled={isSelf}>
                  <SelectTrigger data-testid="users-status-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active" data-testid="users-status-opt-active">Aktif</SelectItem>
                    <SelectItem value="inactive" data-testid="users-status-opt-inactive">Nonaktif</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            ) : null}
          </div>
          {isSelf ? <p className="text-[12px] text-[#8E8E93]">Peran & status akun sendiri tidak dapat diubah (anti terkunci).</p> : null}
          <DialogFooter>
            <button type="submit" className="primary-button" disabled={saving} data-testid="users-submit-button">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Simpan
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
