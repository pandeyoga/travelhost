import { useCallback, useEffect, useState } from "react";
import apiClient from "@/services/apiClient";
import { useLangValue } from "@/hooks/useLang";

// Hook fetch sederhana dengan state loading/error + reload (anti StrictMode double-fetch).
// CMS-06: `lang` masuk dependency → saat pengunjung mengganti bahasa, SELURUH data publik
// otomatis dimuat ulang dalam bahasa itu (tanpa perlu menyentuh tiap halaman).
export function useResource(path) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);
  const lang = useLangValue();

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    apiClient
      .get(path)
      .then((res) => {
        if (active) setData(res.data);
      })
      .catch((e) => {
        if (active) setError(e?.response?.data?.detail || "Gagal memuat data");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [path, tick, lang]);

  return { data, loading, error, reload };
}
