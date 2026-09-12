import { useState } from "react";
import { Loader2, Tag, X, Info, ShieldCheck } from "lucide-react";
import PromoPicker from "@/components/public/booking/PromoPicker";
import { formatCurrency } from "@/utils/formatters";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

// QuoteBreakdown — rincian harga TRANSPARAN + kolom kode promo + DAFTAR promo yang bisa diklik.
//
// Rincian ditampilkan per item (sewa, surcharge tanggal, driver, tol/parkir, potongan promo)
// karena "satu angka besar tanpa penjelasan" adalah alasan nomor satu orang batal memesan
// sewa kendaraan. Validasi promo dilakukan SERVER — pesan penolakannya ditampilkan apa adanya
// supaya pengunjung tahu apa yang harus diubah (mis. "minimal 2 hari").
export default function QuoteBreakdown({ quote, promo, onApplyPromo, onClearPromo, applying,
                                        policy, dpNote, promoContext }) {
  const lang = useLangValue();
  const [code, setCode] = useState("");
  const q = quote || {};
  const lines = q.breakdown || [];
  return (
    <div className="rounded-2xl border border-border bg-card p-5" data-testid="booking-quote">
      <h3 className="font-fraunces text-xl text-foreground">{bi("Rincian harga", "Price breakdown", lang)}</h3>
      {lines.length === 0 ? (
        <p className="mt-4 text-[13px] text-muted-foreground" data-testid="booking-quote-empty">
          {bi("Belum ada rincian — pilih unit dulu.", "No breakdown yet — pick a unit first.", lang)}
        </p>
      ) : (
        <>
          <div className="mt-3 divide-y divide-border">
            {lines.map((b, i) => (
              <div key={i} className="flex items-start justify-between gap-3 py-2.5 text-[13.5px]">
                <span className={b.amount < 0 ? "text-primary" : "text-muted-foreground"}>{b.label}</span>
                <span className={`shrink-0 font-mono font-semibold tabular-nums ${
                  b.amount < 0 ? "text-primary" : "text-foreground"}`}>
                  {formatCurrency(b.amount)}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between rounded-xl px-4 py-3.5 text-primary-foreground"
            style={{ background: "var(--gradient-cta)" }}>
            <span className="text-[13px] font-medium opacity-90">{bi("Total", "Total", lang)}</span>
            <span className="font-mono text-2xl font-semibold tabular-nums" data-testid="booking-quote-total">
              {formatCurrency(q.total)}
            </span>
          </div>
          {q.dp_amount ? (
            <div className="mt-2 flex items-center justify-between rounded-xl border border-border bg-secondary px-4 py-3">
              <span className="text-[12.5px] text-secondary-foreground">
                {bi(`Bayar sekarang (DP ${q.dp_percent}%)`, `Pay now (deposit ${q.dp_percent}%)`, lang)}
              </span>
              <span className="font-mono text-[15px] font-semibold tabular-nums text-foreground" data-testid="booking-quote-dp">
                {formatCurrency(q.dp_amount)}
              </span>
            </div>
          ) : null}
        </>
      )}

      <div className="mt-4">
        <label className="text-[12.5px] font-medium text-foreground/80">{bi("Kode promo", "Promo code", lang)}</label>
        {promo?.code ? (
          <div className="mt-1 flex items-center justify-between rounded-lg border border-primary/40 bg-primary/5 px-3 py-2.5"
            data-testid="booking-promo-applied">
            <span className="inline-flex items-center gap-2 text-[13px] font-semibold text-primary">
              <Tag size={14} /> {promo.code}
            </span>
            <button type="button" onClick={onClearPromo} data-testid="booking-promo-clear"
              className="inline-flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground">
              <X size={12} /> {bi("Hapus", "Remove", lang)}
            </button>
          </div>
        ) : (
          <div className="mt-1 flex gap-2">
            <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder={bi("MIS. GATHERING500", "E.G. GATHERING500", lang)} data-testid="booking-promo-input"
              className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-[13.5px] uppercase text-foreground outline-none focus:border-ring" />
            <button type="button" disabled={!code.trim() || applying} data-testid="booking-promo-apply"
              onClick={() => onApplyPromo(code.trim())}
              className="shrink-0 rounded-lg border border-border bg-card px-4 py-2.5 text-[13px] font-semibold text-foreground transition hover:-translate-y-0.5 disabled:opacity-50">
              {applying ? <Loader2 size={14} className="animate-spin" /> : bi("Pakai", "Apply", lang)}
            </button>
          </div>
        )}
        {promo?.error ? (
          <p className="mt-1.5 text-[12px] text-[hsl(var(--destructive))]" data-testid="booking-promo-error">
            {promo.error}
          </p>
        ) : null}

        {promoContext ? (
          <PromoPicker context={promoContext} appliedCode={promo?.code} onApply={onApplyPromo}
            applying={applying} />
        ) : null}
      </div>

      {dpNote ? (
        <p className="mt-4 flex items-start gap-2 text-[12px] leading-relaxed text-muted-foreground">
          <ShieldCheck size={14} className="mt-0.5 shrink-0 text-primary" /> {dpNote}
        </p>
      ) : null}
      {policy ? (
        <p className="mt-2 flex items-start gap-2 text-[12px] leading-relaxed text-muted-foreground">
          <Info size={14} className="mt-0.5 shrink-0" /> {policy}
        </p>
      ) : null}
    </div>
  );
}
