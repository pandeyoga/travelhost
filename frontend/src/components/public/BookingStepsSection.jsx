import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, CalendarSearch, BadgeCheck, Upload, ShieldCheck, Clock3 } from "lucide-react";
import Reveal from "@/components/public/Reveal";
import SectionHeading from "@/components/public/SectionHeading";
import ResumeBookingChip from "@/components/public/ResumeBookingChip";
import { getBookingConfig } from "@/services/bookingApi";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

/**
 * BookingStepsSection — "Pesan online dalam 3 langkah" (permintaan user 2026-08-12).
 *
 * Kenapa ada di BERANDA: sesudah navbar dirapikan, `Pesan Online` jadi SATU tombol aksi.
 * Tamu yang belum pernah memesan online perlu tahu apa yang akan terjadi SEBELUM masuk wizard —
 * terutama bahwa unit ditahan sementara dan wajib DP. Menjelaskannya di beranda menurunkan
 * jumlah pesanan yang dibuat lalu ditinggalkan (hold hangus = unit terkunci sia-sia).
 *
 * Angka DP & lama hold TIDAK di-hardcode: diambil dari `/public/booking/config` (sumber yang
 * sama dengan mesin harga & Pengaturan Alur Booking), supaya halaman ini tidak pernah
 * menjanjikan persentase yang berbeda dari yang ditagihkan.
 */
const stepsFor = (lang) => [
  {
    icon: CalendarSearch,
    tag: bi("Langkah 1", "Step 1", lang),
    title: bi("Pilih tanggal & unit", "Pick dates & vehicle", lang),
    desc: bi("Masukkan tanggal, jumlah orang, dan layanan. Hanya unit yang benar-benar kosong pada tanggal itu yang ditampilkan — lengkap dengan harganya.", "Enter your dates, group size and service. Only vehicles genuinely free on those dates are shown — with their prices.", lang),
  },
  {
    icon: BadgeCheck,
    tag: bi("Langkah 2", "Step 2", lang),
    title: bi("Isi data & dapat kode booking", "Fill in details & get a booking code", lang),
    desc: bi("Cukup nama & nomor WhatsApp, tanpa membuat akun. Anda langsung menerima kode booking dan unit ditahan sementara untuk Anda.", "Just your name & WhatsApp number, no account needed. You instantly receive a booking code and the vehicle is held for you.", lang),
  },
  {
    icon: Upload,
    tag: bi("Langkah 3", "Step 3", lang),
    title: bi("Transfer DP & unggah bukti", "Pay the deposit & upload proof", lang),
    desc: bi("Transfer DP ke rekening resmi, lalu unggah fotonya di halaman status. Admin memverifikasi dan pesanan Anda berubah menjadi terkonfirmasi.", "Transfer the deposit to our official account, then upload the photo on the status page. Our admin verifies it and your booking becomes confirmed.", lang),
  },
];

export default function BookingStepsSection() {
  const lang = useLangValue();
  const STEPS = stepsFor(lang);
  const [cfg, setCfg] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    getBookingConfig()
      .then((d) => { if (alive) setCfg(d); })
      .catch(() => {})
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  const dp = Number(cfg?.dp_percent) || 0;
  const holdHours = Number(cfg?.hold_hours) || 0;

  return (
    <section className="relative overflow-hidden bg-secondary/40 py-16 md:py-24" data-testid="home-booking-steps">
      <div className="glow-orb h-72 w-72 right-[-40px] top-6" style={{ background: "hsla(var(--ring) / 0.14)" }} aria-hidden="true" />
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <SectionHeading
          eyebrow={bi("Pesan Online", "Book Online", lang)}
          title={bi("Pesan online dalam 3 langkah", "Book online in 3 steps", lang)}
          subtitle={bi("Tanpa telepon, tanpa akun. Ketersediaan dan harga dihitung langsung oleh sistem kami — yang Anda lihat adalah yang Anda bayar.", "No phone calls, no account. Availability and pricing are computed by our system — what you see is what you pay.", lang)}
        />

        <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <Reveal key={s.tag} delay={i * 0.08}>
              <div className="card-premium h-full rounded-2xl p-7" data-testid={`home-booking-step-${i + 1}`}>
                <div className="flex items-center justify-between">
                  <span className="icon-chip h-12 w-12"><s.icon className="h-5 w-5" strokeWidth={1.8} /></span>
                  <span className="font-fraunces text-3xl text-muted-foreground/35">{i + 1}</span>
                </div>
                <span className="mt-5 inline-block rounded-full bg-secondary px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-wide text-secondary-foreground">{s.tag}</span>
                <h3 className="mt-3 font-fraunces text-xl text-foreground">{s.title}</h3>
                <p className="mt-2 text-[13.5px] leading-relaxed text-muted-foreground">{s.desc}</p>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal delay={0.1}>
          <div className="mt-8 flex flex-col gap-5 rounded-2xl border border-border bg-card px-6 py-6 md:flex-row md:items-center md:justify-between">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-muted-foreground">
                {/* LOADING: syarat DP & lama hold datang dari server (Pengaturan Alur Booking),
                    jadi jangan menampilkan angka apa pun sebelum jawabannya tiba.
                    KOSONG/GAGAL: katakan terus terang, jangan diam-diam menghilangkan syarat. */}
                {loading ? (
                  <>
                    <span className="h-6 w-44 animate-pulse rounded-full bg-muted" data-testid="home-booking-terms-skeleton" />
                    <span className="h-6 w-36 animate-pulse rounded-full bg-muted" />
                  </>
                ) : dp || holdHours ? (
                  <>
                    {dp ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1 font-semibold text-secondary-foreground" data-testid="home-booking-dp">
                        <ShieldCheck size={13} /> {bi(`DP ${dp}% untuk mengunci unit`, `${dp}% deposit to lock the vehicle`, lang)}
                      </span>
                    ) : null}
                    {holdHours ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1 font-semibold text-secondary-foreground" data-testid="home-booking-hold">
                        <Clock3 size={13} /> {bi(`Unit ditahan ${holdHours} jam`, `Vehicle held for ${holdHours} hours`, lang)}
                      </span>
                    ) : null}
                  </>
                ) : (
                  <span data-testid="home-booking-terms-empty">{bi("Belum ada info DP yang bisa dimuat — rinciannya muncul saat Anda membuat pesanan.", "Deposit details aren't available yet — they'll appear when you create a booking.", lang)}</span>
                )}
              </div>
              <p className="text-[13px] text-muted-foreground">
                {bi("Sudah pesan dan baru transfer? Buka", "Already booked and just transferred? Open", lang)}{" "}
                <Link to="/booking/status" data-testid="home-booking-status-link" className="font-semibold text-primary underline-offset-2 hover:underline">{bi("Cek Pesanan", "Track Booking", lang)}</Link>{" "}
                {bi("untuk mengunggah bukti transfer.", "to upload your transfer proof.", lang)}
              </p>
              <ResumeBookingChip variant="block" className="mt-1" />
            </div>
            <Link to="/booking" data-testid="home-cta-booking"
              className="cta-shine inline-flex shrink-0 items-center justify-center gap-2 rounded-full px-6 py-3.5 text-[14px] font-semibold text-primary-foreground shadow-[var(--shadow-lift)] transition hover:-translate-y-0.5"
              style={{ background: "var(--gradient-cta)" }}>
              {bi("Mulai Pesan Online", "Start booking online", lang)} <ArrowRight size={16} />
            </Link>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
