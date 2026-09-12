"""services/landing_templates.py — template landing page per SEGMEN IKLAN (armada & destinasi).

Mengapa dua segmen: iklan bisnis ini punya dua niat pembeli yang berbeda.
  * **armada**    — orang mencari UNIT (Hiace/Elf/Bus): yang menjual adalah kondisi unit,
                    kapasitas, fasilitas, harga per hari, dan kepastian sopir.
  * **destinasi** — orang mencari PENGALAMAN (Bromo/Bali/Dieng): yang menjual adalah itinerary,
                    foto tempat, durasi, dan paket harga per orang.

Setiap template sudah menyertakan blok konversi (hero pencarian / formulir / tombol WhatsApp)
supaya halaman langsung layak dipakai sebagai tujuan iklan (aturan INV-LP-01).

KONTRAK (INV-LP-02): props di sini WAJIB memakai nama kanonik dari `landing_blocks.BLOCK_TYPES`.
Sebelumnya template mengirim `success_text`/`deadline`/`cta` pada blok yang skemanya memakai
nama lain, sehingga isinya dibuang senyap saat validasi — halaman terlihat "kehilangan" tombol
atau tenggat tanpa pesan error. Guardrail `verify_landing_contract.py` sekarang menolak keadaan itu.
"""
from datetime import datetime, timedelta, timezone

from core_utils import new_id


def _blk(btype, props, **extra):
    return {"id": new_id("blk"), "type": btype, "hidden": False, "device": "all",
            "props": props, **extra}


def _deadline(days=7):
    """Tenggat contoh yang selalu masih di depan supaya blok hitung mundur langsung hidup."""
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")


def _search_hero(title, subtitle, tabs, chips, fields, note, cta_label, cta_target="/quotation"):
    return _blk("search_hero", {
        "eyebrow": "RAHAZA TRAVEL", "title": title, "subtitle": subtitle,
        "media": {"src": "", "alt": title, "kind": "image"}, "overlay": 45,
        "tabs": tabs, "active_tab": 0, "chips": chips, "fields": fields,
        "search_label": "Cari Sekarang", "note": note,
        "cta": {"label": cta_label, "kind": "internal", "target": cta_target,
                "style": "primary", "keep_attribution": True},
    })


def _hero_media(eyebrow, title, subtitle, ctas, align="left", overlay=50):
    return _blk("hero_media", {
        "eyebrow": eyebrow, "title": title, "subtitle": subtitle,
        "media": {"src": "", "alt": title, "kind": "image"},
        "overlay": overlay, "align": align, "ctas": ctas,
    })


FLEET_FIELDS = [
    {"type": "select", "name": "vehicle_type", "label": "Jenis unit", "icon": "bus",
     "placeholder": "Pilih unit", "options": ["Hiace Premio", "Hiace Commuter", "Elf Long", "Bus Medium", "Bus Big"]},
    {"type": "daterange", "name": "dates", "label": "Tanggal pakai", "icon": "calendar",
     "placeholder": "Mulai - selesai"},
    {"type": "number", "name": "pax", "label": "Jumlah orang", "icon": "users", "placeholder": "mis. 12"},
]
DEST_FIELDS = [
    {"type": "text", "name": "destination", "label": "Tujuan wisata", "icon": "map-pin",
     "placeholder": "Bromo, Bali, Dieng…"},
    {"type": "daterange", "name": "dates", "label": "Tanggal berangkat", "icon": "calendar",
     "placeholder": "Mulai - selesai"},
    {"type": "number", "name": "pax", "label": "Jumlah peserta", "icon": "users", "placeholder": "mis. 20"},
]
AIRPORT_FIELDS = [
    {"type": "text", "name": "origin", "label": "Titik jemput", "icon": "map-pin",
     "placeholder": "Hotel / alamat"},
    {"type": "select", "name": "destination", "label": "Bandara", "icon": "plane",
     "placeholder": "Pilih bandara", "options": ["Soekarno-Hatta (CGK)", "Halim (HLP)", "Juanda (SUB)",
                                                 "Ngurah Rai (DPS)", "Yogyakarta (YIA)", "Kertajati (KJT)"]},
    {"type": "date", "name": "start", "label": "Tanggal & jam", "icon": "calendar",
     "placeholder": "Kapan dijemput?"},
]
TABS = [
    {"label": "Sewa Armada", "icon": "bus", "target": "/fleet", "badge": ""},
    {"label": "Paket Wisata", "icon": "map", "target": "/destinations", "badge": "Baru"},
    {"label": "Antar Bandara", "icon": "plane", "target": "/booking", "badge": ""},
    {"label": "Rombongan", "icon": "users", "target": "/quotation", "badge": ""},
]


def _value_props(items, title="Kenapa memilih kami"):
    return _blk("value_props", {"title": title, "items": items})


def _lead_form(title, subtitle, fields=None, submit_label="Kirim Permintaan"):
    return _blk("lead_form", {
        "title": title, "subtitle": subtitle,
        "fields": fields or ["name", "phone", "destination", "start", "pax", "message"],
        "submit_label": submit_label,
        "consent_text": "Saya setuju dihubungi tim RahazaTrans via WhatsApp/telepon.",
        "require_consent": True,
        "success_text": "Terima kasih! Penawaran dikirim maksimal 30 menit pada jam kerja."})


def _wa_cta(text, title="Tanya cepat via WhatsApp", label="Chat WhatsApp"):
    return _blk("wa_cta", {"title": title, "text": text,
                           "cta": {"label": label, "kind": "whatsapp", "target": "",
                                   "message": text, "style": "primary", "keep_attribution": True}})


def _faq(items, title="Pertanyaan yang sering diajukan"):
    return _blk("faq", {"title": title, "items": items})


def _cta_band(title, text, label="Pesan Sekarang", target="/booking", tone="dark"):
    return _blk("cta_band", {"title": title, "text": text, "tone": tone,
                             "ctas": [{"label": label, "kind": "internal", "target": target,
                                       "style": "primary", "keep_attribution": True}]})


def _trust(labels, title=""):
    return _blk("trust_badges", {"title": title,
                                 "items": [{"label": s, "icon": "shield"} for s in labels]})


TEMPLATES = {
    # ----------------------------------------------------------------- SEGMEN ARMADA
    "armada-konversi": {
        "segment": "armada",
        "name": "Armada · Fokus Konversi",
        "description": "Hero pencarian unit + keunggulan + daftar armada + formulir penawaran. "
                       "Paling cocok untuk iklan pencarian unit (Hiace/Elf/Bus).",
        "highlights": ["Hero pencarian", "Daftar armada", "Estimasi biaya", "Formulir lead"],
        "theme": {"preset": "biru-laut", "button_shape": "pill"},
        "blocks": lambda: [
            _search_hero("Sewa Hiace, Elf & Bus + Driver",
                         "Unit terawat, sopir berpengalaman, harga transparan tanpa biaya tersembunyi.",
                         TABS, ["Hiace Premio", "Elf Long", "Bus Medium", "Lepas kunci"],
                         FLEET_FIELDS, "Gratis konsultasi rute & estimasi biaya.",
                         "Minta Penawaran"),
            _value_props([
                {"icon": "shield", "title": "Unit terawat & berasuransi", "text": "Servis berkala, cek harian sebelum jalan."},
                {"icon": "user-check", "title": "Sopir berpengalaman", "text": "Hafal rute wisata, ramah, tepat waktu."},
                {"icon": "receipt", "title": "Harga transparan", "text": "Rincian tertulis: sewa, sopir, BBM, tol, parkir."},
                {"icon": "clock", "title": "Respons cepat", "text": "Penawaran dikirim ≤30 menit di jam kerja."},
            ]),
            _blk("fleet_grid", {"title": "Pilihan armada", "subtitle": "Kapasitas 7–59 kursi",
                                "limit": 6, "show_price": True, "vehicle_type": ""}),
            _blk("price_estimator", {"title": "Hitung estimasi biaya",
                                     "subtitle": "Masukkan rute & durasi untuk perkiraan cepat.",
                                     "default_pax": 12}),
            _lead_form("Minta penawaran armada", "Isi sebentar, tim kami hubungi Anda."),
            _blk("testimonials", {"title": "Kata pelanggan", "limit": 3}),
            _faq([{"q": "Apakah harga termasuk sopir & BBM?",
                   "a": "Ya, paket standar sudah termasuk sopir dan BBM untuk rute yang disepakati."},
                  {"q": "Berapa DP-nya?", "a": "DP 30% untuk mengunci unit dan tanggal."},
                  {"q": "Bisa lepas kunci?", "a": "Untuk unit tertentu bisa, dengan syarat jaminan."}]),
            _wa_cta("Halo, saya mau tanya ketersediaan unit."),
        ],
    },
    "armada-cepat": {
        "segment": "armada",
        "name": "Armada · Klik-ke-WhatsApp",
        "description": "Ringkas untuk iklan Klik-ke-WhatsApp: hero + bukti + tombol WA besar.",
        "highlights": ["Hero pencarian", "Lencana kepercayaan", "Galeri unit", "Tombol WhatsApp"],
        "theme": {"preset": "malam-premium", "button_shape": "rounded"},
        "blocks": lambda: [
            _search_hero("Butuh unit hari ini? Chat sekarang",
                         "Ketersediaan unit real-time. Balas cepat di jam kerja.",
                         TABS[:2], ["Hiace", "Elf", "Bus"], FLEET_FIELDS[:2],
                         "Tanpa biaya tersembunyi.", "Chat WhatsApp"),
            _trust(["500+ trip selesai", "Armada berasuransi", "Sopir tersertifikasi"],
                   title="Dipercaya rombongan sekolah, kantor & keluarga"),
            _blk("gallery", {"title": "Kondisi unit terkini", "items": [], "columns": 4}),
            _wa_cta("Halo, saya butuh unit untuk tanggal "),
            _lead_form("Atau tinggalkan nomor Anda", "Kami hubungi balik.",
                       fields=["name", "phone", "message"], submit_label="Hubungi Saya"),
        ],
    },
    "armada-bandara": {
        "segment": "armada",
        "name": "Armada · Antar-Jemput Bandara",
        "description": "Untuk iklan transfer bandara: hero jemput, jaminan tepat waktu, "
                       "estimasi tarif, dan formulir singkat.",
        "highlights": ["Hero bandara", "Rute tarif flat", "Estimasi tarif", "Formulir singkat"],
        "theme": {"preset": "biru-laut", "button_shape": "rounded"},
        "blocks": lambda: [
            _search_hero("Antar-Jemput Bandara Tepat Waktu",
                         "Sopir memantau jadwal penerbangan Anda. Tunggu gratis 60 menit.",
                         TABS[2:], ["CGK", "Juanda", "YIA", "Ngurah Rai"], AIRPORT_FIELDS,
                         "Harga tetap, tanpa biaya parkir tersembunyi.", "Pesan Penjemputan",
                         cta_target="/booking"),
            _value_props([
                {"icon": "clock", "title": "Pantau jadwal pesawat", "text": "Delay? Sopir menyesuaikan tanpa biaya tambahan."},
                {"icon": "receipt", "title": "Harga tetap", "text": "Tol & parkir sudah termasuk, tidak ada kejutan."},
                {"icon": "user-check", "title": "Sopir berjas", "text": "Menunggu dengan papan nama di pintu kedatangan."},
            ], title="Kenapa transfer bandara kami tenang"),
            _blk("route_grid", {"title": "Rute & tarif tetap", "subtitle":
                                "Harga flat per rute sekali jalan — sudah termasuk driver, tol & parkir.",
                                "ids": [], "limit": 6, "show_price": True,
                                "cta": {"label": "Lihat semua rute", "kind": "internal",
                                        "target": "/booking", "style": "secondary",
                                        "keep_attribution": True}}),
            _blk("fleet_grid", {"title": "Unit untuk transfer", "subtitle": "Bagasi lega untuk keluarga",
                                "limit": 4, "show_price": True, "vehicle_type": "hiace"}),
            _blk("price_estimator", {"title": "Perkiraan tarif penjemputan",
                                     "subtitle": "Hitung dari titik jemput ke bandara.",
                                     "default_pax": 4}),
            _lead_form("Pesan penjemputan", "Isi detail penerbangan, kami konfirmasi via WhatsApp.",
                       fields=["name", "phone", "origin", "destination", "start", "pax"],
                       submit_label="Pesan Sekarang"),
            _cta_band("Terbang besok pagi?", "Kunci penjemputan sekarang, sopir standby 30 menit lebih awal.",
                      label="Pesan Penjemputan", target="/booking"),
            _faq([{"q": "Bagaimana kalau pesawat delay?",
                   "a": "Sopir memantau nomor penerbangan Anda dan menyesuaikan tanpa biaya tambahan."},
                  {"q": "Apakah bisa dini hari?", "a": "Bisa, layanan tersedia 24 jam dengan pemesanan minimal 6 jam sebelumnya."}]),
        ],
    },
    "armada-korporat": {
        "segment": "armada",
        "name": "Armada · Kontrak Korporat",
        "description": "Untuk iklan sewa bulanan/kontrak kantor: kredibilitas, SLA, dan "
                       "formulir permintaan proposal.",
        "highlights": ["Hero korporat", "SLA tertulis", "Lencana kepercayaan", "Minta proposal"],
        "theme": {"preset": "malam-premium", "button_shape": "rounded"},
        "blocks": lambda: [
            _hero_media("SEWA KORPORAT", "Armada Kantor Tanpa Repot Operasional",
                        "Kontrak bulanan dengan unit pengganti, sopir tetap, dan laporan pemakaian bulanan.",
                        [{"label": "Minta Proposal", "kind": "internal", "target": "/quotation",
                          "style": "primary", "keep_attribution": True},
                         {"label": "Lihat Armada", "kind": "internal", "target": "/fleet",
                          "style": "secondary", "keep_attribution": True}]),
            _trust(["Faktur & PPN", "Unit pengganti < 3 jam", "Laporan pemakaian bulanan",
                    "Sopir tetap terlatih"], title="Standar layanan korporat"),
            _value_props([
                {"icon": "receipt", "title": "Administrasi rapi", "text": "Faktur, kontrak, dan laporan bulanan siap audit."},
                {"icon": "shield", "title": "Jaminan ketersediaan", "text": "Unit pengganti bila terjadi kendala teknis."},
                {"icon": "user-check", "title": "Sopir tetap", "text": "Satu sopir dedicated, kenal rute & kebiasaan tim Anda."},
                {"icon": "clock", "title": "Respons SLA", "text": "Keluhan operasional ditangani ≤3 jam kerja."},
            ], title="Yang perusahaan dapatkan"),
            _blk("fleet_grid", {"title": "Unit untuk kontrak", "subtitle": "Sedan, Hiace, hingga bus karyawan",
                                "limit": 6, "show_price": False, "vehicle_type": ""}),
            _blk("rich_text", {"title": "Cakupan kontrak", "width": "narrow", "html":
                               "<ul><li>Sewa unit + sopir (opsi lepas kunci untuk unit tertentu)</li>"
                               "<li>Servis berkala, pajak, dan asuransi ditanggung penyedia</li>"
                               "<li>Penggantian unit maksimal 3 jam kerja</li>"
                               "<li>Laporan pemakaian & BBM tiap bulan</li></ul>"}),
            _lead_form("Minta proposal korporat", "Sebutkan kebutuhan unit & durasi kontrak.",
                       fields=["name", "phone", "email", "vehicle_type", "start", "message"],
                       submit_label="Minta Proposal"),
            _faq([{"q": "Minimal durasi kontrak?", "a": "Mulai 1 bulan, dengan harga lebih baik untuk 6–12 bulan."},
                  {"q": "Apakah bisa faktur pajak?", "a": "Bisa. Kami terbitkan faktur resmi sesuai kebutuhan keuangan Anda."}]),
        ],
    },
    # ----------------------------------------------------------------- SEGMEN DESTINASI
    "destinasi-paket": {
        "segment": "destinasi",
        "name": "Destinasi · Paket Wisata",
        "description": "Hero pencarian tujuan + galeri destinasi + itinerary + formulir peserta. "
                       "Cocok untuk iklan paket wisata per destinasi.",
        "highlights": ["Hero pencarian", "Daftar destinasi", "Galeri & video", "Formulir peserta"],
        "theme": {"preset": "hijau-tropis", "button_shape": "pill"},
        "blocks": lambda: [
            _search_hero("Paket Wisata + Transport Lengkap",
                         "Itinerary siap pakai, tinggal pilih tanggal. Cocok untuk rombongan.",
                         TABS, ["Bromo", "Bali", "Dieng", "Yogyakarta"], DEST_FIELDS,
                         "Harga per orang, minimal 10 peserta.", "Minta Itinerary"),
            _blk("destination_grid", {"title": "Destinasi favorit",
                                      "subtitle": "Pilihan rute yang paling sering diminta",
                                      "limit": 6, "show_price": True, "region": ""}),
            _value_props([
                {"icon": "map", "title": "Itinerary jelas", "text": "Jam per jam, tanpa rute membingungkan."},
                {"icon": "users", "title": "Ramah rombongan", "text": "Sekolah, kantor, keluarga besar."},
                {"icon": "camera", "title": "Spot foto terbaik", "text": "Sopir tahu waktu terbaik tiap spot."},
            ]),
            _blk("gallery", {"title": "Suasana perjalanan", "items": [], "columns": 4}),
            _blk("video", {"title": "Cuplikan perjalanan", "autoplay": False, "loop": False,
                           "media": {"kind": "video", "src": "", "poster": "", "embed_url": ""}}),
            _lead_form("Minta itinerary & harga", "Sebutkan tujuan dan jumlah peserta."),
            _faq([{"q": "Apakah tiket masuk termasuk?", "a": "Bisa termasuk atau terpisah, sesuai paket yang dipilih."},
                  {"q": "Bisa custom rute?", "a": "Bisa. Sampaikan preferensi Anda, kami susun ulang itinerary."}]),
            _wa_cta("Halo, saya mau tanya paket wisata ke "),
        ],
    },
    "destinasi-promo": {
        "segment": "destinasi",
        "name": "Destinasi · Promo Terbatas",
        "description": "Untuk iklan promo musiman: hitung mundur + penawaran + formulir singkat.",
        "highlights": ["Hitung mundur", "Banner CTA", "Pilihan promo", "Formulir singkat"],
        "theme": {"preset": "merah-berani", "button_shape": "pill"},
        "blocks": lambda: [
            _search_hero("Promo Libur Sekolah — Kuota Terbatas",
                         "Harga khusus rombongan untuk keberangkatan bulan ini.",
                         TABS[1:3], ["Bromo 2H1M", "Bali 4H3M"], DEST_FIELDS[:2],
                         "Kuota unit terbatas per tanggal.", "Ambil Promo"),
            _blk("countdown", {"title": "Promo berakhir dalam", "deadline": _deadline(7),
                               "subtitle": "Setelah ini harga kembali normal."}),
            _cta_band("Kunci tanggal Anda sekarang", "DP 30% untuk mengamankan unit & harga promo.",
                      label="Pesan Sekarang", target="/booking"),
            _blk("destination_grid", {"title": "Pilihan promo", "subtitle": "", "limit": 4,
                                      "show_price": True, "region": ""}),
            _lead_form("Tanya ketersediaan tanggal", "Kami balas cepat.",
                       fields=["name", "phone", "destination", "start", "pax"],
                       submit_label="Cek Ketersediaan"),
        ],
    },
    "destinasi-sekolah": {
        "segment": "destinasi",
        "name": "Destinasi · Study Tour Sekolah",
        "description": "Untuk iklan rombongan sekolah: keamanan, izin & pendampingan, "
                       "harga per siswa, dan formulir panitia.",
        "highlights": ["Hero rombongan", "Jaminan keamanan", "Galeri kegiatan", "Formulir panitia"],
        "theme": {"preset": "hijau-tropis", "button_shape": "rounded"},
        "blocks": lambda: [
            _hero_media("STUDY TOUR & OUTING CLASS", "Perjalanan Sekolah yang Aman & Tertib",
                        "Bus laik jalan, sopir berpengalaman rombongan, dan pendamping perjalanan.",
                        [{"label": "Minta Penawaran Sekolah", "kind": "internal", "target": "/quotation",
                          "style": "primary", "keep_attribution": True}], align="center", overlay=55),
            _trust(["Bus laik jalan (KIR aktif)", "Sopir + co-driver", "Pendamping perjalanan",
                    "Asuransi peserta"], title="Standar keselamatan rombongan sekolah"),
            _value_props([
                {"icon": "shield", "title": "Keselamatan utama", "text": "Cek unit sebelum jalan, dua sopir untuk rute jauh."},
                {"icon": "users", "title": "Kapasitas besar", "text": "Bus 45–59 kursi, cukup untuk satu angkatan."},
                {"icon": "map", "title": "Itinerary edukatif", "text": "Destinasi belajar + rekreasi dalam satu rute."},
                {"icon": "receipt", "title": "Harga per siswa", "text": "Rincian jelas untuk proposal ke orang tua."},
            ], title="Kenapa panitia memilih kami"),
            _blk("destination_grid", {"title": "Rute study tour populer", "subtitle": "Bisa disesuaikan kurikulum",
                                      "limit": 6, "show_price": True, "region": ""}),
            _blk("gallery", {"title": "Dokumentasi kegiatan", "items": [], "columns": 4}),
            _lead_form("Minta penawaran rombongan sekolah",
                       "Isi jumlah siswa & tanggal rencana, kami kirim rincian per siswa.",
                       fields=["name", "phone", "email", "destination", "start", "pax", "message"],
                       submit_label="Minta Penawaran"),
            _faq([{"q": "Berapa pendamping yang disediakan?",
                   "a": "Satu pendamping perjalanan per bus, ditambah co-driver untuk rute di atas 8 jam."},
                  {"q": "Apakah bisa termin pembayaran?",
                   "a": "Bisa. Umumnya DP 30%, pelunasan 3 hari sebelum keberangkatan."}]),
            _wa_cta("Halo, saya panitia study tour sekolah. Mau tanya penawaran untuk ",
                    title="Panitia butuh jawaban cepat?"),
        ],
    },
    "destinasi-keluarga": {
        "segment": "destinasi",
        "name": "Destinasi · Liburan Keluarga",
        "description": "Untuk iklan liburan keluarga: nyaman untuk anak & orang tua, "
                       "testimoni, estimasi biaya, dan formulir santai.",
        "highlights": ["Hero keluarga", "Testimoni", "Estimasi biaya", "Formulir santai"],
        "theme": {"preset": "biru-laut", "button_shape": "pill"},
        "blocks": lambda: [
            _hero_media("LIBURAN KELUARGA", "Satu Mobil, Semua Ikut Senang",
                        "Sopir sabar, AC dingin, kursi lega untuk anak dan orang tua.",
                        [{"label": "Rencanakan Liburan", "kind": "internal", "target": "/quotation",
                          "style": "primary", "keep_attribution": True},
                         {"label": "Lihat Destinasi", "kind": "internal", "target": "/destinations",
                          "style": "secondary", "keep_attribution": True}]),
            _value_props([
                {"icon": "users", "title": "Nyaman untuk anak", "text": "Kursi lega, berhenti sesuai kebutuhan keluarga."},
                {"icon": "user-check", "title": "Sopir sabar", "text": "Terbiasa membawa keluarga dengan balita & lansia."},
                {"icon": "camera", "title": "Spot foto keluarga", "text": "Sopir bantu pilih waktu & titik terbaik."},
            ], title="Liburan tanpa drama"),
            _blk("destination_grid", {"title": "Ide liburan keluarga", "subtitle": "Dekat, nyaman, ramah anak",
                                      "limit": 6, "show_price": True, "region": ""}),
            _blk("testimonials", {"title": "Cerita keluarga lain", "limit": 3}),
            _blk("gallery", {"title": "Momen perjalanan", "items": [], "columns": 3}),
            _blk("price_estimator", {"title": "Kira-kira habis berapa?",
                                     "subtitle": "Hitung cepat sebelum bertanya.", "default_pax": 6}),
            _lead_form("Rencanakan bareng kami", "Ceritakan rencana Anda, kami susun pilihannya.",
                       fields=["name", "phone", "destination", "start", "end", "pax", "message"],
                       submit_label="Kirim Rencana"),
            _wa_cta("Halo, saya mau rencanakan liburan keluarga ke "),
        ],
    },
}


def list_templates():
    return [{"key": key, "name": t["name"], "segment": t["segment"],
             "description": t["description"], "blocks": len(t["blocks"]()),
             "highlights": t.get("highlights", []), "theme": t["theme"]}
            for key, t in TEMPLATES.items()]


def build(template_key: str):
    """-> (blocks, theme, segment). Template tak dikenal -> template armada default."""
    t = TEMPLATES.get(template_key) or TEMPLATES["armada-konversi"]
    return t["blocks"](), dict(t["theme"]), t["segment"]
