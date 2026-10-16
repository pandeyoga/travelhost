import { useEffect, useState } from "react";
import apiClient from "@/services/apiClient";

// useSiteFeatures — fitur situs publik yang bisa di-toggle dari ERP (CMS → Pengaturan Situs).
// Sumber: settings.company_info via GET /public/company. Cache satu promise agar tidak refetch.
const DEFAULTS = { show_trip_calculator: true };
let cache = null;
let inflight = null;

const load = () => {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = apiClient.get("/public/company")
      .then((r) => { cache = { ...DEFAULTS, ...(r.data || {}) }; return cache; })
      .catch(() => DEFAULTS)
      .finally(() => { inflight = null; });
  }
  return inflight;
};

export const invalidateSiteFeatures = () => { cache = null; };

export function useSiteFeatures() {
  const [feat, setFeat] = useState(cache || DEFAULTS);
  const [ready, setReady] = useState(!!cache);
  useEffect(() => {
    let active = true;
    load().then((f) => { if (active) { setFeat(f); setReady(true); } });
    return () => { active = false; };
  }, []);
  return { ready, tripCalculator: feat.show_trip_calculator !== false };
}

export default useSiteFeatures;
