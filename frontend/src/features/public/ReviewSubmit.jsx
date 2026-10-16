import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Loader2, Star, CheckCircle2, ShieldCheck, ArrowLeft } from "lucide-react";
import apiClient from "@/services/apiClient";
import { useResource } from "@/hooks/useResource";
import { useLangValue } from "@/hooks/useLang";
import { t } from "@/lib/i18n";
import useSEO from "@/hooks/useSEO";

// ReviewSubmit — CMS-07: halaman ulasan pelanggan (dibuka dari tautan WhatsApp).
// Token satu pesanan: tidak ada login, tidak ada data sensitif yang ditampilkan.
export default function ReviewSubmit() {
  const { token } = useParams();
  const lang = useLangValue();
  const { data: ctx, loading, error } = useResource(`/public/reviews/${token}`);
  const [rating, setRating] = useState(5);
  const [hover, setHover] = useState(0);
  const [quote, setQuote] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [consent, setConsent] = useState(true);
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);

  useSEO({
    title: t("review.title", lang),
    description: lang === "en"
      ? "Tell us about your trip with RahazaTrans."
      : "Ceritakan pengalaman perjalanan Anda bersama RahazaTrans.",
  });

  const submit = async () => {
    if (quote.trim().length < 10) {
      toast.error(lang === "en" ? "Please write at least 10 characters." : "Mohon tulis ulasan minimal 10 karakter.");
      return;
    }
    if (!consent) {
      toast.error(lang === "en" ? "Consent is required to publish." : "Persetujuan diperlukan agar ulasan bisa ditampilkan.");
      return;
    }
    setSending(true);
    try {
      await apiClient.post(`/public/reviews/${token}`, {
        rating, quote: quote.trim(), name: name.trim(), role: role.trim(), consent,
      });
      setDone(true);
      toast.success(t("review.thanks", lang));
    } catch (e) {
      toast.error(e?.response?.data?.detail || (lang === "en" ? "Failed to send review" : "Gagal mengirim ulasan"));
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center pt-24 text-muted-foreground" data-testid="review-loading">
        <Loader2 className="mr-2 animate-spin" /> {t("common.loading", lang)}
      </div>
    );
  }

  if (error || !ctx) {
    return (
      <div className="mx-auto flex min-h-[70vh] max-w-lg flex-col items-center justify-center gap-4 px-5 pt-24 text-center" data-testid="review-invalid">
        <ShieldCheck size={34} className="text-muted-foreground" />
        <h1 className="font-fraunces text-2xl text-foreground">
          {lang === "en" ? "This review link is no longer valid" : "Tautan ulasan ini tidak berlaku"}
        </h1>
        <p className="text-[14px] text-muted-foreground">{error || ""}</p>
        <Link to="/" className="rounded-full bg-primary px-5 py-2.5 text-[13px] font-semibold text-primary-foreground" data-testid="review-home">
          <ArrowLeft size={14} className="mr-1 inline" /> {t("common.back", lang)}
        </Link>
      </div>
    );
  }

  if (done) {
    return (
      <div className="mx-auto flex min-h-[70vh] max-w-lg flex-col items-center justify-center gap-4 px-5 pt-24 text-center" data-testid="review-done">
        <CheckCircle2 size={40} className="text-[#1E8E5A]" />
        <h1 className="font-fraunces text-3xl text-foreground">{t("review.thanks", lang)}</h1>
        <p className="text-[14.5px] leading-relaxed text-muted-foreground">
          {lang === "en"
            ? "Our team moderates every review before it appears on the site — usually within one working day."
            : "Tim kami meninjau setiap ulasan sebelum tampil di situs — biasanya dalam satu hari kerja."}
        </p>
        <Link to="/" className="rounded-full bg-primary px-5 py-2.5 text-[13px] font-semibold text-primary-foreground" data-testid="review-done-home">
          {t("common.back", lang)}
        </Link>
      </div>
    );
  }

  const stars = [1, 2, 3, 4, 5];
  const active = hover || rating;

  return (
    <div className="mx-auto w-full max-w-2xl px-5 pb-20 pt-32" data-testid="review-page">
      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-primary">
        {ctx.booking_code ? `#${ctx.booking_code}` : t("nav.home", lang)}
      </p>
      <h1 className="mt-2 font-fraunces text-3xl leading-tight text-foreground sm:text-4xl">
        {t("review.title", lang)}
      </h1>
      <p className="mt-3 text-[14.5px] leading-relaxed text-muted-foreground">
        {lang === "en"
          ? `Hi ${ctx.customer_name}, your feedback helps other travellers choose with confidence.`
          : `Halo ${ctx.customer_name}, ulasan Anda membantu calon pelanggan lain memilih dengan yakin.`}
        {ctx.route ? ` · ${ctx.route}` : ""}
      </p>

      <div className="mt-8 rounded-2xl border border-border bg-card p-6 shadow-[var(--shadow-lift)]">
        <label className="text-[12.5px] font-semibold text-foreground">{t("review.rating", lang)}</label>
        <div className="mt-2 flex items-center gap-1.5" data-testid="review-stars">
          {stars.map((s) => (
            <button key={s} type="button" onClick={() => setRating(s)}
              onMouseEnter={() => setHover(s)} onMouseLeave={() => setHover(0)}
              aria-label={`${s}`} data-testid={`review-star-${s}`}
              className="rounded-full p-1 transition hover:scale-110">
              <Star size={30} className={s <= active ? "fill-[#F5A524] text-[#F5A524]" : "text-[#C9CAD1]"} />
            </button>
          ))}
          <span className="ml-2 text-[13px] font-semibold tabular-nums text-muted-foreground">{active}/5</span>
        </div>

        <label className="mt-6 block text-[12.5px] font-semibold text-foreground" htmlFor="review-quote">
          {t("review.quote", lang)}
        </label>
        <textarea id="review-quote" rows={5} value={quote} onChange={(e) => setQuote(e.target.value)}
          data-testid="review-quote"
          className="mt-1.5 w-full rounded-xl border border-border bg-background px-3.5 py-2.5 text-[14px] text-foreground outline-none focus:border-primary"
          placeholder={lang === "en"
            ? "The driver was punctual, the van was spotless…"
            : "Sopir tepat waktu, armada bersih, perjalanan nyaman…"} />

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div>
            <label className="block text-[12.5px] font-semibold text-foreground" htmlFor="review-name">{t("review.name", lang)}</label>
            <input id="review-name" value={name} onChange={(e) => setName(e.target.value)}
              data-testid="review-name" placeholder={ctx.customer_name}
              className="mt-1.5 w-full rounded-xl border border-border bg-background px-3.5 py-2.5 text-[14px] text-foreground outline-none focus:border-primary" />
          </div>
          <div>
            <label className="block text-[12.5px] font-semibold text-foreground" htmlFor="review-role">{t("review.role", lang)}</label>
            <input id="review-role" value={role} onChange={(e) => setRole(e.target.value)}
              data-testid="review-role"
              className="mt-1.5 w-full rounded-xl border border-border bg-background px-3.5 py-2.5 text-[14px] text-foreground outline-none focus:border-primary" />
          </div>
        </div>

        <label className="mt-4 flex items-start gap-2.5 text-[12.5px] leading-relaxed text-muted-foreground">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)}
            data-testid="review-consent" className="mt-0.5 h-4 w-4 rounded border-border" />
          {t("review.consent", lang)}
        </label>

        <button type="button" onClick={submit} disabled={sending} data-testid="review-submit"
          className="cta-shine mt-5 flex w-full items-center justify-center gap-2 rounded-full px-5 py-3 text-[14px] font-semibold text-primary-foreground disabled:opacity-60"
          style={{ background: "var(--gradient-cta)" }}>
          {sending ? <Loader2 size={16} className="animate-spin" /> : <Star size={16} />} {t("review.submit", lang)}
        </button>
      </div>
    </div>
  );
}
