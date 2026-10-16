import { useCallback, useEffect, useRef, useState } from "react";
import { MessageCircle, X, Send, Loader2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

const TOKEN_KEY = "rahaza_chat_token";

// Widget chat publik (live) di situs — pesan masuk ke Inbox agen, balasan tampil di sini.
export default function ChatWidget() {
  const lang = useLangValue();
  const [open, setOpen] = useState(false);
  const [started, setStarted] = useState(Boolean(localStorage.getItem(TOKEN_KEY)));
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [hp, setHp] = useState("");
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const endRef = useRef(null);
  const pollRef = useRef(null);

  const token = () => localStorage.getItem(TOKEN_KEY);

  const loadThread = useCallback(async () => {
    const t = token();
    if (!t) return;
    try {
      const r = await apiClient.get(`/public/chat/${t}`);
      setMessages(r.data?.messages || []);
    } catch (e) {
      if (e?.response?.status === 404) { localStorage.removeItem(TOKEN_KEY); setStarted(false); }
    }
  }, []);

  useEffect(() => {
    if (open && started) {
      loadThread();
      pollRef.current = setInterval(loadThread, 5000);
      return () => clearInterval(pollRef.current);
    }
    return undefined;
  }, [open, started, loadThread]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages.length]);

  const send = async () => {
    if (!draft.trim()) return;
    setSending(true);
    try {
      const payload = { name: name.trim(), phone: phone.trim(), message: draft.trim(), token: token() || undefined, hp };
      const r = await apiClient.post("/public/chat", payload);
      if (r.data?.token) { localStorage.setItem(TOKEN_KEY, r.data.token); setStarted(true); }
      setDraft("");
      await loadThread();
    } catch (e) {
      /* tampilkan diam */
    } finally { setSending(false); }
  };

  return (
    <>
      {/* POSISI (design_guidelines §floating_elements_placement_rules).
          Dulu: FAB `bottom-24` & panel `bottom-40` + tinggi TETAP 440 px. Di viewport pendek
          (mis. 1920x800 / 390x640) 160 px + 440 px = 600 px sehingga puncak panel menembus
          header + bar pengumuman (bukti screenshot user). Sekarang offset diturunkan dari
          token `--fab-bottom`/`--panel-bottom` (ikut tinggi StickyMobileCTA + safe-area) dan
          tingginya DIBATASI tinggi viewport dikurangi header. */}
      <button
        onClick={() => setOpen((v) => !v)}
        data-testid="public-chat-fab"
        className="fixed right-4 flex h-12 w-12 items-center justify-center rounded-full bg-[#101935] text-white shadow-lg transition hover:scale-105 sm:right-6"
        style={{ bottom: "var(--fab-bottom)", zIndex: "var(--z-chat, 60)" }}
        aria-label={open ? bi("Tutup chat", "Close chat", lang) : bi("Chat dengan kami", "Chat with us", lang)}
        aria-expanded={open}
      >
        {open ? <X size={20} /> : <MessageCircle size={20} />}
      </button>

      {open ? (
        <div
          className="fixed right-4 flex flex-col overflow-hidden rounded-2xl border border-black/10 bg-white shadow-2xl sm:right-6"
          data-testid="public-chat-panel"
          role="dialog"
          aria-label={bi("Chat dengan tim kami", "Chat with our team", lang)}
          style={{
            bottom: "var(--panel-bottom)",
            zIndex: "var(--z-chat, 60)",
            width: "min(340px, calc(100vw - 2rem))",
            height: "clamp(320px, 58dvh, 460px)",
            maxHeight: "calc(100dvh - var(--header-h) - var(--panel-bottom) - 12px)",
          }}
        >
          <div className="flex items-center gap-2 bg-[#101935] px-4 py-3 text-white">
            <MessageCircle size={16} />
            <div>
              <p className="text-[13px] font-semibold">{bi("Chat dengan RahazaTrans", "Chat with RahazaTrans", lang)}</p>
              <p className="text-[10.5px] text-white/70">{bi("Balasan biasanya dalam beberapa menit", "Replies usually within a few minutes", lang)}</p>
            </div>
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto bg-[#F7F8FB] p-3" data-testid="public-chat-messages">
            {!started ? (
              <div className="rounded-lg bg-white p-3 text-[12.5px] text-[#5b6172] shadow-sm">
                {bi("Halo! Ada yang bisa kami bantu? Tulis pertanyaan Anda di bawah, tim kami akan segera membalas.", "Hi! How can we help? Type your question below and our team will reply shortly.", lang)}
              </div>
            ) : messages.length === 0 ? (
              <p className="text-center text-[12px] text-[#8E8E93]">{bi("Memulai percakapan…", "Starting the conversation…", lang)}</p>
            ) : (
              messages.map((m, i) => {
                const mine = m.sender === "customer";
                return (
                  <div key={i} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[80%] rounded-2xl px-3 py-2 text-[13px] ${mine ? "bg-[#101935] text-white" : "border border-black/5 bg-white text-[#1c2233]"}`}>
                      {m.body}
                    </div>
                  </div>
                );
              })
            )}
            <div ref={endRef} />
          </div>

          <div className="border-t border-black/5 bg-white p-3">
            {!started ? (
              <div className="mb-2 grid grid-cols-2 gap-2">
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder={bi("Nama", "Name", lang)} className="rounded-lg border border-[#d8dae2] px-2.5 py-2 text-[13px] outline-none focus:border-[#101935]" data-testid="public-chat-name" />
                <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder={bi("No. HP", "Phone", lang)} className="rounded-lg border border-[#d8dae2] px-2.5 py-2 text-[13px] outline-none focus:border-[#101935]" data-testid="public-chat-phone" />
              </div>
            ) : null}
            <input aria-hidden="true" tabIndex={-1} autoComplete="off" value={hp} onChange={(e) => setHp(e.target.value)} data-testid="public-chat-hp" style={{ position: "absolute", left: "-9999px", height: 0, width: 0, opacity: 0 }} />
            <div className="flex items-end gap-2">
              <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={1} placeholder={bi("Tulis pesan…", "Type a message…", lang)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                className="flex-1 resize-none rounded-lg border border-[#d8dae2] px-3 py-2 text-[13px] outline-none focus:border-[#101935]" data-testid="public-chat-input" />
              <button onClick={send} disabled={sending || !draft.trim()} className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#101935] text-white disabled:opacity-50" data-testid="public-chat-send">
                {sending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
