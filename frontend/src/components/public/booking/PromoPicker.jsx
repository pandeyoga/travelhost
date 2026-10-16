import { useCallback, useEffect, useState } from "react";
import { Loader2, Tag, TicketPercent, Lock } from "lucide-react";
import { listBookingPromos } from "@/services/bookingApi";
import { formatCurrency } from "@/utils/formatters";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

/**
 * PromoPicker — daftar promo AKTIF yang bisa diklik langsung di wizard `/booking`.
 *
 * Kelayakan & besar potongan DIHITUNG SERVER (endpoint POST /public/booking/promos memakai
 * `services/promos.evaluate` yang sama dengan checkout). Promo yang BELUM memenuhi syarat
 * tetap ditampilkan bersama ALASANNYA (mis. "minimal 2 hari").
 */
export default function PromoPicker({ context, appliedCode, onApply, applying, testId = "booking-promo-list" }) {
  const lang = useLangValue();
  const [state, setState] = useState({ loading: true, error: "", items: [] });
  const key = JSON.stringify(context || {});

  const load = useCallback(async () => {
    if (!context?.vehicle_id || !context?.start_datetime) return;
    setState((s) => ({ ...s, loading: true, error: "" }));
    try {
      const data = await listBookingPromos(context);
      setState({ loading: false, error: "", items: data?.promos || [] });
    } catch (e) {
      setState({ loading: false, items: [], error: e?.response?.data?.detail || bi("Gagal memuat daftar promo", "Failed to load the promo list", lang) });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => { load(); }, [load]);

  const { loading, error, items } = state;

  if (loading) {
    return (
      <div className="mt-3 flex items-center gap-2 text-[12px] text-muted-foreground" data-testid={`${testId}-loading`}>
        <Loader2 size={13} className="animate-spin" /> {bi("Memeriksa promo yang bisa dipakai…", "Checking applicable promos…", lang)}
      </div>
    );
  }
  if (error) {
    return (
      <div className="mt-3 text-[12px] text-muted-foreground" data-testid={`${testId}-error`}>
        {error}{" "}
        <button type="button" onClick={load} className="font-semibold text-primary underline-offset-2 hover:underline" data-testid={`${testId}-retry`}>
          {bi("Coba lagi", "Try again", lang)}
        </button>
      </div>
    );
  }
  if (!items.length) {
    return (
      <p className="mt-3 text-[12px] text-muted-foreground" data-testid={`${testId}-empty`}>
        {bi("Belum ada promo aktif untuk pesanan ini. Punya kode dari admin? Masukkan di kolom atas.", "No active promos for this booking. Have a code from admin? Enter it in the field above.", lang)}
      </p>
    );
  }

  return (
    <div className="mt-3" data-testid={testId}>
      <p className="flex items-center gap-1.5 text-[12px] font-semibold text-foreground/80">
        <TicketPercent size={13} className="text-primary" /> {bi("Promo yang tersedia", "Available promos", lang)}
      </p>
      <ul className="mt-2 space-y-2">
        {items.map((p) => {
          const active = appliedCode && appliedCode === p.code;
          return (
            <li key={p.code}
              className={`rounded-xl border px-3 py-2.5 ${p.eligible ? "border-primary/35 bg-primary/[0.04]" : "border-border bg-secondary/40"}`}
              data-testid={`${testId}-item-${p.code}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-1.5 text-[13px] font-semibold text-foreground">
                    {p.eligible ? <Tag size={13} className="shrink-0 text-primary" />
                      : <Lock size={13} className="shrink-0 text-muted-foreground" />}
                    <span className="truncate">{p.title || p.code}</span>
                  </p>
                  <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                    {bi("Kode", "Code", lang)} <span className="font-mono font-semibold">{p.code}</span>
                    {p.terms?.length ? ` · ${p.terms.join(" · ")}` : ""}
                  </p>
                  {p.eligible ? (
                    <p className="mt-1 text-[12px] font-semibold text-primary tabular-nums" data-testid={`${testId}-save-${p.code}`}>
                      {bi("Hemat", "Save", lang)} {formatCurrency(p.discount)}
                    </p>
                  ) : (
                    <p className="mt-1 text-[11.5px] text-muted-foreground" data-testid={`${testId}-reason-${p.code}`}>
                      {p.reason}
                    </p>
                  )}
                </div>
                {p.eligible ? (
                  <button type="button" disabled={applying || active}
                    onClick={() => onApply(p.code)}
                    data-testid={`${testId}-use-${p.code}`}
                    className="shrink-0 rounded-lg border border-primary/40 bg-card px-3 py-1.5 text-[12px] font-semibold text-primary transition hover:-translate-y-0.5 disabled:opacity-50">
                    {active ? bi("Terpakai", "Applied", lang) : applying ? <Loader2 size={12} className="animate-spin" /> : bi("Pakai", "Apply", lang)}
                  </button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
