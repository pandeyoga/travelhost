"""scripts/import_content.py — Impor konten situs RahazaTrans (foto + copywriting) ke database.

Dipakai untuk mengisi situs publik yang masih kosong setelah deploy (VPS maupun lokal).
Aman dijalankan ULANG (idempoten): foto dikenali dari `import_key`, dokumen destinasi/halaman
di-upsert berdasarkan slug, jadi tidak ada duplikasi.

Yang diimpor (sumber: content_import/assets/):
  * Media Library  → folder "Konten Situs" › Beranda / Galeri Tamu / <Destinasi>
  * Destinasi      → Bandung, Gunung Bromo, Yogyakarta, Pangandaran (hero, galeri, sorotan
                     berfoto, itinerary, rute, FAQ, hotel) — status published & populer.
  * Halaman        → Beranda (hero + section "Galeri Momen Tamu"), hero halaman Destinasi,
                     Armada, Paket, Promo, Blog, Tentang, Kontak, Kalkulator.
  * Testimoni      → 3 testimoni tamu (hanya bila belum ada testimoni non-demo).

Cara pakai (di VPS, dari /opt/travel):
    docker compose -f deploy/docker-compose.yml exec -T backend python /app/scripts/import_content.py
Lokal:
    cd /app && python scripts/import_content.py [--content-dir content_import/assets] [--dry-run]
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from core_utils import new_id, now_iso  # noqa: E402
from services import media_lib as ml  # noqa: E402
from services import media_store as ms  # noqa: E402

ACTOR = {"id": "import-script", "name": "Impor Konten", "email": "import@rahazatrans.local"}

# --------------------------------------------------------------------------- COPYWRITING
DESTINATIONS = [
    {
        "slug": "bromo", "name": "Gunung Bromo", "region": "jawa_timur", "position": 1,
        "hero": "bromo/savanna-bromo.jpg", "card": "home/bromo.jpg",
        "lat": -7.9425, "lng": 112.9530, "best_time": "Mei – September (langit cerah, sunrise maksimal)",
        "intro": "Negeri di atas awan yang tak pernah gagal membuat terdiam. Kami jemput Anda dari Bandung "
                 "atau Surabaya, berangkat malam, dan tiba tepat saat langit Penanjakan mulai memerah.",
        "description": "Sunrise legendaris di Penanjakan, lautan pasir yang berbisik, savana hijau Bukit Teletubbies, "
                       "hingga kesegaran Air Terjun Madakaripura — satu rute, empat lanskap yang berbeda.",
        "highlights": [
            ("Sunrise Penanjakan", "Matahari terbit di antara Bromo, Batok, dan Semeru — momen yang wajib Anda saksikan sekali seumur hidup.", "bromo/savanna-bromo.jpg"),
            ("Pasir Berbisik", "Hamparan lautan pasir vulkanik yang sunyi; berkuda atau naik jeep menuju kaki kawah.", "bromo/pasir-berbisik-bromo.jpg"),
            ("Bukit Teletubbies", "Savana hijau bergelombang yang ikonik, spot foto favorit rombongan.", "bromo/bukit-teletubbies.jpg"),
            ("Air Terjun Madakaripura", "Air terjun tertinggi di Jawa, tersembunyi di ngarai hijau — penutup trip yang menyegarkan.", "bromo/air-terjun-makadaripura.jpg"),
        ],
        "itinerary": [
            ("Hari 1", "Bandung → Probolinggo", "Berangkat sore/malam dengan Hiace Premio, rehat & makan di rest area utama, tiba dini hari di kawasan Cemoro Lawang."),
            ("Hari 2", "Sunrise & Lautan Pasir", "03.00 menuju Penanjakan dengan jeep 4x4, lanjut kawah Bromo, Pasir Berbisik, dan Bukit Teletubbies. Sore bebas & istirahat."),
            ("Hari 3", "Madakaripura → Pulang", "Trekking ringan ke Air Terjun Madakaripura, makan siang, belanja oleh-oleh, perjalanan kembali ke Bandung."),
        ],
        "route": [("Bandung", -6.9147, 107.6098, "Titik kumpul & briefing rute."),
                  ("Yogyakarta", -7.7956, 110.3695, "Rehat & makan tengah perjalanan."),
                  ("Surabaya", -7.2575, 112.7521, "Transit & istirahat driver."),
                  ("Probolinggo", -7.7543, 113.2159, "Gerbang menuju kawasan Bromo."),
                  ("Gunung Bromo", -7.9425, 112.9530, "Tiba menjelang dini hari untuk sunrise.")],
        "faqs": [("Jam berapa berangkat untuk sunrise?", "Dari penginapan ±03.00 dini hari menuju Penanjakan. Driver kami sudah hafal jalurnya."),
                 ("Apakah jeep 4x4 termasuk?", "Jeep lokal wajib untuk masuk lautan pasir. Kami koordinasikan dan masukkan ke penawaran bila diminta."),
                 ("Perlu bawa apa?", "Jaket tebal, sarung tangan, masker debu, dan sepatu nyaman — suhu bisa di bawah 10°C.")],
        "hotels": [("Jiwa Jawa Resort Bromo", 4.5, "Rp 900rb–1,8jt"), ("Lava View Lodge", 4.2, "Rp 700rb–1,2jt")],
    },
    {
        "slug": "yogyakarta", "name": "Yogyakarta", "region": "yogyakarta", "position": 2,
        "hero": "yogyakarta/candi-borobudur.jpg", "card": "home/yogyakarta.jpg",
        "lat": -7.7956, "lng": 110.3695, "best_time": "Sepanjang tahun (favorit April – Oktober)",
        "intro": "Kota yang selalu punya cara untuk membuat rindu. Dari candi warisan dunia sampai gudeg tengah malam, "
                 "Yogyakarta nyaman dijangkau dari Bandung dalam satu perjalanan yang kami rancang tanpa terburu-buru.",
        "description": "Borobudur saat pagi, Prambanan saat senja, Malioboro saat malam, dan deburan Parangtritis sebagai penutup. "
                       "Cocok untuk keluarga, rombongan sekolah, hingga tamu mancanegara.",
        "highlights": [
            ("Candi Borobudur", "Candi Buddha terbesar di dunia; paling magis dikunjungi pagi hari saat kabut masih menggantung.", "yogyakarta/candi-borobudur.jpg"),
            ("Candi Prambanan", "Kompleks candi Hindu termegah di Jawa, indah disapu cahaya senja.", "yogyakarta/candi-prambanan.jpg"),
            ("Malioboro", "Jantung kota: belanja batik, kuliner lesehan, dan andong keliling keraton.", "yogyakarta/malioboro.jpg"),
            ("Pantai Parangtritis", "Pantai selatan yang legendaris — sunset, ATV, dan gumuk pasir Barchan.", "yogyakarta/pantai-parangtritis.jpg"),
        ],
        "itinerary": [
            ("Hari 1", "Bandung → Yogyakarta", "Perjalanan santai via jalur selatan, rehat di Purwokerto, tiba sore, check-in, dan kuliner malam di Malioboro."),
            ("Hari 2", "Candi & Kota", "Borobudur pagi, Prambanan sore, malam bebas di kawasan Tugu/Malioboro."),
            ("Hari 3", "Pantai & Pulang", "Parangtritis pagi, belanja bakpia & batik, perjalanan kembali ke Bandung."),
        ],
        "route": [("Bandung", -6.9147, 107.6098, "Keberangkatan & briefing."),
                  ("Purwokerto", -7.4216, 109.2345, "Rehat & makan di jalur selatan."),
                  ("Magelang", -7.4706, 110.2178, "Mendekati kawasan Borobudur."),
                  ("Yogyakarta", -7.7956, 110.3695, "Tiba di kota budaya, mulai eksplorasi.")],
        "faqs": [("Borobudur dan Prambanan bisa sehari?", "Bisa — Borobudur pagi dan Prambanan sore. Driver kami mengatur waktunya agar tidak terburu-buru."),
                 ("Cocok untuk study tour?", "Sangat cocok. Tersedia Hiace 14 kursi, Elf 19 kursi, dan koordinasi jadwal untuk rombongan sekolah/kampus."),
                 ("Berapa lama dari Bandung?", "Sekitar 8–10 jam tergantung lalu lintas dan titik rehat.")],
        "hotels": [("Phoenix Hotel Yogyakarta", 4.6, "Rp 800rb–1,6jt"), ("Greenhost Boutique Hotel", 4.4, "Rp 600rb–1,2jt")],
    },
    {
        "slug": "bandung", "name": "Bandung", "region": "jawa_barat", "position": 3,
        "hero": "bandung/lembang-tourism-area.jpg", "card": "home/bandung.jpg",
        "lat": -6.9147, "lng": 107.6098, "best_time": "Sepanjang tahun (sejuk, hindari akhir pekan panjang)",
        "intro": "Kota kami sendiri — dan itulah kenapa kami tahu sudut-sudut terbaiknya. Dari kesejukan Lembang sampai "
                 "romantisnya Braga di malam hari, biarkan driver lokal kami yang mengantar.",
        "description": "Wisata alam Lembang dan Ciwidey, sejarah di Museum Asia Afrika, hingga kuliner dan belanja di Braga — "
                       "Bandung selalu punya agenda untuk keluarga maupun gathering kantor.",
        "highlights": [
            ("Kawasan Wisata Lembang", "Farmhouse, Floating Market, hingga Tangkuban Perahu — udara sejuk dan spot foto tanpa habis.", "bandung/lembang-tourism-area.jpg"),
            ("Kampung Cai Ranca Upas", "Camping ground di Ciwidey dengan penangkaran rusa dan pemandian air panas.", "bandung/kampung-cai-ranca-upas.jpg"),
            ("Jalan Braga", "Ikon kota kembang: arsitektur kolonial, kafe, dan suasana malam yang hidup.", "bandung/braga-street.jpg"),
            ("Museum Asia Afrika", "Napak tilas Konferensi Asia Afrika 1955 di jantung kota.", "bandung/museum-asia-afrika.jpg"),
        ],
        "itinerary": [
            ("Hari 1", "Bandung Utara", "Penjemputan di hotel/stasiun, Tangkuban Perahu, Farmhouse Lembang, kuliner sore di Punclut."),
            ("Hari 2", "Bandung Selatan", "Kawah Putih, Ranca Upas, petik stroberi, pulang lewat Situ Patenggang."),
            ("Hari 3", "Kota & Belanja", "Museum Asia Afrika, Braga, factory outlet Riau/Dago, pengantaran ke stasiun/bandara."),
        ],
        "route": [("Stasiun Bandung", -6.9144, 107.6023, "Titik jemput utama tamu luar kota."),
                  ("Lembang", -6.8117, 107.6175, "Kawasan wisata alam Bandung Utara."),
                  ("Ciwidey", -7.1050, 107.4350, "Kawah Putih & Ranca Upas."),
                  ("Braga", -6.9175, 107.6095, "Penutup di jantung kota.")],
        "faqs": [("Bisa jemput di bandara/stasiun?", "Bisa. Kami melayani penjemputan di Stasiun Bandung, Bandara Husein, KCIC Tegalluar, dan Whoosh Padalarang."),
                 ("Sewa harian dalam kota berapa jam?", "Paket 12 jam termasuk driver; kelebihan jam dihitung per jam sesuai penawaran."),
                 ("Cocok untuk gathering kantor?", "Sangat cocok — kami sering melayani outing perusahaan dengan beberapa unit sekaligus.")],
        "hotels": [("The Trans Luxury Hotel", 4.8, "Rp 2jt–4jt"), ("Padma Hotel Bandung", 4.7, "Rp 1,8jt–3,5jt")],
    },
    {
        "slug": "pangandaran", "name": "Pangandaran", "region": "jawa_barat", "position": 4,
        "hero": "pangandaran/green-canyon-pangandaran.jpg", "card": "home/pangandaran.jpg",
        "lat": -7.6841, "lng": 108.6500, "best_time": "April – Oktober (air jernih, ombak tenang)",
        "intro": "Pantai, tebing, sungai hijau zamrud, dan goa purba — semua dalam radius satu jam. "
                 "Pangandaran adalah pelarian akhir pekan favorit dari Bandung yang kami tempuh dalam 5–6 jam nyaman.",
        "description": "Body rafting di Green Canyon, berenang di Citumang yang sebening kaca, menyusuri Goa Sinjang Lawang, "
                       "lalu menutup hari dengan sunset di Batu Hiu.",
        "highlights": [
            ("Green Canyon", "Susur sungai Cijulang berwarna zamrud di antara tebing batu — body rafting paling ikonik di Jawa Barat.", "pangandaran/green-canyon-pangandaran.jpg"),
            ("Air Terjun Citumang", "Sungai jernih kehijauan untuk berenang, meloncat, dan river tubing ringan.", "pangandaran/air-terjun-citumang.jpg"),
            ("Goa Sinjang Lawang", "Goa purba raksasa dengan lorong sungai bawah tanah yang menakjubkan.", "pangandaran/goa-sinjang-lawang.jpg"),
            ("Pantai Batu Hiu", "Tebing karang berbentuk sirip hiu — spot sunset terbaik di pesisir selatan.", "pangandaran/pantai-batu-hiu.jpg"),
        ],
        "itinerary": [
            ("Hari 1", "Bandung → Pangandaran", "Berangkat pagi via Garut–Tasik, makan siang di Banjar, check-in, sunset di Pantai Batu Hiu."),
            ("Hari 2", "Green Canyon & Citumang", "Body rafting Green Canyon pagi, berenang di Citumang sore, seafood malam di pasar ikan."),
            ("Hari 3", "Goa & Pulang", "Goa Sinjang Lawang, Pantai Pangandaran, oleh-oleh, perjalanan pulang ke Bandung."),
        ],
        "route": [("Bandung", -6.9147, 107.6098, "Keberangkatan pagi."),
                  ("Garut", -7.2140, 107.9000, "Rehat & kuliner dodol."),
                  ("Banjar", -7.3690, 108.5400, "Makan siang."),
                  ("Pangandaran", -7.6841, 108.6500, "Tiba di pesisir selatan.")],
        "faqs": [("Berapa lama Bandung–Pangandaran?", "Sekitar 5–6 jam dengan rehat. Kami sarankan berangkat pagi agar sore sudah bisa menikmati pantai."),
                 ("Body rafting aman untuk anak?", "Aman untuk usia 7+ dengan pelampung dan pemandu berlisensi; kami bantu pesan operatornya."),
                 ("Ada penginapan ramah rombongan?", "Ada, dari villa tepi pantai sampai hotel bintang 3 — lihat rekomendasi di bawah.")],
        "hotels": [("Laut Biru Resort", 4.4, "Rp 700rb–1,4jt"), ("Pantai Indah Resort Hotel", 4.2, "Rp 500rb–1jt")],
    },
]

GALLERY = [  # (berkas, keterangan) — foto momen tamu untuk section beranda
    ("klien-17.jpg", "Kaldera Bromo dari Penanjakan"), ("klien-01.jpg", "Rombongan keluarga siap jelajah kota"),
    ("klien-05.jpg", "Menanti sunrise di Penanjakan"), ("klien-02.jpg", "Pantai Mustika, Pangandaran"),
    ("klien-03.jpg", "Tamu mancanegara di Yogyakarta"), ("klien-16.jpg", "Sunrise Bromo yang tak terlupakan"),
    ("klien-04.jpg", "Bersepeda keliling desa wisata"), ("klien-10.jpg", "Kebun teh Bandung Selatan"),
    ("klien-11.jpg", "Rombongan wisata religi di pesisir"), ("klien-20.jpg", "Telaga Warna, Dieng"),
    ("klien-13.jpg", "Bersama armada kami di Bromo"), ("klien-06.jpg", "Senja di pantai selatan"),
    ("klien-07.jpg", "Lautan pasir Bromo"), ("klien-08.jpg", "Gerbang Malioboro, Yogyakarta"),
    ("klien-14.jpg", "Pintu Langit"), ("klien-15.jpg", "Tuk Bimalukar, Dieng"),
    ("klien-18.jpg", "Atas Awan"), ("klien-19.jpg", "Semeru & Bromo saat fajar"),
    ("klien-21.jpg", "Tamu bersama tim RahazaTrans"), ("klien-22.jpg", "Bersantai di homestay"),
    ("klien-09.jpg", "Kawah Bromo"), ("klien-12.jpg", "Rombongan di Pantai Parangtritis"),
]

HOME_HERO = {
    "eyebrow": "Rental armada premium & paket wisata · Bandung",
    "title": "Perjalanan nyaman ke destinasi favorit Jawa",
    "subtitle": "Hiace Premio bersih dengan driver berpengalaman, harga transparan, dan itinerary yang dirancang "
                "agar rombongan Anda cukup duduk manis. Bromo, Yogyakarta, Pangandaran, Bandung — kami yang urus.",
    "chips": ["Driver profesional", "Armada terawat & ber-KIR", "Pelacakan real-time", "Bebas ribet, harga jujur"],
    "primary_label": "Minta Penawaran", "primary_href": "/quotation",
    "secondary_label": "Lihat Destinasi", "secondary_href": "/destinations",
}
HOME_GALLERY_TEXT = {
    "eyebrow": "Galeri", "title": "Momen perjalanan bersama tamu kami",
    "subtitle": "Dokumentasi nyata dari trip yang telah kami dampingi — keluarga, rombongan sekolah, gathering kantor, hingga tamu mancanegara.",
}
PAGE_HEROES = {  # slug halaman → (gambar, eyebrow, judul, subjudul)
    "destinations": ("home/hero-bromo.jpg", "Destinasi", "Ke mana kita minggu ini?",
                     "Rute favorit yang sudah ratusan kali kami tempuh — lengkap dengan itinerary, estimasi, dan tips lokal."),
    "fleet": ("home/hero-bromo-fajar.jpg", "Armada", "Unit bersih, terawat, siap jalan jauh",
              "Hiace Premio, Elf, hingga bus — semua ber-KIR, servis berkala, dan dilengkapi GPS."),
    "packages": ("home/hero-telaga.jpg", "Paket Wisata", "Paket lengkap, tinggal berangkat",
                 "Armada, driver, itinerary, dan penginapan dalam satu harga transparan."),
    "promo": ("home/hero-pantai.jpg", "Promo", "Harga spesial untuk trip berikutnya",
              "Diskon rombongan, promo hari kerja, dan penawaran musiman — cek sebelum memesan."),
    "blog": ("home/hero-kebun-teh.jpg", "Blog", "Cerita & tips perjalanan",
             "Panduan destinasi, tips rombongan, dan cerita dari balik kemudi."),
    "about": ("home/hero-kebun-teh.jpg", "Tentang Kami", "Berangkat dari Bandung, dipercaya se-Jawa",
              "RahazaTrans lahir dari kecintaan pada perjalanan darat yang nyaman, aman, dan jujur harganya."),
    "contact": ("home/hero-pantai.jpg", "Kontak", "Ngobrol dulu, pesan kemudian",
                "Tim kami siap membantu menyusun rute, armada, dan anggaran yang pas untuk rombongan Anda."),
    "trip-calculator": ("home/hero-bromo.jpg", "Kalkulator Trip", "Hitung perkiraan biaya dalam 1 menit",
                        "Pilih rute, tanggal, dan armada — estimasi langsung muncul, tanpa perlu menunggu balasan."),
}
TESTIMONIALS = [
    ("Ibu Ratna & Rombongan Majelis", "Wisata Religi, 2 unit Hiace", 5, "klien-11.jpg",
     "Driver sabar, mobil bersih, dan jadwal ziarah sampai pantai selatan semua tepat waktu. Ibu-ibu senang semua."),
    ("Keluarga Hartono", "Trip Keluarga Bromo 3H2M", 5, "klien-13.jpg",
     "Berangkat malam dari Bandung, sampai Penanjakan tepat sunrise. Anak-anak nyaman tidur di Hiace Premio sepanjang jalan."),
    ("Michael & Friends", "International Guests · Yogyakarta", 5, "klien-03.jpg",
     "Our driver knew every hidden spot in Jogja and was incredibly patient with our schedule. Highly recommended!"),
]


# --------------------------------------------------------------------------- HELPERS
class Importer:
    def __init__(self, db, content_dir: Path, dry: bool, force_media: bool = False):
        self.db, self.dir, self.dry, self.force = db, content_dir, dry, force_media
        self.urls = {}
        self.stats = {"media_new": 0, "media_reused": 0}

    async def folder(self, name: str, parent: str = "") -> str:
        doc = await self.db[ml.FOLDERS].find_one({"parent_id": parent, "name": name}, {"_id": 0, "id": 1})
        if doc:
            return doc["id"]
        if self.dry:
            return "dry"
        return (await ml.create_folder(self.db, name, parent, ACTOR))["id"]

    async def media(self, rel: str, folder_id: str, alt: str) -> str:
        """Unggah berkas relatif ke content dir (sekali saja) → URL publik."""
        if rel in self.urls:
            return self.urls[rel]
        key = f"content_import:{rel}"
        existing = await self.db[ml.MEDIA].find_one({"import_key": key, "deleted": False}, {"_id": 0, "id": 1, "version": 1})
        if existing and self.force and not self.dry:
            await ml.soft_delete_assets(self.db, [existing["id"]])
            existing = None
        if existing:
            self.stats["media_reused"] += 1
            url = ml.media_url(existing["id"], existing.get("version") or 1)
        else:
            path = self.dir / rel
            if not path.exists():
                raise SystemExit(f"Berkas tidak ditemukan: {path}")
            if self.dry:
                url = f"/api/public/media/DRY-{Path(rel).stem}"
            else:
                meta = ms.upload_bytes(path.read_bytes(), ms.guess_content_type(path.name),
                                       filename=path.name, folder="library")
                doc = await ml.register_asset(self.db, meta, ACTOR, folder_id=folder_id, alt=alt,
                                              source="import", extra={"import_key": key})
                url = ml.media_url(doc["id"], 1)
            self.stats["media_new"] += 1
        self.urls[rel] = url
        return url

    async def upsert(self, coll: str, match: dict, doc: dict, label: str, id_prefix: str = "doc"):
        existing = await self.db[coll].find_one(match, {"_id": 0, "id": 1, "created_at": 1})
        action = "update" if existing else "create"
        print(f"  [{coll}] {action}: {label}")
        if self.dry:
            return
        if existing:
            doc = {k: v for k, v in doc.items() if k != "id"}
            await self.db[coll].update_one({"id": existing["id"]}, {"$set": {**doc, "updated_at": now_iso()}})
        else:
            doc.setdefault("id", new_id(id_prefix))
            await self.db[coll].insert_one({**match, **doc, "created_at": now_iso(), "updated_at": now_iso()})


# --------------------------------------------------------------------------- STEPS
async def import_destinations(imp: Importer, root_folder: str):
    print("\n== Destinasi")
    for d in DESTINATIONS:
        fid = await imp.folder(d["name"], root_folder)
        hero = await imp.media(d["hero"], fid, f"{d['name']} — {Path(d['hero']).stem}")
        card = await imp.media(d["card"], fid, f"Kartu {d['name']}")
        highlights = []
        for title, desc, img in d["highlights"]:
            highlights.append({"title": title, "desc": desc, "image": await imp.media(img, fid, f"{d['name']} — {title}")})
        gallery = [card] + [h["image"] for h in highlights if h["image"] != hero]
        doc = {
            "name": d["name"], "region": d["region"], "position": d["position"], "popular": True,
            "status": "published", "source": "cms", "ops_active": True,
            "hero_image": hero, "gallery": gallery, "intro": d["intro"], "description": d["description"],
            "highlights": highlights,
            "itinerary": [{"day": a, "title": b, "desc": c} for a, b, c in d["itinerary"]],
            "route_points": [{"name": n, "lat": la, "lng": ln, "desc": ds} for n, la, ln, ds in d["route"]],
            "faqs": [{"q": q, "a": a} for q, a in d["faqs"]],
            "hotel_recommendations": [{"name": n, "rating": r, "price_range": p} for n, r, p in d["hotels"]],
            "best_time": d["best_time"], "lat": d["lat"], "lng": d["lng"],
            "meta_title": f"{d['name']} · Paket Wisata & Sewa Hiace dari Bandung | RahazaTrans",
            "meta_description": d["description"][:155], "og_image": hero,
        }
        await imp.upsert("destinations", {"slug": d["slug"]}, doc, d["name"], "dst")
    if not imp.dry:
        # destinasi lain tanpa urutan → taruh setelah konten impor agar kartu utama beranda = foto asli
        await imp.db.destinations.update_many({"position": {"$exists": False}}, {"$set": {"position": 50}})


async def import_home(imp: Importer, root_folder: str):
    print("\n== Beranda")
    fid = await imp.folder("Beranda", root_folder)
    gfid = await imp.folder("Galeri Tamu", root_folder)
    hero_img = await imp.media("home/hero-bromo.jpg", fid, "Hero beranda — kaldera Bromo")
    items = [{"url": await imp.media(f"gallery/{f}", gfid, cap), "caption": cap} for f, cap in GALLERY]

    page = await imp.db.site_pages.find_one({"slug": "home"}, {"_id": 0}) or {}
    from routers.site_pages import default_sections
    sections = page.get("sections") or default_sections("home")
    types = [s.get("type") for s in sections]
    for s in sections:
        if s.get("type") == "hero":
            s["data"] = {**(s.get("data") or {}), **HOME_HERO, "image": hero_img}
        if s.get("type") == "gallery":
            s["data"] = {**HOME_GALLERY_TEXT, "items": items}
            s["enabled"] = True
    if "gallery" not in types:
        idx = types.index("testimonials") + 1 if "testimonials" in types else len(sections)
        sections.insert(idx, {"id": new_id("sec"), "type": "gallery", "enabled": True,
                              "data": {**HOME_GALLERY_TEXT, "items": items}})
    await imp.upsert("site_pages", {"slug": "home"},
                     {"title": "Beranda", "sections": sections}, "hero + galeri", "pge")


async def import_page_heroes(imp: Importer, root_folder: str):
    print("\n== Hero halaman")
    fid = await imp.folder("Beranda", root_folder)
    from routers.site_pages import default_sections
    for slug, (img, eyebrow, title, subtitle) in PAGE_HEROES.items():
        url = await imp.media(img, fid, f"Hero {slug}")
        page = await imp.db.site_pages.find_one({"slug": slug}, {"_id": 0}) or {}
        sections = page.get("sections") or default_sections(slug)
        for s in sections:
            if s.get("type") == "page_hero":
                s["data"] = {**(s.get("data") or {}), "eyebrow": eyebrow, "title": title, "subtitle": subtitle, "image": url}
        await imp.upsert("site_pages", {"slug": slug},
                         {"title": page.get("title") or slug, "sections": sections}, slug, "pge")


async def import_testimonials(imp: Importer, root_folder: str):
    print("\n== Testimoni")
    fid = await imp.folder("Galeri Tamu", root_folder)
    for name, role, rating, img, quote in TESTIMONIALS:
        avatar = await imp.media(f"gallery/{img}", fid, name)
        await imp.upsert("testimonials", {"name": name},
                         {"role": role, "rating": rating, "avatar": avatar, "quote": quote,
                          "approved": True, "position": 1}, name, "tst")
    if not imp.dry:
        # buang avatar demo (pravatar) supaya beranda hanya menampilkan tamu nyata
        await imp.db.testimonials.update_many({"avatar": {"$regex": "pravatar"}}, {"$set": {"approved": False, "position": 99}})


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--content-dir", default=str(ROOT / "content_import" / "assets"))
    ap.add_argument("--dry-run", action="store_true", help="tampilkan rencana tanpa menulis")
    ap.add_argument("--skip-testimonials", action="store_true")
    ap.add_argument("--force-media", action="store_true", help="unggah ulang foto yang sudah pernah diimpor (foto lama diarsipkan)")
    args = ap.parse_args()

    content_dir = Path(args.content_dir)
    if not content_dir.is_dir():
        raise SystemExit(f"Folder konten tidak ada: {content_dir}")
    mongo, dbname = os.environ["MONGO_URL"], os.environ["DB_NAME"]
    db = AsyncIOMotorClient(mongo)[dbname]
    info = ms.storage_info()
    if not info["ready"] and not args.dry_run:
        raise SystemExit(f"Penyimpanan media belum siap: {info.get('reason')}")
    print(f"DB={dbname} · media backend={ms.backend_name()} · konten={content_dir}{' · DRY-RUN' if args.dry_run else ''}")

    imp = Importer(db, content_dir, args.dry_run, args.force_media)
    if not args.dry_run:
        await ml.ensure_indexes(db)
    root = await imp.folder("Konten Situs")
    await import_destinations(imp, root)
    await import_home(imp, root)
    await import_page_heroes(imp, root)
    if not args.skip_testimonials:
        await import_testimonials(imp, root)
    print(f"\nSelesai. Media baru={imp.stats['media_new']} · dipakai ulang={imp.stats['media_reused']}")


if __name__ == "__main__":
    asyncio.run(main())
