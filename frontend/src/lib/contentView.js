// lib/contentView.js — CMS-08: catat tampilan konten + jejak konten terakhir.
//
// Dua hal sekaligus, sekali panggil dari halaman detail:
//  1. `POST /api/public/content-view` → angka tampilan per konten (server yang anti-inflasi).
//  2. jejak `content_last` di localStorage → dikirim bersama form lead/pesanan sehingga
//     laporan "konten → lead → pesanan" tahu artikel/destinasi mana pemicunya.
//
// Tidak pernah melempar error: analitik TIDAK boleh merusak halaman publik.
import apiClient from "@/services/apiClient";

const KEY = "tf_content_last";
const sent = new Set();

export function recordContentTouch({ kind, slug, title = "", path = "" }) {
  if (!kind || !slug) return;
  try {
    localStorage.setItem(KEY, JSON.stringify({
      kind, slug, title, path: path || window.location.pathname,
      ts: new Date().toISOString(),
    }));
  } catch { /* private mode */ }
}

export function getContentTouch() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** Catat satu tampilan konten (idempoten per sesi tab, server tetap punya jaring dedupe). */
export function trackContentView({ kind, slug, title = "", path = "" }) {
  if (!kind || !slug) return;
  recordContentTouch({ kind, slug, title, path });
  const key = `${kind}:${slug}`;
  if (sent.has(key)) return;
  sent.add(key);
  apiClient.post("/public/content-view", { kind, slug, title }).catch(() => {
    sent.delete(key);   // biar bisa dicoba lagi saat kunjungan berikutnya
  });
}

export default trackContentView;
