# Deploy ke VPS (Docker + MongoDB 7 + Caddy)

VPS: `212.85.25.26` (Ubuntu 22.04/24.04, login root).

## 1. Instalasi pertama (tanpa domain, akses via IP)

```bash
ssh root@212.85.25.26
git clone https://github.com/pandeyoga/travelhost.git /opt/travel && cd /opt/travel
OWNER_EMAIL=admin@anda.com OWNER_PASSWORD='GantiKataSandiKuat' bash deploy/install_vps.sh
```

Hasil: situs di `http://212.85.25.26`, ERP di `http://212.85.25.26/app/login`.
Jika VPS sudah punya project lain di port 80/443 (SIPRO), otomatis jadi `http://212.85.25.26:8080` — lihat bagian anti bentrok di bawah.
Tambahkan `SEED_DEMO=true` di depan perintah bila ingin data demo.

## 2. Pasang domain (nanti, saat domain siap)

Arahkan A record `rahazatrans.com` dan `erp.rahazatrans.com` → `212.85.25.26`, lalu:

```bash
cd /opt/travel && bash deploy/set_domain.sh rahazatrans.com erp.rahazatrans.com email@anda.com
```

- Situs publik: `https://rahazatrans.com` — tautan "Masuk ERP" sudah tidak ada di website.
- ERP **hanya** lewat `https://erp.rahazatrans.com` (root otomatis ke `/app/login`).
  `https://rahazatrans.com/app/...` dialihkan ke subdomain ERP.
- Tanpa subdomain (`bash deploy/set_domain.sh rahazatrans.com "" email@anda.com`) ERP tetap
  bisa diakses lewat slug `https://rahazatrans.com/app/login`.

## 3. Update kode

```bash
cd /opt/travel && bash deploy/update.sh
```
Backup otomatis → `git reset --hard origin/main` → build → ganti container. Data & `.env` aman.

## 3b. Isi konten situs (foto + copywriting)

Foto destinasi, galeri tamu, dan teks halaman ada di repo (`content_import/assets/`). Setelah
`update.sh`, jalankan sekali (aman diulang — tidak menduplikasi):

```bash
cd /opt/travel && bash deploy/import_content.sh            # tambah --dry-run untuk melihat rencana
```
Hasil: Media Library → folder "Konten Situs"; destinasi Bromo/Yogyakarta/Bandung/Pangandaran tayang;
Beranda punya hero + section "Galeri Momen Tamu"; hero semua halaman terisi; 3 testimoni tamu.
Semua tetap bisa disunting dari ERP → Konten Web.

## 4. Backup / restore

```bash
bash deploy/backup.sh                                          # manual (cron harian 02:00 sudah dipasang)
bash deploy/backup.sh restore deploy/backups/travel-2026-06-01_0200.archive.gz
```

## 5. Perintah berguna

```bash
cd /opt/travel/deploy
docker compose ps
docker compose logs -f backend
docker compose exec -T backend python /app/deploy/create_owner.py   # reset kata sandi owner (dari .env)
nano .env && docker compose up -d --force-recreate backend           # ubah env (API key, dsb.)
```

## Catatan
- `deploy/.env` dibuat saat instalasi dan tidak masuk git (`Caddyfile.generated` juga).
- Frontend dibangun dengan API same-origin (`/api`), jadi satu image berlaku untuk IP, domain, dan subdomain.

## WhatsApp (OpenWA) di VPS
Container `openwa` (Node 20 + Chromium, image dari `deploy/Dockerfile.openwa`) ikut jalan bila
`COMPOSE_PROFILES=wa` di `deploy/.env` (default saat instalasi). Sesi WA tersimpan di volume
`travel_openwa_data`, jadi restart/update **tidak** perlu scan ulang.

1. Login ERP → **Sistem › Integrasi API › WhatsApp** → provider **OpenWA** → simpan.
2. Klik **Tampilkan QR** lalu scan dari HP (WhatsApp › Perangkat tertaut).
3. Kirim invoice/kwitansi via tombol WA di Keuangan.

Perintah:
```bash
cd /opt/travel/deploy
docker compose logs -f openwa            # lihat log / QR di terminal
docker compose restart openwa            # restart sidecar
docker compose down openwa && docker volume rm travel_openwa_data && docker compose up -d openwa   # ganti nomor (scan ulang)
```
Matikan WA: set `COMPOSE_PROFILES=` (kosong) di `.env` lalu `docker compose up -d --remove-orphans`.

## VPS yang sudah punya project lain (mis. SIPRO) — anti bentrok
- Nama project `travel` → container/volume/network `travel_*`, terpisah dari `sipro_*`.
- Port: `install_vps.sh` mendeteksi 80/443 yang sudah dipakai → otomatis **mode behind**:
  situs ini hanya membuka `HTTP_PORT` (default **8080**), TLS tetap di proxy yang ada.
  - Sebelum domain: `http://212.85.25.26:8080` (ERP `…:8080/app/login`).
  - Setelah `set_domain.sh`, skrip mencetak blok untuk ditambahkan ke Caddyfile SIPRO
    (`/opt/sipro/deploy/Caddyfile`, simpan ke repo SIPRO agar tidak hilang saat update mereka):
    ```
    rahazatrans.com, erp.rahazatrans.com {
    	reverse_proxy 212.85.25.26:8080
    }
    ```
    lalu `cd /opt/sipro/deploy && docker compose restart caddy`. Caddy kita yang menangani
    pemisahan situs publik vs subdomain ERP (Host header diteruskan apa adanya).
- Port internal (8001, 8033, 27017) tidak dipublikasikan ke host → tidak bentrok dengan Mongo/backend SIPRO.
- Paksa mode: `PROXY_MODE=own` (Caddy kita pegang 80/443) atau `PROXY_MODE=behind HTTP_PORT=8081`.
