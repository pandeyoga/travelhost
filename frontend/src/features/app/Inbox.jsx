import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Inbox as InboxIcon, Send, StickyNote, Globe, MessageCircle, Phone, Check, CheckCheck,
  UserCheck, Search, Loader2, ChevronLeft, Clock, Ban, ShieldCheck, Sparkles, Zap, Paperclip, X, FileText,
} from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { useAuth } from "@/context/AuthContext";
import { LoadingState, EmptyState } from "@/components/shared/DataStates";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { formatDateTime, formatCurrency } from "@/utils/formatters";

const FILTERS = [
  { v: "all", l: "Semua" }, { v: "unassigned", l: "Belum di-assign" }, { v: "mine", l: "Tugas Saya" },
];
const CHANNEL_ICON = { web: Globe, whatsapp: MessageCircle, internal: Phone };
const CHANNEL_LABEL = { web: "Web Chat", whatsapp: "WhatsApp", internal: "Internal" };
const STATUS_TONE = { open: "success", snoozed: "warning", closed: "neutral" };
const STATUS_LABEL = { open: "Terbuka", snoozed: "Ditunda", closed: "Selesai" };

function MsgStatus({ status }) {
  if (status === "read") return <CheckCheck size={13} className="text-[#34C759]" />;
  if (status === "delivered") return <CheckCheck size={13} className="text-[#8E8E93]" />;
  return <Check size={13} className="text-[#8E8E93]" />;
}

export default function Inbox() {
  const { user } = useAuth();
  const [conversations, setConversations] = useState([]);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState(null);
  const [active, setActive] = useState(null);
  const [loadingThread, setLoadingThread] = useState(false);
  const [draft, setDraft] = useState("");
  const [internal, setInternal] = useState(false);
  const [attachFile, setAttachFile] = useState(null);
  const fileRef = useRef(null);
  const [sending, setSending] = useState(false);
  const [users, setUsers] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [simOpen, setSimOpen] = useState(false);
  const [sim, setSim] = useState({ from_phone: "", text: "", name: "" });
  const [simBusy, setSimBusy] = useState(false);
  const endRef = useRef(null);

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter !== "all") params.set("assigned", filter);
      if (search.trim()) params.set("q", search.trim());
      const r = await apiClient.get(`/conversations?${params.toString()}`);
      setConversations(Array.isArray(r.data) ? r.data : []);
    } catch (e) {
      setConversations([]);
    } finally { setLoading(false); }
  }, [filter, search]);

  const loadThread = useCallback(async (id) => {
    if (!id) return;
    setLoadingThread(true);
    try {
      const r = await apiClient.get(`/conversations/${id}`);
      setActive(r.data);
      if (r.data?.unread > 0) {
        await apiClient.post(`/conversations/${id}/read`).catch(() => {});
      }
    } catch (e) {
      toast.error("Gagal memuat percakapan");
    } finally { setLoadingThread(false); }
  }, []);

  useEffect(() => { loadList(); }, [loadList]);
  useEffect(() => { apiClient.get("/users").then((r) => setUsers(Array.isArray(r.data) ? r.data : [])).catch(() => {}); }, []);
  useEffect(() => { apiClient.get("/wa/templates").then((r) => setTemplates(Array.isArray(r.data) ? r.data : [])).catch(() => {}); }, []);
  useEffect(() => { if (activeId) loadThread(activeId); }, [activeId, loadThread]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [active?.messages?.length]);

  const openConv = (c) => setActiveId(c.id);

  const send = async (payload) => {
    if (!activeId) return;
    if (!payload && attachFile && !internal) {
      setSending(true);
      try {
        const fd = new FormData();
        fd.append("file", attachFile);
        fd.append("caption", draft.trim());
        await apiClient.post(`/conversations/${activeId}/wa-media`, fd, { headers: { "Content-Type": "multipart/form-data" } });
        setDraft(""); setAttachFile(null);
        if (fileRef.current) fileRef.current.value = "";
        await loadThread(activeId);
        loadList();
        toast.success("Lampiran terkirim via WhatsApp");
      } catch (e) {
        toast.error(e?.response?.data?.detail || "Gagal mengirim lampiran");
      } finally { setSending(false); }
      return;
    }
    const body = payload || { body: draft.trim(), internal };
    if (!body.body && !body.template_key) return;
    setSending(true);
    try {
      await apiClient.post(`/conversations/${activeId}/messages`, body);
      setDraft(""); setInternal(false);
      await loadThread(activeId);
      loadList();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengirim pesan");
    } finally { setSending(false); }
  };

  const pickFile = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 8 * 1024 * 1024) { toast.error("Ukuran file maksimal 8 MB"); e.target.value = ""; return; }
    setAttachFile(f);
  };

  const sendTemplate = (key) => {
    if (!key || key === "none") return;
    send({ template_key: key, body: "" });
    toast.success("Template WhatsApp dikirim");
  };

  const toggleOptIn = async () => {
    if (!active) return;
    const next = active.wa_opt_in === false; // currently opted-out -> opt-in
    try {
      await apiClient.post(`/conversations/${activeId}/${next ? "wa-optin" : "wa-optout"}`);
      toast.success(next ? "Kontak di-opt-in WhatsApp" : "Kontak di-opt-out (berhenti) WhatsApp");
      loadThread(activeId); loadList();
    } catch (e) { toast.error("Gagal mengubah opt-in"); }
  };

  const simulate = async () => {
    if (!sim.from_phone.trim() || !sim.text.trim()) { toast.error("Nomor & pesan wajib diisi"); return; }
    setSimBusy(true);
    try {
      const r = await apiClient.post("/wa/simulate-inbound", sim);
      toast.success(r.data?.lead_created ? "Pesan masuk + lead baru dibuat" : "Pesan WA masuk diterima");
      setSim({ from_phone: "", text: "", name: "" }); setSimOpen(false);
      loadList();
      if (r.data?.conversation_id) setActiveId(r.data.conversation_id);
    } catch (e) { toast.error("Gagal menyimulasikan pesan"); }
    finally { setSimBusy(false); }
  };

  const assign = async (val) => {
    try {
      await apiClient.patch(`/conversations/${activeId}`, { assigned_to: val === "none" ? "" : val });
      toast.success(val === "none" ? "Assign dilepas" : "Percakapan di-assign");
      loadThread(activeId); loadList();
    } catch (e) { toast.error("Gagal mengubah assign"); }
  };
  const setStatus = async (val) => {
    try {
      await apiClient.patch(`/conversations/${activeId}`, { status: val });
      toast.success("Status diperbarui");
      loadThread(activeId); loadList();
    } catch (e) { toast.error("Gagal mengubah status"); }
  };

  const ChIcon = active ? (CHANNEL_ICON[active.channel] || Phone) : Phone;

  if (loading && conversations.length === 0 && !activeId) return <LoadingState testId="inbox-loading" />;

  return (
    <div className="section-card overflow-hidden" data-testid="inbox-page">
      <div className="grid grid-cols-1 md:grid-cols-[340px_1fr]" style={{ minHeight: 560 }}>
        {/* List pane */}
        <div className={`border-r border-[#EFF0F2] ${activeId ? "hidden md:block" : "block"}`}>
          <div className="border-b border-[#EFF0F2] p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <InboxIcon size={16} className="text-[#007AFF]" />
                <h2 className="text-[14px] font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>Inbox</h2>
              </div>
              <button onClick={() => setSimOpen((v) => !v)} data-testid="inbox-simulate-toggle"
                className="flex items-center gap-1 rounded-full bg-[#E8F8EE] px-2.5 py-1 text-[11px] font-semibold text-[#1B8A4B] transition hover:bg-[#D7F2E2]">
                <Sparkles size={12} /> Simulasi WA
              </button>
            </div>
            {simOpen ? (
              <div className="mb-2 space-y-2 rounded-[10px] border border-[#CDEBD8] bg-[#F4FCF7] p-2.5" data-testid="inbox-simulate-panel">
                <p className="flex items-center gap-1 text-[11px] font-semibold text-[#1B8A4B]"><MessageCircle size={12} /> Simulasikan pesan WhatsApp masuk (mock)</p>
                <Input value={sim.from_phone} onChange={(e) => setSim((s) => ({ ...s, from_phone: e.target.value }))} placeholder="Nomor pengirim (08xx)" data-testid="inbox-sim-phone" />
                <Input value={sim.name} onChange={(e) => setSim((s) => ({ ...s, name: e.target.value }))} placeholder="Nama (opsional)" data-testid="inbox-sim-name" />
                <Textarea rows={2} value={sim.text} onChange={(e) => setSim((s) => ({ ...s, text: e.target.value }))} placeholder="Isi pesan…" data-testid="inbox-sim-text" />
                <button className="primary-button w-full !h-9" onClick={simulate} disabled={simBusy} data-testid="inbox-sim-send">
                  {simBusy ? <Loader2 size={14} className="animate-spin" /> : <Send size={13} />} Kirim Simulasi
                </button>
              </div>
            ) : null}
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#8E8E93]" />
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari nama/telepon/subjek" className="pl-8" data-testid="inbox-search" />
            </div>
            <div className="mt-2 inline-flex w-full rounded-[10px] border border-[#EFF0F2] bg-[#F7F7F9] p-0.5">
              {FILTERS.map((f) => (
                <button key={f.v} onClick={() => setFilter(f.v)} data-testid={`inbox-filter-${f.v}`}
                  className={`flex-1 rounded-[8px] px-2 py-1.5 text-[11.5px] font-semibold transition ${filter === f.v ? "bg-white text-[#007AFF] shadow-sm" : "text-[#6B6B73]"}`}>
                  {f.l}
                </button>
              ))}
            </div>
          </div>
          <div className="max-h-[520px] overflow-y-auto" data-testid="inbox-list">
            {conversations.length === 0 ? (
              <div className="p-6"><EmptyState title="Tidak ada percakapan" description="Percakapan dari web-chat & WhatsApp akan muncul di sini." testId="inbox-empty" /></div>
            ) : (
              conversations.map((c) => {
                const CIcon = CHANNEL_ICON[c.channel] || Phone;
                return (
                  <button key={c.id} onClick={() => openConv(c)} data-testid={`inbox-conv-${c.id}`}
                    className={`flex w-full items-start gap-2.5 border-b border-[#F5F5F7] px-3 py-3 text-left transition hover:bg-[#FAFAFB] ${activeId === c.id ? "bg-[#F0F6FF]" : ""}`}>
                    <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[#EAF3FF]"><CIcon size={14} className="text-[#007AFF]" /></div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-[13px] font-semibold text-[#1C1C1E]">{c.contact_name}</span>
                        {c.unread > 0 ? <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-[#FF3B30] px-1 text-[10px] font-bold text-white">{c.unread}</span> : null}
                      </div>
                      <p className="truncate text-[11.5px] text-[#6B6B73]">{c.last_message_preview || c.subject}</p>
                      <div className="mt-1 flex items-center gap-1.5">
                        <span className={`status-pill tone-${STATUS_TONE[c.status]} !px-1.5 !py-0`} style={{ fontSize: 10 }}>{STATUS_LABEL[c.status]}</span>
                        <span className="text-[10px] text-[#A0A0A8]">{CHANNEL_LABEL[c.channel]}{c.assignee_name ? ` · ${c.assignee_name}` : ""}</span>
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Thread pane */}
        <div className={`flex flex-col ${activeId ? "flex" : "hidden md:flex"}`} style={{ maxHeight: 600 }}>
          {!active ? (
            <div className="flex flex-1 items-center justify-center p-10 text-center text-[13px] text-[#8E8E93]" data-testid="inbox-no-selection">
              Pilih percakapan untuk membuka thread.
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between gap-2 border-b border-[#EFF0F2] p-3">
                <div className="flex min-w-0 items-center gap-2">
                  <button className="icon-button !h-8 !w-8 md:hidden" onClick={() => { setActiveId(null); setActive(null); }} data-testid="inbox-back"><ChevronLeft size={16} /></button>
                  <ChIcon size={16} className="text-[#007AFF]" />
                  <div className="min-w-0">
                    <p className="truncate text-[13.5px] font-bold text-[#1C1C1E]">{active.contact_name}</p>
                    <p className="truncate text-[11px] text-[#8E8E93]">{active.contact_phone || CHANNEL_LABEL[active.channel]} · {active.subject}</p>
                  </div>
                </div>
                <div className="flex flex-shrink-0 items-center gap-1.5">
                  <Select value={active.assigned_to || "none"} onValueChange={assign}>
                    <SelectTrigger className="!h-8 w-[140px] text-[12px]" data-testid="inbox-assign"><UserCheck size={12} className="mr-1" /><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Belum di-assign</SelectItem>
                      {users.filter((u) => u.role !== "driver").map((u) => <SelectItem key={u.id} value={u.id}>{u.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <Select value={active.status} onValueChange={setStatus}>
                    <SelectTrigger className="!h-8 w-[110px] text-[12px]" data-testid="inbox-status"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="open">Terbuka</SelectItem>
                      <SelectItem value="snoozed">Ditunda</SelectItem>
                      <SelectItem value="closed">Selesai</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {active.channel === "whatsapp" ? (
                <div className="flex flex-wrap items-center gap-2 border-b border-[#EFF0F2] bg-[#FBFEFC] px-3 py-2 text-[11px]" data-testid="inbox-wa-bar">
                  {active.wa_within_session
                    ? <span className="flex items-center gap-1 rounded-full bg-[#E8F8EE] px-2 py-0.5 font-semibold text-[#1B8A4B]"><Clock size={11} /> Sesi 24 jam aktif</span>
                    : <span className="flex items-center gap-1 rounded-full bg-[#FFF1D6] px-2 py-0.5 font-semibold text-[#C25400]"><Clock size={11} /> Di luar sesi · gunakan template</span>}
                  <span className="flex items-center gap-1 text-[#6B6B73]">Biaya WA: <b className="tabular-nums text-[#1C1C1E]">{formatCurrency(active.total_cost || 0)}</b></span>
                  {active.wa_opt_in === false
                    ? <button onClick={toggleOptIn} className="flex items-center gap-1 rounded-full bg-[#FFE0DC] px-2 py-0.5 font-semibold text-[#A8221A]" data-testid="inbox-wa-optin"><Ban size={11} /> Opt-out · klik untuk opt-in</button>
                    : <button onClick={toggleOptIn} className="flex items-center gap-1 rounded-full bg-[#F2F2F5] px-2 py-0.5 font-semibold text-[#6B6B73]" data-testid="inbox-wa-optout"><ShieldCheck size={11} /> Opt-in aktif · klik untuk opt-out</button>}
                </div>
              ) : null}

              <div className="flex-1 space-y-2.5 overflow-y-auto bg-[#FAFAFB] p-4" data-testid="inbox-thread">
                {loadingThread ? (
                  <p className="text-center text-[12px] text-[#8E8E93]">Memuat…</p>
                ) : (active.messages || []).length === 0 ? (
                  <p className="text-center text-[12px] text-[#8E8E93]">Belum ada pesan.</p>
                ) : (
                  (active.messages || []).map((m) => {
                    if (m.internal) {
                      return (
                        <div key={m.id} className="mx-auto max-w-[85%] rounded-lg border border-[#FFE6B0] bg-[#FFF8EC] px-3 py-2" data-testid={`inbox-msg-${m.id}`}>
                          <div className="mb-0.5 flex items-center gap-1 text-[10.5px] font-semibold text-[#C25400]"><StickyNote size={11} /> Catatan internal · {m.author_name || "Agen"}</div>
                          <p className="text-[12.5px] text-[#7A4A00]">{m.body}</p>
                        </div>
                      );
                    }
                    const mine = m.sender === "agent";
                    return (
                      <div key={m.id} className={`flex ${mine ? "justify-end" : "justify-start"}`} data-testid={`inbox-msg-${m.id}`}>
                        <div className={`max-w-[75%] rounded-2xl px-3.5 py-2 ${mine ? "bg-[#007AFF] text-white" : "border border-[#EFF0F2] bg-white text-[#1C1C1E]"}`}>
                          {m.attachment ? (
                            <p className={`mb-1 flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11.5px] font-semibold ${mine ? "bg-white/15" : "bg-[#F2F2F5]"}`} data-testid={`inbox-msg-attachment-${m.id}`}>
                              <FileText size={12} /> {m.attachment.filename || "Lampiran"}
                            </p>
                          ) : null}
                          <p className="text-[13px] leading-snug">{m.body}</p>
                          <div className={`mt-0.5 flex items-center gap-1 text-[10px] ${mine ? "text-white/70" : "text-[#A0A0A8]"}`}>
                            <span>{formatDateTime(m.created_at)}</span>
                            {m.template_key ? <span className="rounded bg-white/20 px-1">tpl:{m.template_key}</span> : null}
                            {mine && m.cost ? <span className="tabular-nums">· Rp {Math.round(m.cost)}</span> : null}
                            {mine ? <MsgStatus status={m.status} /> : null}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={endRef} />
              </div>

              <div className="border-t border-[#EFF0F2] p-3">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <button onClick={() => setInternal((v) => !v)} data-testid="inbox-internal-toggle"
                    className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold transition ${internal ? "bg-[#FFF1D6] text-[#C25400]" : "bg-[#F2F2F5] text-[#6B6B73]"}`}>
                    <StickyNote size={12} /> {internal ? "Catatan internal" : "Balas ke kontak"}
                  </button>
                  {active.channel === "whatsapp" && !internal ? (
                    <>
                      <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp,application/pdf" className="hidden" onChange={pickFile} data-testid="inbox-attach-input" />
                      <button onClick={() => fileRef.current?.click()} data-testid="inbox-attach-btn"
                        className="flex items-center gap-1 rounded-full bg-[#F2F2F5] px-2.5 py-1 text-[11px] font-semibold text-[#6B6B73] transition hover:bg-[#E8E8EC]">
                        <Paperclip size={12} /> Lampiran
                      </button>
                      {attachFile ? (
                        <span className="flex items-center gap-1 rounded-full bg-[#D6F5DE] px-2.5 py-1 text-[11px] font-semibold text-[#127A36]" data-testid="inbox-attach-chip">
                          <FileText size={11} /> {attachFile.name}
                          <button onClick={() => { setAttachFile(null); if (fileRef.current) fileRef.current.value = ""; }} data-testid="inbox-attach-remove"><X size={11} /></button>
                        </span>
                      ) : null}
                    </>
                  ) : null}
                  {active.channel === "whatsapp" && !internal && templates.length > 0 ? (
                    <Select value="none" onValueChange={sendTemplate}>
                      <SelectTrigger className="!h-7 w-[180px] text-[11px]" data-testid="inbox-template-select"><Zap size={12} className="mr-1 text-[#25D366]" /><SelectValue placeholder="Kirim template" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none" disabled>Kirim template…</SelectItem>
                        {templates.map((t) => <SelectItem key={t.key} value={t.key}>{t.name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  ) : null}
                </div>
                <div className="flex items-end gap-2">
                  <Textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={2}
                    placeholder={internal ? "Tulis catatan internal (tidak terkirim ke kontak)…" : attachFile ? "Caption lampiran (opsional)…" : "Tulis balasan…"}
                    onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send(); }}
                    data-testid="inbox-composer" />
                  <button className="primary-button !h-10" disabled={sending || (!draft.trim() && !attachFile)} onClick={() => send()} data-testid="inbox-send">
                    {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
