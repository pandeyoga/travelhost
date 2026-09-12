import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import apiClient from "@/services/apiClient";

/**
 * CMS-12 — URL lama TIDAK boleh menjadi jalan buntu.
 *
 * Kalau halaman detail publik gagal menemukan slug (404), hook ini menanyakan alamat yang
 * sedang dibuka ke `GET /api/public/redirect`. Bila editor pernah mengganti slug konten
 * (atau memasang pengalihan manual), pengunjung LANGSUNG dipindahkan ke alamat baru dengan
 * `replace` — sehingga tombol Kembali tidak terjebak memantul ke halaman mati.
 *
 * Dipakai di SATU tempat per halaman detail agar tidak ada halaman yang lupa: tautan dari
 * Google, WhatsApp, atau blog pihak lain adalah sumber trafik nyata yang sudah dibayar.
 *
 * @param {boolean} shouldTry hanya dicoba saat konten benar-benar tidak ditemukan
 * @returns {{checking: boolean, to: string}}
 */
export default function useSlugRedirect(shouldTry) {
  const navigate = useNavigate();
  const location = useLocation();
  const [checking, setChecking] = useState(false);
  const [to, setTo] = useState("");

  useEffect(() => {
    if (!shouldTry) {
      setChecking(false);
      setTo("");
      return undefined;
    }
    let alive = true;
    setChecking(true);
    apiClient
      .get("/public/redirect", { params: { path: location.pathname } })
      .then((r) => {
        if (!alive) return;
        const target = String(r?.data?.to_path || "");
        if (target && target !== location.pathname) {
          setTo(target);
          navigate(`${target}${location.search || ""}`, { replace: true });
        }
      })
      .catch(() => { /* tidak ada pengalihan → halaman "tidak ditemukan" yang jujur */ })
      .finally(() => { if (alive) setChecking(false); });
    return () => { alive = false; };
  }, [shouldTry, location.pathname, location.search, navigate]);

  return { checking, to };
}
