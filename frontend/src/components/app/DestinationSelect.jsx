import { useEffect, useState } from "react";
import apiClient from "@/services/apiClient";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

// INV-REF-02: destinasi booking = relasi ke master `destinations` — selector, bukan teks bebas.
// Nilai warisan (pra-master) tetap ditampilkan sebagai opsi nonaktif agar dialog edit tidak rusak.
export const DestinationSelect = ({ value, onChange, testId = "destination-select", placeholder = "Pilih destinasi", optionsPath = "/bookings/destination-options" }) => {
  const [options, setOptions] = useState([]);
  useEffect(() => {
    apiClient.get(optionsPath)
      .then((r) => setOptions(Array.isArray(r.data) ? r.data : []))
      .catch(() => setOptions([]));
  }, [optionsPath]);
  const known = options.some((o) => o.value === value);
  return (
    <Select value={value || ""} onValueChange={onChange}>
      <SelectTrigger data-testid={testId}><SelectValue placeholder={placeholder} /></SelectTrigger>
      <SelectContent>
        {value && !known ? (
          <SelectItem value={value}>{value} (warisan — di luar master)</SelectItem>
        ) : null}
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value} data-testid={`${testId}-opt-${o.slug || o.value}`}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};

export default DestinationSelect;
