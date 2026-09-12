import { useCallback, useEffect, useState } from "react";
import { DEFAULT_LANG, LANGS, getLang, setLang as applyLang, subscribeLang } from "@/lib/lang";

// hooks/useLang.js — CMS-06: baca & ubah bahasa aktif dari komponen React.
// Semua komponen ikut re-render saat bahasa berubah (langganan ke store modul), sehingga
// data publik otomatis di-fetch ulang lewat `useResource`.
export function useLang() {
  const [lang, setState] = useState(getLang());
  useEffect(() => subscribeLang(setState), []);
  const change = useCallback((next) => { applyLang(next); }, []);
  return { lang, setLang: change, langs: LANGS, defaultLang: DEFAULT_LANG };
}

export function useLangValue() {
  const [lang, setState] = useState(getLang());
  useEffect(() => subscribeLang(setState), []);
  return lang;
}

export default useLang;
