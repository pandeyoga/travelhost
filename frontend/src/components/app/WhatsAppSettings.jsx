import { useCallback, useEffect, useState } from "react";
import { MessageCircle, Save, Loader2, Plus, Pencil, Trash2, FileText, Send, CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { OpenWaPanel } from "@/components/app/OpenWaPanel";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";

const PROVIDERS = [["mock", "Mock / Simulasi"], ["openwa", "OpenWA — Scan QR"], ["meta_cloud", "Meta WhatsApp Cloud (resmi)"], ["partner", "Partner / BSP (E6)"]];

export default function WhatsAppSettings() {
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [testPhone, setTestPhone] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const loadCfg = useCallback(() => {
    apiClient.get("/wa/config").then((r) => setCfg(r.data)).catch(() => setCfg(null));
  }, []);
  const loadTpl = useCallback(() => {
    apiClient.get("/wa/templates").then((r) => setTemplates(Array.isArray(r.data) ? r.data : [])).catch(() => {});
  }, []);
  useEffect(() => { loadCfg(); loadTpl(); }, [loadCfg, loadTpl]);

  const set = (k, v) => setCfg((c) => ({ ...c, [k]: v }));
  const setMeta = (k, v) => setCfg((c) => ({ ...c, meta: { ...(c.meta || {}), [k]: v } }));

  const save = async () => {
    setSaving(true);
    const payload = {
      provider: cfg.provider, business_phone: cfg.business_phone,
      price_per_message: Number(cfg.price_per_message) || 0, session_hours: Number(cfg.session_hours) || 24,
      auto_reply_enabled: !!cfg.auto_reply_enabled, auto_reply_text: cfg.auto_reply_text,
      away_reply_text: cfg.away_reply_text,
    };
    if (cfg.provider === "meta_cloud") {
      payload.meta = {
        phone_number_id: cfg.meta?.phone_number_id || "", verify_token: cfg.meta?.verify_token || "",
        api_version: cfg.meta?.api_version || "v21.0",
        access_token: cfg._access_token || "", app_secret: cfg._app_secret || "",
      };
    }
    try { await apiClient.patch("/wa/config", payload); toast.success("Konfigurasi WhatsApp disimpan"); loadCfg(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan"); }
    finally { setSaving(false); }
  };

  const testSend = async () => {
    if (!testPhone.trim()) { toast.error("Isi nomor tujuan (62…)"); return; }
    setTesting(true); setTestResult(null);
    try {
      const r = await apiClient.post("/wa/test-send", { to_phone: testPhone.trim() });
      setTestResult(r.data);
      if (r.data?.ok) toast.success(`Terkirim via ${r.data.provider} (status: ${r.data.status})`);
      else toast.error(r.data?.error || `Gagal (status: ${r.data?.status})`);
    } catch (e) {
      const detail = e?.response?.data?.detail || "Gagal mengirim tes";
      setTestResult({ ok: false, error: detail });
      toast.error(detail);
    } finally { setTesting(false); }
  };

  const saveTpl = async () => {
    if (!editing.key.trim() || !editing.body.trim()) { toast.error("Key & isi template wajib diisi"); return; }
    setBusy(true);
    try {
      await apiClient.put(`/wa/templates/${editing.key.trim()}`, {
        name: editing.name, language: editing.language, category: editing.category, body: editing.body,
      });
      toast.success("Template disimpan"); setEditing(null); loadTpl();
    } catch (e) { toast.error("Gagal menyimpan template"); }
    finally { setBusy(false); }
  };
  const delTpl = async (key) => {
    if (!window.confirm(`Hapus template "${key}"?`)) return;
    try { await apiClient.delete(`/wa/templates/${key}`); toast.success("Template dihapus"); loadTpl(); }
    catch (e) { toast.error("Gagal menghapus"); }
  };

  if (!cfg) return null;

  return (
    <>
      <section className="section-card" data-testid="settings-wa">
        <div className="section-head">
          <div className="flex min-w-0 items-center gap-2"><MessageCircle size={16} className="text-[#25D366]" /><h2 className="truncate">WhatsApp Adapter</h2></div>
          <button className="primary-button flex-shrink-0" onClick={save} disabled={saving} data-testid="settings-wa-save">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Simpan
          </button>
        </div>
        <div className="section-body space-y-3">
          <p className="text-[12px] text-[#6B6B73]">Provider pengiriman pesan. <b>Mock</b> aktif tanpa kredensial (simulasi jujur). Meta Cloud diaktifkan pada fase E6.</p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5"><Label>Provider</Label>
              <Select value={cfg.provider} onValueChange={(v) => set("provider", v)}>
                <SelectTrigger data-testid="wa-provider"><SelectValue /></SelectTrigger>
                <SelectContent>{PROVIDERS.map(([k, l]) => <SelectItem key={k} value={k}>{l}</SelectItem>)}</SelectContent>
              </Select></div>
            <div className="space-y-1.5"><Label>Nomor Bisnis (62…)</Label>
              <Input value={cfg.business_phone || ""} onChange={(e) => set("business_phone", e.target.value)} data-testid="wa-phone" /></div>
            <div className="space-y-1.5"><Label>Estimasi Biaya / Pesan (Rp)</Label>
              <Input type="number" value={cfg.price_per_message ?? ""} onChange={(e) => set("price_per_message", e.target.value)} data-testid="wa-price" /></div>
            <div className="space-y-1.5"><Label>Durasi Sesi (jam)</Label>
              <Input type="number" value={cfg.session_hours ?? ""} onChange={(e) => set("session_hours", e.target.value)} data-testid="wa-session" /></div>
          </div>
          <label className="flex items-center gap-2 text-[13px] text-[#3C3C43]">
            <Switch checked={!!cfg.auto_reply_enabled} onCheckedChange={(v) => set("auto_reply_enabled", v)} data-testid="wa-autoreply" /> Balasan otomatis saat pesan masuk
          </label>
          <div className="space-y-1.5"><Label>Pesan Sambutan (jam kerja)</Label>
            <Textarea rows={2} value={cfg.auto_reply_text || ""} onChange={(e) => set("auto_reply_text", e.target.value)} data-testid="wa-autoreply-text" /></div>
          <div className="space-y-1.5"><Label>Pesan di Luar Jam Kerja</Label>
            <Textarea rows={2} value={cfg.away_reply_text || ""} onChange={(e) => set("away_reply_text", e.target.value)} data-testid="wa-away-text" /></div>

          {cfg.provider === "openwa" ? <OpenWaPanel /> : null}

          {cfg.provider === "meta_cloud" ? (
            <div className="rounded-[10px] border border-[#FFE6B0] bg-[#FFF8EC] p-3" data-testid="wa-meta-box">
              <p className="mb-2 flex items-center gap-2 text-[12px] font-semibold text-[#C25400]">
                Kredensial Meta Cloud
                {cfg.meta?.access_token_set && cfg.meta?.phone_number_id
                  ? <span className="inline-flex items-center gap-1 rounded-full bg-[#34C759]/15 px-2 py-0.5 text-[10.5px] font-semibold text-[#127A36]" data-testid="wa-meta-ready"><CheckCircle2 size={11} /> Siap kirim</span>
                  : <span className="inline-flex items-center gap-1 rounded-full bg-[#FF9500]/15 px-2 py-0.5 text-[10.5px] font-semibold text-[#8C4A00]" data-testid="wa-meta-ready">Belum lengkap</span>}
              </p>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-1.5"><Label>Phone Number ID</Label>
                  <Input value={cfg.meta?.phone_number_id || ""} onChange={(e) => setMeta("phone_number_id", e.target.value)} data-testid="wa-meta-pnid" /></div>
                <div className="space-y-1.5"><Label>Verify Token</Label>
                  <Input value={cfg.meta?.verify_token || ""} onChange={(e) => setMeta("verify_token", e.target.value)} data-testid="wa-meta-verify" /></div>
                <div className="space-y-1.5"><Label>Access Token {cfg.meta?.access_token_set ? "(tersimpan)" : ""}</Label>
                  <Input type="password" placeholder={cfg.meta?.access_token_set ? "•••• (biarkan kosong utk tetap)" : ""} value={cfg._access_token || ""} onChange={(e) => set("_access_token", e.target.value)} data-testid="wa-meta-token" /></div>
                <div className="space-y-1.5"><Label>App Secret {cfg.meta?.app_secret_set ? "(tersimpan)" : ""}</Label>
                  <Input type="password" placeholder={cfg.meta?.app_secret_set ? "••••" : ""} value={cfg._app_secret || ""} onChange={(e) => set("_app_secret", e.target.value)} data-testid="wa-meta-secret" /></div>
                <div className="space-y-1.5"><Label>API Version</Label>
                  <Input value={cfg.meta?.api_version || "v21.0"} onChange={(e) => setMeta("api_version", e.target.value)} placeholder="v21.0" data-testid="wa-meta-apiver" /></div>
              </div>
              <p className="mt-2 text-[11px] text-[#8C4A00]">Webhook URL: <code>{(process.env.REACT_APP_BACKEND_URL || "") + "/api/wa/webhook"}</code></p>
              <p className="mt-1 text-[11px] text-[#8C4A00]">Simpan kredensial lalu gunakan <b>Test Kirim</b> di bawah untuk memverifikasi koneksi Graph API.</p>
            </div>
          ) : null}

          <div className="rounded-[10px] border border-[#D6E4FF] bg-[#F2F7FF] p-3" data-testid="wa-testsend-box">
            <p className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold text-[#0058CC]"><Send size={13} /> Test Kirim Pesan</p>
            <p className="mb-2 text-[11.5px] text-[#3C3C43]">Kirim pesan uji via provider aktif (<b>{cfg.provider}</b>). Mock → selalu sukses (simulasi). Meta Cloud → kirim nyata (gagal rapi bila kredensial belum lengkap).</p>
            <div className="flex flex-wrap items-center gap-2">
              <Input value={testPhone} onChange={(e) => setTestPhone(e.target.value)} placeholder="62812xxxxxxx" className="max-w-[220px]" data-testid="wa-test-phone" />
              <button className="primary-button" onClick={testSend} disabled={testing} data-testid="wa-test-send">
                {testing ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} Test Kirim
              </button>
              {testResult ? (
                <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11.5px] font-semibold ${testResult.ok ? "bg-[#34C759]/15 text-[#127A36]" : "bg-[#FF3B30]/12 text-[#A8221A]"}`} data-testid="wa-test-result">
                  {testResult.ok ? <CheckCircle2 size={12} /> : <XCircle size={12} />} {testResult.ok ? `Terkirim (${testResult.provider})` : (testResult.error || "Gagal")}
                </span>
              ) : null}
            </div>
          </div>
        </div>
      </section>

      <section className="section-card" data-testid="settings-wa-templates">
        <div className="section-head">
          <div className="flex min-w-0 items-center gap-2"><FileText size={16} className="text-[#007AFF]" /><h2 className="truncate">Template WhatsApp</h2></div>
          <button className="primary-button flex-shrink-0" onClick={() => setEditing({ key: "", name: "", language: "id", category: "utility", body: "" })} data-testid="wa-tpl-add"><Plus size={14} /> Tambah</button>
        </div>
        <div className="section-body">
          <p className="mb-2 text-[12px] text-[#6B6B73]">Template untuk membalas di luar sesi 24 jam & dipakai aksi otomasi. Gunakan {"{variabel}"} untuk personalisasi.</p>
          {templates.length === 0 ? <p className="py-6 text-center text-[13px] text-[#8E8E93]" data-testid="wa-tpl-empty">Belum ada template.</p>
            : (
              <div className="divide-y divide-[#F2F2F5]" data-testid="wa-tpl-list">
                {templates.map((t) => (
                  <div key={t.key} className="flex flex-wrap items-start justify-between gap-3 py-3" data-testid={`wa-tpl-${t.key}`}>
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-2 text-[13px] font-bold text-[#1C1C1E]">{t.name} <span className="rounded-full bg-[#F2F2F5] px-2 py-0.5 text-[10.5px] text-[#6B6B73]">{t.key} · {t.category}</span></p>
                      <p className="mt-0.5 text-[11.5px] text-[#6B6B73]">{t.body}</p>
                    </div>
                    <div className="flex flex-shrink-0 items-center gap-2">
                      <button className="icon-button !h-8 !w-8" onClick={() => setEditing({ ...t })} data-testid={`wa-tpl-edit-${t.key}`}><Pencil size={14} /></button>
                      <button className="icon-button !h-8 !w-8" onClick={() => delTpl(t.key)} data-testid={`wa-tpl-del-${t.key}`}><Trash2 size={14} /></button>
                    </div>
                  </div>
                ))}
              </div>
            )}
        </div>
      </section>

      <Dialog open={!!editing} onOpenChange={(v) => !v && setEditing(null)}>
        <DialogContent data-testid="wa-tpl-dialog">
          <DialogHeader><DialogTitle>{editing?.name ? "Ubah Template" : "Template Baru"}</DialogTitle></DialogHeader>
          {editing ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5"><Label>Key (unik)</Label>
                  <Input value={editing.key} disabled={!!editing.name && templates.some((t) => t.key === editing.key)} onChange={(e) => setEditing((s) => ({ ...s, key: e.target.value.replace(/\s/g, "_").toLowerCase() }))} data-testid="wa-tpl-key" /></div>
                <div className="space-y-1.5"><Label>Nama</Label>
                  <Input value={editing.name} onChange={(e) => setEditing((s) => ({ ...s, name: e.target.value }))} data-testid="wa-tpl-name" /></div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5"><Label>Bahasa</Label>
                  <Input value={editing.language} onChange={(e) => setEditing((s) => ({ ...s, language: e.target.value }))} data-testid="wa-tpl-lang" /></div>
                <div className="space-y-1.5"><Label>Kategori</Label>
                  <Select value={editing.category} onValueChange={(v) => setEditing((s) => ({ ...s, category: v }))}>
                    <SelectTrigger data-testid="wa-tpl-cat"><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value="utility">Utility</SelectItem><SelectItem value="marketing">Marketing</SelectItem><SelectItem value="authentication">Authentication</SelectItem></SelectContent>
                  </Select></div>
              </div>
              <div className="space-y-1.5"><Label>Isi Pesan</Label>
                <Textarea rows={3} value={editing.body} onChange={(e) => setEditing((s) => ({ ...s, body: e.target.value }))} data-testid="wa-tpl-body" /></div>
            </div>
          ) : null}
          <DialogFooter>
            <button className="secondary-button" onClick={() => setEditing(null)} data-testid="wa-tpl-cancel">Batal</button>
            <button className="primary-button" onClick={saveTpl} disabled={busy} data-testid="wa-tpl-save">{busy ? <Loader2 size={14} className="animate-spin" /> : null} Simpan</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
