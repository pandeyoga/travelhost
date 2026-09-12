import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, Eraser, Info, Languages, Loader2, Sparkles } from "lucide-react";
import apiClient from "@/services/apiClient";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import RichTextEditor from "@/components/cms/RichTextEditor";

/**
 * TranslationFields — CMS-06: isi versi English satu konten.
 *
 * Prinsip yang dijaga:
 *  - **Field terbatas.** Daftar field diambil dari server (`GET /api/content/meta/i18n`),
 *    bukan ditulis ulang di frontend — kalau backend menambah field terjemahan, UI ikut
 *    tanpa perubahan kode (dan mustahil menulis field yang tidak diizinkan).
 *  - **Kosong = jatuh ke Indonesia.** Halaman English tidak pernah tampil berlubang; itulah
 *    sebabnya field boleh dikosongkan tanpa rasa takut.
 *  - **Manual sesuai keputusan pemilik.** Terjemahan otomatis (AI) DIMATIKAN. Bila suatu saat
 *    kunci LLM dipasang, tombol "Terjemahkan" muncul sendiri karena `ai_available` dibaca
 *    dari server — hasilnya pun hanya SARAN yang masih bisa disunting.
 */
export default function TranslationFields({ resource, fields, base, value, onChange }) {
  const [meta, setMeta] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    apiClient.get("/content/meta/i18n")
      .then((r) => { if (alive) setMeta(r.data); })
      .catch(() => { if (alive) setMeta({ translatable: {}, ai_available: false }); });
    return () => { alive = false; };
  }, []);

  const keys = (meta?.translatable || {})[resource] || [];
  const en = value || {};
  const set = (k, v) => onChange({ ...en, [k]: v });

  const fieldConf = (k) => fields.find((f) => f.k === k) || { k, label: k, type: "text" };

  const copyFrom = (k) => {
    const src = base?.[k];
    if (src === undefined || src === null || src === "") {
      toast.message("Versi Indonesia masih kosong");
      return;
    }
    set(k, src);
  };

  const translateAll = async () => {
    const payload = {};
    keys.forEach((k) => {
      const v = base?.[k];
      if (typeof v === "string" && v.trim()) payload[k] = v;
      else if (Array.isArray(v) && v.length) payload[k] = v;
    });
    if (!Object.keys(payload).length) { toast.message("Belum ada teks Indonesia untuk diterjemahkan"); return; }
    setBusy(true);
    try {
      const { data } = await apiClient.post(`/content/${resource}/translate`, { target: "en", fields: payload });
      onChange({ ...en, ...(data?.translations || {}) });
      toast.success("Saran terjemahan dimuat — silakan tinjau sebelum menyimpan");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Terjemahan otomatis tidak tersedia");
    } finally { setBusy(false); }
  };

  if (!meta) {
    return <p className="px-1 py-6 text-center text-[12.5px] text-[#6B6B73]" data-testid="cf-en-loading">Memuat daftar field terjemahan…</p>;
  }

  if (!keys.length) {
    return (
      <div className="rounded-[12px] border border-dashed border-[#D9DADF] bg-[#F7F8FA] px-4 py-8 text-center" data-testid="cf-en-empty">
        <Languages size={18} className="mx-auto mb-2 text-[#8E8E93]" />
        <p className="text-[13px] font-semibold text-[#1C1C1E]">Jenis konten ini belum punya field terjemahan</p>
        <p className="mt-1 text-[11.5px] text-[#6B6B73]">Testimoni ditulis dalam bahasa aslinya oleh pelanggan, jadi tidak diterjemahkan.</p>
      </div>
    );
  }

  const filled = keys.filter((k) => {
    const v = en[k];
    return Array.isArray(v) ? v.length > 0 : String(v || "").trim().length > 0;
  }).length;

  return (
    <div className="space-y-3" data-testid="cf-en-panel">
      <div className="flex flex-wrap items-start justify-between gap-2 rounded-[12px] border border-[#D5E4FF] bg-[#F4F8FF] px-3 py-2.5">
        <p className="flex items-start gap-1.5 text-[11.5px] leading-relaxed text-[#0058CC]">
          <Info size={13} className="mt-0.5 shrink-0" />
          <span>
            Terisi <span className="font-bold tabular-nums">{filled}/{keys.length}</span> field.
            Field yang dikosongkan otomatis memakai versi Indonesia — halaman English tidak akan berlubang.
          </span>
        </p>
        {meta.ai_available ? (
          <button type="button" className="secondary-button" onClick={translateAll} disabled={busy} data-testid="cf-en-translate">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} Terjemahkan dengan AI
          </button>
        ) : (
          <span className="rounded-md bg-white px-2 py-1 text-[10.5px] font-semibold text-[#6B6B73]" data-testid="cf-en-manual-note">
            Terjemahan otomatis OFF — isi manual
          </span>
        )}
      </div>

      {keys.map((k) => {
        const conf = fieldConf(k);
        const idVal = base?.[k];
        const idPreview = Array.isArray(idVal) ? idVal.join(" · ") : String(idVal || "");
        const enVal = en[k];
        return (
          <div key={k} className="space-y-1">
            <div className="flex items-center justify-between gap-2">
              <Label className="text-[12px]">{conf.label} <span className="text-[#8A8A8F]">(EN)</span></Label>
              <div className="flex items-center gap-1">
                <button type="button" title="Salin dari Indonesia" onClick={() => copyFrom(k)}
                  className="flex h-6 items-center gap-1 rounded-md px-1.5 text-[10.5px] font-semibold text-[#0058CC] transition hover:bg-[#F2F2F5]"
                  data-testid={`cf-en-copy-${k}`}><Copy size={11} /> Salin ID</button>
                <button type="button" title="Kosongkan (pakai versi Indonesia)" onClick={() => set(k, Array.isArray(idVal) ? [] : "")}
                  className="flex h-6 items-center gap-1 rounded-md px-1.5 text-[10.5px] font-semibold text-[#6B6B73] transition hover:bg-[#F2F2F5]"
                  data-testid={`cf-en-clear-${k}`}><Eraser size={11} /> Kosongkan</button>
              </div>
            </div>

            {conf.type === "richtext" ? (
              <RichTextEditor value={String(enVal || "")} onChange={(v) => set(k, v)} testId={`cf-en-rte-${k}`}
                placeholder="Write the English version…" />
            ) : conf.type === "list" ? (
              <Textarea rows={3} value={Array.isArray(enVal) ? enVal.join("\n") : String(enVal || "")}
                onChange={(e) => set(k, e.target.value.split("\n").map((s) => s.trim()).filter(Boolean))}
                placeholder="One item per line" data-testid={`cf-en-${k}`} />
            ) : conf.type === "textarea" ? (
              <Textarea rows={3} value={String(enVal || "")} onChange={(e) => set(k, e.target.value)}
                data-testid={`cf-en-${k}`} />
            ) : (
              <Input value={String(enVal || "")} onChange={(e) => set(k, e.target.value)}
                data-testid={`cf-en-${k}`} />
            )}

            {idPreview ? (
              <p className="line-clamp-2 rounded-md bg-[#F7F8FA] px-2 py-1 text-[10.5px] leading-relaxed text-[#8A8A8F]">
                ID: {idPreview.replace(/<[^>]*>/g, " ").slice(0, 220)}
              </p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
